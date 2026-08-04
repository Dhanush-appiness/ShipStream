from django.contrib.auth.password_validation import validate_password as django_validate_password
from rest_framework import serializers

from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model=User
        fields=['email','password']
        extra_kwargs={'password':{'write_only':True}}

def validate_password(self,value):
    if len(value)<8:
        raise serializers.ValidationError('Password must be at least 8 characters.')
    return value

class LoginSerializer(serializers.Serializer):
    email=serializers.EmailField()
    password=serializers.CharField(write_only=True)

class LogoutSerializer(serializers.Serializer):
    refresh=serializers.CharField()


class PasswordResetRequestSerializer(serializers.Serializer):
    email=serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token=serializers.CharField(max_length=255)
    new_password=serializers.CharField(min_length=8,write_only=True,validators=[django_validate_password],)
