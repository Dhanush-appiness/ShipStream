from rest_framework import serializers
from .models import Project,ExportJob

class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model=Project
        fields='__all__'
        read_only_fields=('id','organization','created_at','updated_at')
class ExportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model=ExportJob
        fields='__all__'
        read_only_fields=('id','user','status','file_url','created_at','completed_at',)