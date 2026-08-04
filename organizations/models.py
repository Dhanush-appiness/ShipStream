from django.conf import settings
from django.db import models


class Organization(models.Model):
    name=models.CharField(max_length=255)
    slug=models.SlugField(unique=True)
    plan=models.CharField(max_length=20, default='free')
    is_active=models.BooleanField(default=True,db_index=True)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.name

class Membership(models.Model):
    class RoleChoices(models.TextChoices):
        OWNER='OWNER','Owner'
        ADMIN='ADMIN','Admin'
        MEMBER='MEMBER','Member'
        GUEST='GUEST','Guest'
    user=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    organization=models.ForeignKey(
        Organization,
        on_delete=models.CASCADE
    )
    role=models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.MEMBER
    )
    joined_at=models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.email}-{self.organization.name}'
    class Meta:
        constraints=[
            models.UniqueConstraint(
                fields=['user','organization'],
                name='unique_user_organization'
            )
        ]

class Invitation(models.Model):
    class RoleChoices(models.TextChoices):
        OWNER='OWNER','Owner'
        ADMIN='ADMIN','Admin'
        MEMBER='MEMBER','Member'
        GUEST='GUEST','Guest'
    class StatusChoices(models.TextChoices):
        PENDING='PENDING','Pending'
        ACCEPTED='ACCEPTED','Accepted'
        EXPIRED='EXPIRED','Expired'
    organization=models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invitation"
    )
    invited_by=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='invitation'
    )
    email=models.EmailField()
    token=models.CharField(max_length=255,unique=True)
    role=models.CharField(max_length=20,choices=RoleChoices.choices,default=RoleChoices.MEMBER)
    status=models.CharField(max_length=20,choices=StatusChoices.choices,default=StatusChoices.PENDING,db_index=True)
    expires_at=models.DateTimeField()
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.email
