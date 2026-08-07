import pytest
from rest_framework.test import APIRequestFactory

from .permissions import IsOrganizationAdmin, IsOrganizationMemberOrReadOnly


@pytest.fixture
def request_factory():
    return APIRequestFactory()


@pytest.mark.django_db
def test_guest_can_read(
    request_factory,
    guest,
    organization,
    guest_membership,
):
    request=request_factory.get('/')
    request.user=guest
    request.organization=organization
    permission=IsOrganizationMemberOrReadOnly()
    assert permission.has_permission(request,None) is True


@pytest.mark.django_db
def test_guest_cannot_write(
    request_factory,
    guest,
    organization,
    guest_membership,
):
    request=request_factory.post('/')
    request.user=guest
    request.organization=organization
    permission=IsOrganizationMemberOrReadOnly()
    assert permission.has_permission(request,None) is False


@pytest.mark.django_db
def test_member_can_write(
    request_factory,
    user,
    organization,
    membership,
):
    request=request_factory.post('/')
    request.user=user
    request.organization=organization
    permission=IsOrganizationMemberOrReadOnly()
    assert permission.has_permission(request,None) is True


@pytest.mark.django_db
def test_owner_has_admin_permission(
    request_factory,
    owner,
    organization,
    owner_membership,
):
    request=request_factory.delete('/')
    request.user=owner
    request.organization=organization
    permission=IsOrganizationAdmin()
    assert permission.has_permission(request,None) is True


@pytest.mark.django_db
def test_member_does_not_have_admin_permission(
    request_factory,
    user,
    organization,
    membership,
):
    request=request_factory.delete('/')
    request.user=user
    request.organization=organization

    permission=IsOrganizationAdmin()

    assert permission.has_permission(request,None) is False


@pytest.mark.django_db
def test_cleanup_old_exports_deletes_completed_jobs_past_retention(
    organization,
    project,
    owner,
):
    from datetime import timedelta

    from django.utils import timezone

    from common.tasks import cleanup_old_exports
    from projects.models import ExportJob

    old_job=ExportJob.objects.create(
        project=project,
        user=owner,
        type='CSV',
        status=ExportJob.StatusChoices.Completed,
        completed_at=timezone.now()-timedelta(days=31),
    )

    recent_job=ExportJob.objects.create(
        project=project,
        user=owner,
        type='CSV',
        status=ExportJob.StatusChoices.Completed,
        completed_at=timezone.now()-timedelta(days=1),
    )

    pending_job=ExportJob.objects.create(
        project=project,
        user=owner,
        type='CSV',
        status=ExportJob.StatusChoices.Pending,
    )

    cleanup_old_exports.run()

    assert not ExportJob.objects.filter(id=old_job.id).exists()
    assert ExportJob.objects.filter(id=recent_job.id).exists()
    assert ExportJob.objects.filter(id=pending_job.id).exists()


@pytest.mark.django_db
def test_seed_demo_data_command_is_idempotent():
    from django.core.management import call_command

    from accounts.models import User
    from organizations.models import Membership, Organization
    from projects.models import Project
    from tasks.models import Task

    call_command('seed_demo_data')

    assert Organization.objects.filter(slug='acme-corp').exists()
    assert Organization.objects.filter(slug='globex-inc').exists()
    assert User.objects.filter(email='bob@example.com').count()==1
    assert Membership.objects.filter(user__email='bob@example.com').count()==2

    project_count=Project.objects.count()
    task_count=Task.objects.count()

    call_command('seed_demo_data')

    assert Project.objects.count()==project_count
    assert Task.objects.count()==task_count


@pytest.mark.django_db
def test_seed_demo_data_flush_removes_and_recreates_seeded_data():
    from django.core.management import call_command

    from organizations.models import Organization

    call_command('seed_demo_data')

    original_id=Organization.objects.get(slug='acme-corp').id

    call_command('seed_demo_data',flush=True)

    assert Organization.objects.filter(slug='acme-corp').count()==1
    new_id=Organization.objects.get(slug='acme-corp').id
    assert new_id!=original_id
