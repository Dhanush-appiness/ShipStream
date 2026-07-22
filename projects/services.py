from django.shortcuts import get_object_or_404
from organizations.models import Membership
from .models import Project


class ProjectService:
    @staticmethod
    def get_user_organization(user):
        membership=Membership.objects.select_related(
            "organization"
        ).filter(
            user=user
        ).first()
        if membership is None:
            raise ValueError("User is not part of any organization.")
        return membership.organization

    @staticmethod
    def get_projects(user):
        organization=ProjectService.get_user_organization(user)
        return Project.objects.filter(
            organization=organization,
            is_deleted=False
        )

    @staticmethod
    def get_project(user,project_id):
        organization=ProjectService.get_user_organization(user)
        return get_object_or_404(
            Project,
            id=project_id,
            organization=organization,
            is_deleted=False,
        )

    @staticmethod
    def create_project(user,validated_data):
        organization=ProjectService.get_user_organization(user)
        return Project.objects.create(
            organization=organization,
            **validated_data
        )
    
    @staticmethod
    def update_project(user,project_id,validated_data):
        project=ProjectService.get_project(user,project_id)
        for field, value in validated_data.items():
            setattr(project,field,value)
        project.save()
        return project
    
    @staticmethod
    def delete_project(user,project_id):
        project=ProjectService.get_project(user,project_id)
        project.is_deleted=True
        project.save()
        return project