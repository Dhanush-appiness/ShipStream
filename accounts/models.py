from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

class User(AbstractUser):
    username=None
    email=models.EmailField(unique=True)
    is_verified=models.BooleanField(default=False,db_index=True)
    USERNAME_FIELD='email'
    REQUIRED_FIELDS=[]

class PasswordReset(models.Model):
    user=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_resets'
    )
    token=models.CharField(max_length=255,unique=True)
    expires_at=models.DateTimeField()
    used_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.user.email
    
class RefreshToken(models.Model):
    user=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='refresh_tokens'
    )
    token=models.CharField(max_length=255,unique=True)
    expires_at=models.DateTimeField()
    revoked_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.user.email

