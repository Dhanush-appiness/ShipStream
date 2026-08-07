from rest_framework import serializers

from .models import ExportJob, Project, ProjectMember


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model=Project
        fields='__all__'
        read_only_fields=('id','organization','is_deleted','created_at','updated_at')

class ExportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model=ExportJob
        fields=['id','project','user','type','status','file_url','created_at','completed_at']
        read_only_fields=('id','user','status','file_url','created_at','completed_at',)

class ProjectMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model=ProjectMember
        fields='__all__'
        read_only_fields=('id','project','joined_at',)
