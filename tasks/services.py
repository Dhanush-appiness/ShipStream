from django.shortcuts import get_object_or_404
from .models import Task,Comment,Label,TaskLabel,ActivityLog,Notification
from projects.models import ExportJob
from organizations.models import Membership
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

class TaskService:
    @staticmethod
    def broadcast_task_update(task, action):
        print(f"Broadcasting {action} for task {task.id}")
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
    def get_user_organization(user):
        membership=Membership.objects.filter(user=user).select_related('organization').first()
        if not membership:
            raise ValueError('User does not belong to any organization.')
        return membership.organization

    @staticmethod
    def get_tasks(organization):
        return Task.objects.filter(
            project__organization=organization,
            is_deleted=False,
        ).select_related(
            'project',
            'assignee',
            'created_by',
        )

    @staticmethod
    def get_task(task_id,organization):
        return get_object_or_404(
            Task,
            id=task_id,
            project__organization=organization,
            is_deleted=False,
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
        task.is_deleted=True
        task.save(update_fields=['is_deleted'])
        ActivityLogService.log(
            task.project.organization,
            task,
            task.created_by,
            'TASK_DELETED',
        )
        TaskService.broadcast_task_update(task, "deleted")
        
        
        
class CommentService:

    @staticmethod
    def get_comments(task_id, user):
        organization=TaskService.get_user_organization(user)
        return Comment.objects.filter(
            task__id=task_id,
            task__project__organization=organization,
        )

    @staticmethod
    def create_comment(serializer, user):
        task=serializer.validated_data['task']
        organization=TaskService.get_user_organization(user)
        if task.project.organization!=organization:
            raise ValueError("Cannot comment on another organization's task.")
        serializer.save(author=user)
        ActivityLogService.log(
            organization,
            task,
            user,
            'COMMENT_ADDED',
        )

    @staticmethod
    def get_comment(comment_id, user):
        organization=TaskService.get_user_organization(user)
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
    def get_labels(user):
        organization=TaskService.get_user_organization(user)
        return Label.objects.filter(
            organization=organization
        )

    @staticmethod
    def create_label(serializer,user):
        organization=TaskService.get_user_organization(user)
        serializer.save(
            organization=organization
        )

    @staticmethod
    def get_label(label_id,user):
        organization=TaskService.get_user_organization(user)
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
    def get_task_labels(user):
        organization=TaskService.get_user_organization(user)

        return TaskLabel.objects.filter(
            task__project__organization=organization
        ).select_related(
            'task',
            'label'
        )

    @staticmethod
    def create_task_label(serializer, user):
        organization=TaskService.get_user_organization(user)
        task=serializer.validated_data['task']
        label=serializer.validated_data['label']
        if task.project.organization!=organization:
            raise ValueError('Invalid task.')
        if label.organization!=organization:
            raise ValueError('Invalid label.')

        serializer.save()

    @staticmethod
    def get_task_label(pk,user):
        organization=TaskService.get_user_organization(user)
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
    def get_logs(user):
        organization=TaskService.get_user_organization(user)
        return ActivityLog.objects.filter(
            organization=organization
        ).select_related(
            'actor',
            'task'
        )

    @staticmethod
    def get_log(pk,user):
        organization=TaskService.get_user_organization(user)
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
    def get_notifications(user):
        return Notification.objects.filter(
            user=user
        ).select_related(
            'task'
        )

    @staticmethod
    def get_notification(pk, user):
        return get_object_or_404(
            Notification,
            id=pk,
            user=user,
        )

    @staticmethod
    def mark_as_read(notification):
        from django.utils import timezone
        notification.read_at=timezone.now()
        notification.save(update_fields=['read_at'])
        return notification


class ExportJobService:

    @staticmethod
    def get_jobs(user):
        organization=TaskService.get_user_organization(user)
        return ExportJob.objects.filter(
            organization=organization
        )

    @staticmethod
    def get_job(pk,user):
        organization=TaskService.get_user_organization(user)
        return get_object_or_404(
            ExportJob,
            id=pk,
            organization=organization,
        )

    @staticmethod
    def create_job(serializer, user):
        organization=TaskService.get_user_organization(user)
        serializer.save(
            organization=organization,
            requested_by=user,
            status='PENDING',
        )