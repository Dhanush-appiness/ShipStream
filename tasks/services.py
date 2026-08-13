"""
Service layer for the tasks app.

Business logic for tasks, comments, labels, task-label links, activity logs,
and notifications lives here rather than in views or serializers. Views call
into these services and stay thin (see docs/adr/0002-service-layer.md for
the reasoning). Every write path here that has more than one meaningful
failure mode is wrapped in try/except so failures are logged with context
before being re-raised to the caller (the DRF exception handler in
common/exceptions.py turns them into the API's standard error envelope).
"""

import logging
import re

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from organizations.models import Membership

from .models import ActivityLog, Comment, Label, Notification, Task, TaskLabel

logger=logging.getLogger(__name__)

# How long a cached dashboard aggregation is trusted before falling back to
# the database, even if no invalidation event fired. This is a safety net,
# not the primary invalidation mechanism - see TaskService.invalidate_dashboard_cache.
DASHBOARD_CACHE_TTL=300

# Task status values. Mirrors Task.STATUS_CHOICES - kept as separate
# constants here so service-layer code never compares against a bare
# string literal.
STATUS_TODO='TODO'
STATUS_IN_PROGRESS='IN_PROGRESS'
STATUS_DONE='DONE'
STATUS_BLOCKED='BLOCKED'

# ActivityLog.action values written by this service layer.
ACTION_TASK_CREATED='TASK_CREATED'
ACTION_TASK_UPDATED='TASK_UPDATED'
ACTION_TASK_DELETED='TASK_DELETED'
ACTION_COMMENT_ADDED='COMMENT_ADDED'

# Notification.type values written by this service layer.
NOTIFICATION_TASK_ASSIGNED='TASK_ASSIGNED'
NOTIFICATION_TASK_UPDATED='TASK_UPDATED'
NOTIFICATION_MENTION='MENTION'

# Matches an @email.address style mention inside comment text, e.g.
# "@alice@example.com please review". Deliberately requires a full email
# rather than a bare username, since that's the only unambiguous way to
# resolve a mention to exactly one Membership without a separate lookup table.
MENTION_PATTERN=r'@([\w\.-]+@[\w\.-]+\.\w+)'


class TaskService:
    """Business logic for creating, mutating, and querying tasks."""

    @staticmethod
    def broadcast_task_update(task,action):
        """
        Push a task change to every WebSocket client connected to this
        task's project. Sends to the project-scoped Channels group
        (project_<id>), never a global group - see
        docs/adr/0003-realtime-architecture.md for why.
        """
        logger.info('Broadcasting %s for task %s',action,task.id)
        channel_layer=get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'project_{task.project_id}',
            {
                'type':'task_updated',
                'action':action,
                'task_id':task.id,
                'title':task.title,
                'status':task.status,
            },
        )


    @staticmethod
    def get_tasks(organization):
        """
        Return every non-deleted task belonging to the given organization,
        with the FKs the task list/detail serializers need pre-fetched to
        stay N+1-free, ordered for kanban-column rendering
        (status, then position within that column).
        """
        return Task.objects.for_organization(
            organization
        ).select_related(
            'project',
            'assignee',
            'created_by',
        ).order_by(
            'status','position','id'
            )

    @staticmethod
    def get_dashboard_cache_key(organization):
        """Redis cache key for one organization's dashboard aggregation."""
        return f'dashboard:org:{organization.id}'

    @staticmethod
    def invalidate_dashboard_cache(organization):
        """
        Drop the cached dashboard for this organization. Called from every
        task mutation (create/update/delete/restore/reorder) so the next
        read recomputes fresh numbers instead of waiting out the TTL.
        """
        cache.delete(TaskService.get_dashboard_cache_key(organization))

    @staticmethod
    def get_dashboard(organization):
        """
        Return status counts, overdue count, and per-assignee workload for
        an organization, computed as database aggregations (not in Python).
        Cached in Redis for DASHBOARD_CACHE_TTL seconds; callers that
        mutate tasks are responsible for invalidating via
        invalidate_dashboard_cache so this stays correct between writes.
        """
        cache_key=TaskService.get_dashboard_cache_key(organization)
        cached=cache.get(cache_key)
        if cached is not None:
            return cached

        tasks=Task.objects.for_organization(organization)

        status_counts={
            STATUS_TODO:tasks.filter(status=STATUS_TODO).count(),
            STATUS_IN_PROGRESS:tasks.filter(status=STATUS_IN_PROGRESS).count(),
            STATUS_DONE:tasks.filter(status=STATUS_DONE).count(),
            STATUS_BLOCKED:tasks.filter(status=STATUS_BLOCKED).count(),
        }

        overdue=tasks.filter(
            due_date__lt=timezone.localdate(),
        ).exclude(
            status=STATUS_DONE,
        ).count()

        workload=list(
            tasks.filter(
                assignee__isnull=False,
            ).exclude(
                status=STATUS_DONE,
            ).values(
                'assignee_id',
                'assignee__email',
            ).annotate(
                task_count=Count('id'),
            ).order_by(
                '-task_count',
                'assignee_id',
            )
        )

        dashboard={
            'status_counts':status_counts,
            'overdue':overdue,
            'workload':workload,
        }

        cache.set(cache_key,dashboard,DASHBOARD_CACHE_TTL)

        return dashboard

    @staticmethod
    def search_tasks(organization,query):
        """
        Free-text search over an organization's tasks. On PostgreSQL this
        filters and ranks against the persisted search_vector column
        (kept up to date by Task.save()) so the GIN index on that column
        actually gets used - see README's "Database Indexing Decisions"
        section. Falls back to icontains on non-Postgres backends (e.g.
        SQLite in a local dev shell) since SearchVector/SearchRank are
        Postgres-only.
        """
        tasks=TaskService.get_tasks(organization)

        if not query:
            return tasks

        if connection.vendor!='postgresql':
            return tasks.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query)
            )

        search_query=SearchQuery(query)

        return tasks.filter(
            search_vector=search_query,
        ).annotate(
            rank=SearchRank(
                F('search_vector'),
                search_query,
            ),
        ).order_by(
            '-rank',
            'id',
        )

    @staticmethod
    def get_task(task_id,organization):
        """Return a single task scoped to the organization, or 404."""
        return get_object_or_404(
            Task.objects.for_organization(organization),
            id=task_id,
        )

    @staticmethod
    def create_task(serializer,user,organization):
        """
        Create a task from a validated serializer, then perform every side
        effect a new task requires: activity log entry, an assignment
        notification if it was created with an assignee, a WebSocket
        broadcast to the project's connected clients, and dashboard cache
        invalidation.
        """
        try:
            project=serializer.validated_data['project']
            if project.organization!=organization:
                raise ValueError("You cannot create tasks in another organization's task.")
            serializer.save(created_by=user)
            ActivityLogService.log(
                organization,
                serializer.instance,
                user,
                ACTION_TASK_CREATED,
            )
            task = serializer.instance
            if task.assignee:
                NotificationService.create_notification(
                task.assignee,
                task,
                NOTIFICATION_TASK_ASSIGNED,
                'New Task Assigned',
                f"You were assigned '{task.title}'.",
                )
            TaskService.broadcast_task_update(task,'created')
            TaskService.invalidate_dashboard_cache(organization)
        except Exception as exc:
            logger.error('Failed to create task for organization %s: %s',organization.id,exc)
            raise

    @staticmethod
    def update_task(task,validated_data):
        """
        Apply field changes to an existing task and perform the same side
        effects as create_task: notify the assignee, log the activity,
        broadcast the change, invalidate the dashboard cache.
        """
        try:
            for key, value in validated_data.items():
                setattr(task, key,value)
            task.save()
            if task.assignee:
                NotificationService.create_notification(
                task.assignee,
                task,
                NOTIFICATION_TASK_UPDATED,
                'Task Updated',
                f"Task '{task.title}' has been updated.",
            )
            ActivityLogService.log(
                task.project.organization,
                task,
                task.created_by,
                ACTION_TASK_UPDATED,
            )
            TaskService.broadcast_task_update(task,'updated')
            TaskService.invalidate_dashboard_cache(task.project.organization)
            return task
        except Exception as exc:
            logger.error('Failed to update task %s: %s',task.id,exc)
            raise

    @staticmethod
    def delete_task(task):
        """
        Soft-delete a task (see Task.delete()), log the deletion, broadcast
        it, and invalidate the dashboard cache so deleted tasks stop being
        counted immediately rather than after the cache TTL expires.
        """
        try:
            task.delete()
            ActivityLogService.log(
                task.project.organization,
                task,
                task.created_by,
                ACTION_TASK_DELETED,
            )
            TaskService.broadcast_task_update(task,'deleted')
            TaskService.invalidate_dashboard_cache(task.project.organization)
        except Exception as exc:
            logger.error('Failed to delete task %s: %s',task.id,exc)
            raise

    @staticmethod
    def restore_task(organization,task_id):
        """
        Bring a soft-deleted task back (admin-only at the view layer - see
        TaskRestoreView). 404s if no matching soft-deleted task exists for
        this organization, which also prevents restoring a task that was
        never deleted in the first place.
        """
        try:
            task=get_object_or_404(
                Task.all_objects.filter(project__organization=organization),
                id=task_id,
                is_deleted=True,
            )
            task.is_deleted=False
            task.save(update_fields=['is_deleted'])
            TaskService.invalidate_dashboard_cache(organization)
            return task
        except Exception as exc:
            logger.error('Failed to restore task %s: %s',task_id,exc)
            raise

    @staticmethod
    @transaction.atomic
    def reorder_task(organization,task_id,status,position):
        """
        Move a task to a new status column and/or position within it,
        shifting every other task in the affected column(s) to keep
        `position` values contiguous. Wrapped in a single DB transaction
        so a failure partway through can't leave positions inconsistent.

        Three cases, handled separately:
        1. Same column, moving down (higher position): tasks strictly
           between the old and new position shift up by one to close the gap.
        2. Same column, moving up (lower position): tasks between the new
           and old position shift down by one to make room.
        3. Different column: the old column's tasks after the old position
           shift up by one (closing the gap left behind), and the new
           column's tasks at/after the new position shift down by one
           (making room for the incoming task).
        """
        try:
            task=get_object_or_404(
                Task.objects.for_organization(organization),
                id=task_id,
            )
            old_status=task.status
            old_position=task.position
            if old_status==status:
                if old_position<position:
                    # Moving down within the same column: close the gap the
                    # task leaves behind by shifting the tasks it passed over up by one.
                    Task.objects.filter(
                        project=task.project,
                        status=status,
                        position__gt=old_position,
                        position__lte=position,
                    ).update(
                        position=F('position')-1
                    )
                elif old_position>position:
                    # Moving up within the same column: make room at the
                    # target position by shifting the tasks it passes over down by one.
                    Task.objects.filter(
                        project=task.project,
                        status=status,
                        position__gte=position,
                        position__lt=old_position,
                    ).update(
                        position=F('position')+1
                    )
            else:
                # Moving to a different column: close the gap in the old
                # column, then make room at the target position in the new one.
                Task.objects.filter(
                    project=task.project,
                    status=old_status,
                    position__gt=old_position,
                ).update(
                    position=F('position')-1
                )
                Task.objects.filter(
                    project=task.project,
                    status=status,
                    position__gte=position,
                ).update(
                    position=F('position')+1
                )
            task.status=status
            task.position=position
            task.save(update_fields=['status','position'])
            TaskService.invalidate_dashboard_cache(organization)
            return task
        except Exception as exc:
            logger.error('Failed to reorder task %s: %s',task_id,exc)
            raise



class CommentService:
    """Business logic for task comments, including @mention notifications."""

    @staticmethod
    def get_comments(task_id,organization):
        """Return a task's comments, scoped to the organization, with author/task pre-fetched."""
        return Comment.objects.filter(
            task__id=task_id,
            task__project__organization=organization,
        ).select_related(
            'author',
            'task',
        )

    @staticmethod
    def extract_mentions(content):
        """Return every @email-style mention found in comment text, as a list of email strings."""
        return re.findall(
            MENTION_PATTERN,
            content,
        )

    @staticmethod
    def create_comment(serializer,user,organization):
        """
        Save a comment, log the activity, then resolve any @mentions in its
        content to organization members and notify each one (except the
        comment's own author, who doesn't need to be told they mentioned
        themselves). Notification emails are dispatched to Celery, not sent
        inline, so comment creation isn't blocked on outbound mail.
        """
        try:
            task=serializer.validated_data['task']

            if task.project.organization!=organization:
                raise ValueError(
                    "Cannot comment on another organization's task."
                )

            comment=serializer.save(author=user)

            ActivityLogService.log(
                organization,
                task,
                user,
                ACTION_COMMENT_ADDED,
            )

            mentioned_emails=CommentService.extract_mentions(
                comment.content
            )

            mentioned_memberships=Membership.objects.filter(
                organization=organization,
                user__email__in=mentioned_emails,
            ).select_related('user')

            from .tasks import send_mention_notification_email

            for membership in mentioned_memberships:
                if membership.user==user:
                    continue

                notification=NotificationService.create_notification(
                    membership.user,
                    task,
                    NOTIFICATION_MENTION,
                    'You were mentioned in a comment',
                    f"{user.email} mentioned you in '{task.title}'.",
                )

                send_mention_notification_email.delay(
                    notification.id
                )
        except Exception as exc:
            logger.error('Failed to create comment on task: %s',exc)
            raise

    @staticmethod
    def get_comment(comment_id,organization):
        """Return a single comment scoped to the organization, or 404."""
        return get_object_or_404(
            Comment,
            id=comment_id,
            task__project__organization=organization,
        )

    @staticmethod
    def update_comment(comment,validated_data):
        """Apply field changes to an existing comment and save."""
        for key, value in validated_data.items():
            setattr(comment,key,value)
        comment.save()
        return comment

    @staticmethod
    def delete_comment(comment):
        """Delete a comment (hard delete - comments aren't soft-deleted)."""
        comment.delete()


class LabelService:
    """Business logic for org-scoped labels."""

    @staticmethod
    def get_labels(organization):
        """Return every label belonging to the organization."""
        return Label.objects.filter(
        organization=organization
        ).order_by('created_at', 'id')

    @staticmethod
    def create_label(serializer,organization):
        """Save a new label, scoped to the given organization."""
        serializer.save(
            organization=organization
        )

    @staticmethod
    def get_label(label_id,organization):
        """Return a single label scoped to the organization, or 404."""
        return get_object_or_404(
            Label,
            id=label_id,
            organization=organization,
        )

    @staticmethod
    def update_label(label,validated_data):
        """Apply field changes to an existing label and save."""
        for key, value in validated_data.items():
            setattr(label,key,value)
        label.save()
        return label

    @staticmethod
    def delete_label(label):
        """Delete a label (hard delete)."""
        label.delete()


class TaskLabelService:
    """Business logic for the Task<->Label many-to-many link."""

    @staticmethod
    def get_task_labels(organization):
        """Return every task-label link in the organization, with task/label pre-fetched."""
        return TaskLabel.objects.filter(
            task__project__organization=organization
        ).select_related(
            'task',
            'label'
        )

    @staticmethod
    def create_task_label(serializer,organization):
        """
        Attach a label to a task, after confirming both the task and the
        label actually belong to the active organization - guards against
        a client passing a valid-looking task/label id that belongs to a
        different tenant entirely.
        """
        task=serializer.validated_data['task']
        label=serializer.validated_data['label']
        if task.project.organization!=organization:
            raise ValueError('Invalid task.')
        if label.organization!=organization:
            raise ValueError('Invalid label.')

        serializer.save()

    @staticmethod
    def get_task_label(pk,organization):
        """Return a single task-label link scoped to the organization, or 404."""
        return get_object_or_404(
            TaskLabel,
            id=pk,
            task__project__organization=organization,
        )

    @staticmethod
    def update_task_label(task_label,validated_data):
        """Apply field changes to an existing task-label link and save."""
        for key, value in validated_data.items():
            setattr(task_label,key,value)
        task_label.save()
        return task_label

    @staticmethod
    def delete_task_label(task_label):
        """Remove a label from a task (hard delete of the link row)."""
        task_label.delete()


class ActivityLogService:
    """Writes and reads the immutable activity log for tasks."""

    @staticmethod
    def log(
        organization,
        task,
        actor,
        action,
        payload=None,
    ):
        """
        Record one activity log entry. This is the single place every
        significant task mutation (create/update/delete/comment) writes
        through, per the "immutable activity record" requirement - see
        docs/adr/0002-service-layer.md for why this is a plain function
        call from each mutating service method rather than a signal.
        """
        if payload is None:
            payload={}
        ActivityLog.objects.create(
            organization=organization,
            task=task,
            actor=actor,
            action=action,
            payload=payload,
        )

    @staticmethod
    def get_logs(organization):
        """Return an organization's activity feed, with actor/task pre-fetched."""
        return ActivityLog.objects.filter(
            organization=organization
        ).select_related(
            'actor',
            'task'
        )

    @staticmethod
    def get_log(pk,organization):
        """Return a single activity log entry scoped to the organization, or 404."""
        return get_object_or_404(
            ActivityLog,
            id=pk,
            organization=organization,
        )


class NotificationService:
    """Creates and reads per-user task notifications."""

    @staticmethod
    def create_notification(
        user,
        task,
        notification_type,
        title,
        body,
    ):
        """Create one notification for a user about a task."""
        return Notification.objects.create(
            user=user,
            task=task,
            type=notification_type,
            title=title,
            body=body,
        )

    @staticmethod
    def get_notifications(user,organization):
        """Return a user's notifications within the organization, with task pre-fetched."""
        return Notification.objects.filter(
            user=user,
            task__project__organization=organization,
        ).select_related(
        'task'
        ).order_by('created_at', 'id')

    @staticmethod
    def get_notification(pk,user,organization):
        """Return a single notification scoped to the user and organization, or 404."""
        return get_object_or_404(
            Notification,
            id=pk,
            user=user,
            task__project__organization=organization,
        )

    @staticmethod
    def mark_as_read(notification):
        """Stamp a notification as read with the current time and save."""
        notification.read_at=timezone.now()
        notification.save(update_fields=['read_at'])
        return notification
