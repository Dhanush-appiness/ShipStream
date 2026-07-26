from django.shortcuts import get_object_or_404
from organizations.models import Membership
from .models import Project,ExportJob
from .tasks import generate_export


class ProjectService:
    @staticmethod
    def get_user_organization(user):
        membership=Membership.objects.select_related(
            'organization'
        ).filter(
            user=user
        ).first()
        if membership is None:
            raise ValueError('User is not part of any organization.')
        return membership.organization

    @staticmethod
    def get_projects(organization):
        return Project.objects.filter(
            organization=organization,
            is_deleted=False
        )

    @staticmethod
    def get_project(organization,project_id):
        return get_object_or_404(
            Project,
            id=project_id,
            organization=organization,
            is_deleted=False,
        )

    @staticmethod
    def create_project(organization, validated_data):
        return Project.objects.create(
            organization=organization,
            **validated_data
        )
    
    @staticmethod
    def update_project(organization,project_id,validated_data):
        project=ProjectService.get_project(
            organization,
            project_id
        )
        for field, value in validated_data.items():
            setattr(project,field,value)
        project.save()
        return project
    
    @staticmethod
    def delete_project(organization,project_id):
        project=ProjectService.get_project(
            organization,
            project_id
        )
        project.is_deleted=True
        project.save()
        return project


class ExportJobService:

    @staticmethod
    def get_jobs(organization):
        return ExportJob.objects.filter(
            project__organization=organization
        ).select_related(
            'project',
            'user',
        )

    @staticmethod
    def get_job(organization,job_id):
        return get_object_or_404(
            ExportJob,
            id=job_id,
            project__organization=organization,
        )

    @staticmethod
    def create_job(user,organization,validated_data):
        project=validated_data['project']
        if project.organization!=organization:
            raise ValueError(
                "Cannot export another organization's project."
            )
        job=ExportJob.objects.create(
            user=user,
            status=ExportJob.StatusChoices.Pending,
            **validated_data,
        )
        generate_export.delay(job.id)
        return job