import logging
import re

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import connection, transaction
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from organizations.models import Membership

from .models import ActivityLog, Comment, Label, Notification, Task, TaskLabel

logger=logging.getLogger(__name__)

class TaskService:
    @staticmethod
    def broadcast_task_update(task, action):
        logger.info("Broadcasting %s for task %s",action,task.id,)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'tasks',
            {
                'type': 'task_updated',
                'action': action,
                'task_id': task.id,
                'title': task.title,
                'status': task.status,
            },
        )


    @staticmethod
    def get_tasks(organization):
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
    def get_dashboard(organization):
        tasks=Task.objects.for_organization(organization)

        status_counts={
            'TODO':tasks.filter(status='TODO').count(),
            'IN_PROGRESS':tasks.filter(status='IN_PROGRESS').count(),
            'DONE':tasks.filter(status='DONE').count(),
            'BLOCKED':tasks.filter(status='BLOCKED').count(),
        }

        overdue=tasks.filter(
            due_date__lt=timezone.localdate(),
        ).exclude(
            status='DONE',
        ).count()

        workload=list(
            tasks.filter(
                assignee__isnull=False,
            ).exclude(
                status='DONE',
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

        return {
            'status_counts':status_counts,
            'overdue':overdue,
            'workload':workload,
        }

    @staticmethod
    def search_tasks(organization,query):
        tasks=TaskService.get_tasks(organization)

        if not query:
            return tasks

        if connection.vendor!='postgresql':
            return tasks.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query)
            )

        search_vector=SearchVector(
            'title',
            weight='A',
        ) + SearchVector(
            'description',
            weight='B',
        )

        search_query=SearchQuery(query)

        return tasks.annotate(
            search=search_vector,
            rank=SearchRank(
                search_vector,
                search_query,
            ),
        ).filter(
            search=search_query,
        ).order_by(
            '-rank',
            'id',
        )

    @staticmethod
    def get_task(task_id,organization):
        return get_object_or_404(
            Task.objects.for_organization(organization),
            id=task_id,
        )

    @staticmethod
    def create_task(serializer,user,organization):
        project=serializer.validated_data['project']
        if project.organization!=organization:
            raise ValueError("You cannot create tasks in another organization's task.")
        serializer.save(created_by=user)
        ActivityLogService.log(
            organization,
            serializer.instance,
            user,
            'TASK_CREATED',
        )
        task = serializer.instance
        if task.assignee:
            NotificationService.create_notification(
            task.assignee,
            task,
            'TASK_ASSIGNED',
            'New Task Assigned',
            f"You were assigned '{task.title}'.",
            )
        TaskService.broadcast_task_update(task,'created')

    @staticmethod
    def update_task(task,validated_data):
        for key, value in validated_data.items():
            setattr(task, key,value)
        task.save()
        if task.assignee:
            NotificationService.create_notification(
            task.assignee,
            task,
            'TASK_UPDATED',
            'Task Updated',
            f"Task '{task.title}' has been updated.",
        )
        ActivityLogService.log(
            task.project.organization,
            task,
            task.created_by,
            'TASK_UPDATED',
        )
        TaskService.broadcast_task_update(task,'updated')
        return task

    @staticmethod
    def delete_task(task):
        task.delete()
        ActivityLogService.log(
            task.project.organization,
            task,
            task.created_by,
            'TASK_DELETED',
        )
        TaskService.broadcast_task_update(task,'deleted')

    @staticmethod
    @transaction.atomic
    def reorder_task(organization,task_id,status,position):
        task=get_object_or_404(
            Task.objects.for_organization(organization),
            id=task_id,
        )
        old_status=task.status
        old_position=task.position
        if old_status==status:
            if old_position<position:
                Task.objects.filter(
                    project=task.project,
                    status=status,
                    position__gt=old_position,
                    position__lte=position,
                ).update(
                    position=F('position')-1
                )
            elif old_position>position:
                Task.objects.filter(
                    project=task.project,
                    status=status,
                    position__gte=position,
                    position__lt=old_position,
                ).update(
                    position=F('position')+1
                )
        else:
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
        return task



class CommentService:

    @staticmethod
    def get_comments(task_id,organization):
        return Comment.objects.filter(
            task__id=task_id,
            task__project__organization=organization,
        )

    @staticmethod
    def extract_mentions(content):
        return re.findall(
            r'@([\w\.-]+@[\w\.-]+\.\w+)',
            content,
        )

    @staticmethod
    def create_comment(serializer,user,organization):
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
            'COMMENT_ADDED',
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
                'MENTION',
                'You were mentioned in a comment',
                f"{user.email} mentioned you in '{task.title}'.",
            )

            send_mention_notification_email.delay(
                notification.id
            )

    @staticmethod
    def get_comment(comment_id,organization):
        return get_object_or_404(
            Comment,
            id=comment_id,
            task__project__organization=organization,
        )

    @staticmethod
    def update_comment(comment,validated_data):
        for key, value in validated_data.items():
            setattr(comment,key,value)
        comment.save()
        return comment

    @staticmethod
    def delete_comment(comment):
        comment.delete()


class LabelService:

    @staticmethod
    def get_labels(organization):
        return Label.objects.filter(
            organization=organization
        )

    @staticmethod
    def create_label(serializer,organization):
        serializer.save(
            organization=organization
        )

    @staticmethod
    def get_label(label_id,organization):
        return get_object_or_404(
            Label,
            id=label_id,
            organization=organization,
        )

    @staticmethod
    def update_label(label,validated_data):
        for key, value in validated_data.items():
            setattr(label,key,value)
        label.save()
        return label

    @staticmethod
    def delete_label(label):
        label.delete()


class TaskLabelService:

    @staticmethod
    def get_task_labels(organization):

        return TaskLabel.objects.filter(
            task__project__organization=organization
        ).select_related(
            'task',
            'label'
        )

    @staticmethod
    def create_task_label(serializer,organization):
        task=serializer.validated_data['task']
        label=serializer.validated_data['label']
        if task.project.organization!=organization:
            raise ValueError('Invalid task.')
        if label.organization!=organization:
            raise ValueError('Invalid label.')

        serializer.save()

    @staticmethod
    def get_task_label(pk,organization):
        return get_object_or_404(
            TaskLabel,
            id=pk,
            task__project__organization=organization,
        )

    @staticmethod
    def update_task_label(task_label,validated_data):
        for key, value in validated_data.items():
            setattr(task_label,key,value)
        task_label.save()
        return task_label

    @staticmethod
    def delete_task_label(task_label):
        task_label.delete()


class ActivityLogService:

    @staticmethod
    def log(
        organization,
        task,
        actor,
        action,
        payload=None,
    ):
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
        return ActivityLog.objects.filter(
            organization=organization
        ).select_related(
            'actor',
            'task'
        )

    @staticmethod
    def get_log(pk,organization):
        return get_object_or_404(
            ActivityLog,
            id=pk,
            organization=organization,
        )


class NotificationService:

    @staticmethod
    def create_notification(
        user,
        task,
        notification_type,
        title,
        body,
    ):
        return Notification.objects.create(
            user=user,
            task=task,
            type=notification_type,
            title=title,
            body=body,
        )

    @staticmethod
    def get_notifications(user,organization):
        return Notification.objects.filter(
            user=user,
            task__project__organization=organization,
        ).select_related(
            'task'
        )

    @staticmethod
    def get_notification(pk,user,organization):
        return get_object_or_404(
            Notification,
            id=pk,
            user=user,
            task__project__organization=organization,
        )

    @staticmethod
    def mark_as_read(notification):
        from django.utils import timezone
        notification.read_at=timezone.now()
        notification.save(update_fields=['read_at'])
        return notification
