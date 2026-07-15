from rest_framework import serializers
from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model=User
        fields=['email','password']
        extra_kwargs={'password':{'write_only':True}}

def validate_password(self,value):
    if len(value)<8:
        raise serializers.ValidationError('Password must be more than 8 character!')
    return 