"""
Service layer for project management, project membership, and export jobs.
"""

import logging

from django.shortcuts import get_object_or_404

from organizations.models import Membership

from .models import ExportJob, Project, ProjectMember
from .tasks import generate_export

logger = logging.getLogger(__name__)

# Project status values are defined on the Project model.

class ProjectService:
    """Business logic for creating, mutating, and querying projects."""

    @staticmethod
    def get_projects(organization):
        """Return every non-deleted project belonging to the organization."""
        return Project.objects.for_organization(organization)

    @staticmethod
    def get_project(organization, project_id):
        """Return a single project scoped to the organization, or 404."""
        return get_object_or_404(
            Project.objects.for_organization(organization),
            id=project_id,
        )

    @staticmethod
    def create_project(organization, validated_data):
        """Create a new project under the given organization."""
        try:
            return Project.objects.create(organization=organization, **validated_data)
        except Exception as exc:
            logger.error('Failed to create project for organization %s: %s', organization.id, exc)
            raise

    @staticmethod
    def update_project(organization, project_id, validated_data):
        """Apply field changes to an existing project and save."""
        try:
            project = ProjectService.get_project(organization, project_id)
            for field, value in validated_data.items():
                setattr(project, field, value)
            project.save()
            return project
        except Exception as exc:
            logger.error('Failed to update project %s: %s', project_id, exc)
            raise

    @staticmethod
    def delete_project(organization, project_id):
        """Soft-delete a project (see Project.delete())."""
        try:
            project = ProjectService.get_project(organization, project_id)
            project.delete()
            return project
        except Exception as exc:
            logger.error('Failed to delete project %s: %s', project_id, exc)
            raise

    @staticmethod
    def archive_project(organization, project_id):
        """Mark a project ARCHIVED without soft-deleting it."""
        try:
            project = ProjectService.get_project(organization, project_id)
            project.status=Project.StatusChoices.ARCHIVED
            project.save(update_fields=['status'])
            return project
        except Exception as exc:
            logger.error('Failed to archive project %s: %s', project_id, exc)
            raise

    @staticmethod
    def restore_project(organization, project_id):
        """Restore a soft-deleted project."""

        try:
            project = get_object_or_404(
                Project.all_objects.filter(organization=organization),
                id=project_id,
                is_deleted=True,
            )
            project.is_deleted = False
            project.save(update_fields=['is_deleted'])
            return project
        except Exception as exc:
            logger.error(
                'Failed to restore project %s: %s',
                project_id,
                exc,
            )
            raise


class ProjectMemberService:
    """Business logic for project members."""

    @staticmethod
    def get_members(organization, project_id):
        """Return every member assigned to a project, with user/project pre-fetched."""
        project = ProjectService.get_project(organization, project_id)
        return ProjectMember.objects.filter(project=project).select_related('user','project').order_by('joined_at','id')

    @staticmethod
    def add_member(organization, project_id, user):
        """Assign an organization member to a project."""

        try:
            project = ProjectService.get_project(organization, project_id)

            membership = Membership.objects.filter(
                user=user,
                organization=organization,
            ).exists()

            if not membership:
                raise ValueError('User must belong to the organization.')

            project_member, created = ProjectMember.objects.get_or_create(
                project=project,
                user=user,
            )

            return project_member
        except Exception as exc:
            logger.error('Failed to add member to project %s: %s', project_id, exc)
            raise

    @staticmethod
    def get_member(organization, project_id, user_id):
        """Return a single project-membership row scoped to the organization, or 404."""
        project = ProjectService.get_project(organization, project_id)
        return get_object_or_404(
            ProjectMember,
            project=project,
            user_id=user_id,
        )

    @staticmethod
    def remove_member(project_member):
        """Remove a user from a project (hard delete of the membership row)."""
        project_member.delete()


class ExportJobService:
    """Business logic for requesting and tracking CSV export jobs."""

    @staticmethod
    def get_jobs(organization):
        """Return every export job in the organization, with project/user pre-fetched."""
        return ExportJob.objects.filter(project__organization=organization).select_related(
            'project',
            'user',
        )

    @staticmethod
    def get_job(organization, job_id):
        """Return a single export job scoped to the organization, or 404."""
        return get_object_or_404(
            ExportJob,
            id=job_id,
            project__organization=organization,
        )

    @staticmethod
    def create_job(user, organization, validated_data):
        """Create an export job and queue CSV generation."""

        try:
            project = validated_data['project']
            if project.organization != organization:
                raise ValueError("Cannot export another organization's project.")
            job = ExportJob.objects.create(
                user=user,
                status=ExportJob.StatusChoices.Pending,
                **validated_data,
            )
            generate_export.delay(job.id)
            return job
        except Exception as exc:
            logger.error(
                'Failed to create export job for organization %s: %s', organization.id, exc
            )
            raise
