"""Service layer for tasks and related operations."""

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

# Dashboard cache lifetime in seconds.
DASHBOARD_CACHE_TTL=300

# Task status values.
STATUS_TODO='TODO'
STATUS_IN_PROGRESS='IN_PROGRESS'
STATUS_DONE='DONE'
STATUS_BLOCKED='BLOCKED'

# ActivityLog.action values written by this service layer.
ACTION_TASK_CREATED='TASK_CREATED'
ACTION_TASK_UPDATED='TASK_UPDATED'
ACTION_TASK_DELETED='TASK_DELETED'
ACTION_COMMENT_ADDED='COMMENT_ADDED'
ACTION_TASK_RESTORED='TASK_RESTORED'
ACTION_TASK_REORDERED='TASK_REORDERED'

# Notification.type values written by this service layer.
NOTIFICATION_TASK_ASSIGNED='TASK_ASSIGNED'
NOTIFICATION_TASK_UPDATED='TASK_UPDATED'
NOTIFICATION_MENTION='MENTION'

# Match @email-style mentions.
MENTION_PATTERN=r'@([\w\.-]+@[\w\.-]+\.\w+)'


class TaskService:
    """Business logic for creating, mutating, and querying tasks."""

    @staticmethod
    def broadcast_task_update(task,action):
        """Broadcast a task update to its project WebSocket group."""

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
        """Return non-deleted tasks for an organization."""

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
        """Clear the dashboard cache for an organization."""

        cache.delete(TaskService.get_dashboard_cache_key(organization))

    @staticmethod
    def get_dashboard(organization):
        """Return dashboard statistics for an organization."""

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
        """Search tasks within an organization."""

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
        """Create a task and handle its side effects."""

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
    def update_task(task,user,validated_data):
        """Update a task and handle its side effects."""

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
                user,
                ACTION_TASK_UPDATED,
            )
            TaskService.broadcast_task_update(task,'updated')
            TaskService.invalidate_dashboard_cache(task.project.organization)
            return task
        except Exception as exc:
            logger.error('Failed to update task %s: %s',task.id,exc)
            raise

    @staticmethod
    def delete_task(task,user):
        """Soft-delete a task and handle its side effects."""

        try:
            task.delete()
            ActivityLogService.log(
                task.project.organization,
                task,
                user,
                ACTION_TASK_DELETED,
            )
            TaskService.broadcast_task_update(task,'deleted')
            TaskService.invalidate_dashboard_cache(task.project.organization)
        except Exception as exc:
            logger.error('Failed to delete task %s: %s',task.id,exc)
            raise

    @staticmethod
    def restore_task(organization,task_id,user):
        """Restore a soft-deleted task."""

        try:
            task=get_object_or_404(
                Task.all_objects.filter(project__organization=organization),
                id=task_id,
                is_deleted=True,
            )
            ActivityLogService.log(
                organization,
                task,
                user,
                ACTION_TASK_RESTORED,
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
    def reorder_task(organization,task_id,status,position,user):
        """Move a task to a different position or status."""

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
            ActivityLogService.log(
                organization,
                task,
                user,
                ACTION_TASK_REORDERED,
                {
                    'old_status':old_status,
                    'new_status':status,
                    'old_position':old_position,
                    'new_position':position,
                },
            )
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
        """Create a comment and notify mentioned users."""

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
        """Attach a label to a task after validating organization ownership."""

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
        """Create an activity log entry."""

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
