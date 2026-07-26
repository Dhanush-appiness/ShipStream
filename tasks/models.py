from django.db import models
from django.conf import settings
from projects.models import Project
from organizations.models import Organization

class Task(models.Model):
    project=models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='tasks'
    )
    assignee=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks'
    )
    created_by=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tasks'
    )
    title=models.CharField(max_length=255)
    description=models.TextField(blank=True)
    STATUS_CHOICES=[
        ('TODO','To Do'),
        ('IN_PROGRESS','In Progress'),
        ('DONE','Done')
    ]
    status=models.CharField(max_length=20,choices=STATUS_CHOICES,default='TODO')
    PRIORITY_CHOICES=[
    ('LOW','Low'),
    ('MEDIUM','Medium'),
    ('HIGH','High'),
]
    priority=models.CharField(max_length=20,choices=PRIORITY_CHOICES,default='MEDIUM')
    is_deleted=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    due_date=models.DateField(null=True,blank=True)
    
    def __str__(self):
        return self.title


class Comment(models.Model):
    task=models.ForeignKey(
        Task,
        on_delete=models.CASCADE
    )
    author=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='Comments'
    )
    content=models.TextField()
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.content[:50]
    
class Label(models.Model):
    organization=models.ForeignKey(
        Organization,
        on_delete=models.CASCADE
    )
    name=models.CharField(max_length=7,default='#808080')
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.name
    class Meta:
        constraints=[
            models.UniqueConstraint(
                fields=['organization','name'],
                name='unique_label_per_org'
            )
        ]

class TaskLabel(models.Model):
    task=models.ForeignKey(
        Task,
        on_delete=models.CASCADE
    )
    label=models.ForeignKey(
        Label,
        on_delete=models.CASCADE
    )
    class Meta:
        constraints=[
            models.UniqueConstraint(
                fields=['task','label'],
                name='unique_task_label'
            )
        ]
    def __str__(self):
        return f'{self.task} - {self.label}' 
        
class ActivityLog(models.Model):
    organization=models.ForeignKey(
        Organization,
        on_delete=models.CASCADE
    )
    task=models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='activity_logs',
    )
    actor=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='activity_logs'
    )
    action=models.CharField(max_length=100)
    payload=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f'{self.actor} - {self.action}'
    
class Notification(models.Model):
    user=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    task=models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    type=models.CharField(max_length=50)
    title=models.CharField(max_length=255)
    body=models.TextField()
    read_at=models.DateTimeField(blank=True,null=True)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.title
