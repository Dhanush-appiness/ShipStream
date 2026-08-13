from django.conf import settings
from django.db import models

from common.managers import AllObjectsManager, ProjectManager
from organizations.models import Organization


class Project(models.Model):
    class StatusChoices(models.TextChoices):
        ACTIVE='ACTIVE','Active'
        ARCHIVED='ARCHIVED','Archived'

    objects=ProjectManager()
    all_objects=AllObjectsManager()

    organization=models.ForeignKey(
        Organization,
        on_delete=models.CASCADE
    )
    name=models.CharField(max_length=255)
    description=models.TextField(blank=True)
    status=models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE,
    )
    is_deleted=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    def delete(self,*args,**kwargs):
        self.is_deleted=True
        self.save(update_fields=['is_deleted'])

    def __str__(self):
        return self.name

    class Meta:
        constraints=[
            models.UniqueConstraint(
                fields=['organization','name'],
                name='unique_project_per_org'
            )
        ]


class ProjectMember(models.Model):
    project=models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='members'
    )
    user=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_memberships'
    )
    joined_at=models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.email}-{self.project.name}'

    class Meta:
        constraints=[
            models.UniqueConstraint(
                fields=['project','user'],
                name='unique_project_member'
            )
        ]


class ExportJob(models.Model):
    class ExportType(models.TextChoices):
        CSV='CSV','CSV'
    class StatusChoices(models.TextChoices):
        Pending='PENDING','Pending'
        Processing='PROCESSING','Processing'
        Completed='COMPLETED','Completed'
        Failed='FAILED','Failed'
    project=models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='export_jobs'
    )
    user=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='export_jobs'
    )
    type=models.CharField(max_length=20,choices=ExportType.choices,default=ExportType.CSV,)
    status=models.CharField(max_length=20,choices=StatusChoices.choices,default=StatusChoices.Pending)
    file_path=models.CharField(max_length=500,null=True,blank=True)
    file_url=models.URLField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    completed_at=models.DateTimeField(null=True,blank=True)
    def __str__(self):
        if self.user:
            return f'{self.user.email}-{self.type}'
        else:
            return f'Deleted User-{self.type}'
