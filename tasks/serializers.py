from rest_framework import serializers
from .models import Task,Comment,Label,TaskLabel,ActivityLog,Notification
from projects.models import ExportJob


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model=Task
        fields='__all__'
        read_only_fields=(
            'id',
            'created_by',
            'created_at',
            'updated_at',
            'is_deleted',
        )

class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model=Comment
        fields= '__all__'
        read_only_fields=(
            'id',
            'author',
            'created_at',
            'updated_at',
        )


class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model=Label
        fields='__all__'
        read_only_fields=(
            'id',
            'organization',
            'created_at',
        )
        
        
class TaskLabelSerializer(serializers.ModelSerializer):
    class Meta:
        model=TaskLabel
        fields='__all__'
        
class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model=ActivityLog
        fields='__all__'
        read_only_fields=(
            'id',
            'organization',
            'task',
            'actor',
            'action',
            'payload',
            'created_at',
        )

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model=Notification
        fields='__all__'
        read_only_fields=(
            'id',
            'created_at',
            'user',
        )

class ExportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model=ExportJob
        fields='__all__'
        read_only_fields=(
            'id',
            'organization',
            'requested_by',
            'status',
            'file_url',
            'created_at',
            'completed_at',
        )