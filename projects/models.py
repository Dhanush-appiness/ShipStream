from django.db import models
from organizations.models import Organization
from django.conf import settings

class Project(models.Model):
    organization=models.ForeignKey(
        Organization,
        on_delete=models.CASCADE
    )
    name=models.CharField(max_length=255)
    description=models.TextField(blank=True)
    status=models.CharField(max_length=20, default='ACTIVE')
    is_deleted=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

def __str__(self):
    return self.name

class Meta:
    constraints=[
        models.UniqueConstraint(
            fields=['organization','name'],
            name='unique_project_per_org'
        )
    ]

class ExportJob(models.Model):
    class ExportType(models.TextChoices):
        CSV='CSV','CSV'
        XML='XML','XML'
        PDF='PDF','PDF'
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
    type=models.CharField(max_length=20,null=True,blank=True)
    status=models.CharField(max_length=20,choices=StatusChoices.choices,default=StatusChoices.Pending)
    file_url=models.URLField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    completed_at=models.DateTimeField(null=True,blank=True)
    def __str__(self):
        if self.user:
            return f'{self.user.email} - {self.type}'
        else:
            return f'Deleted User - {self.type}'
