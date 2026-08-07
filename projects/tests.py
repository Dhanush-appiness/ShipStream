import pytest
from django.http import Http404
from django.urls import reverse

from accounts.models import User
from organizations.models import Organization

from .models import ExportJob, Project, ProjectMember
from .services import ProjectService


@pytest.mark.django_db
def test_create_project_logs_and_reraises_on_failure(organization):
    from unittest.mock import patch

    with patch(
        'projects.services.Project.objects.create',
        side_effect=RuntimeError('boom'),
    ):
        with pytest.raises(RuntimeError,match='boom'):
            ProjectService.create_project(
                organization,
                {'name':'Will Fail'},
            )


@pytest.fixture
def second_organization(db):
    return Organization.objects.create(
        name='Second Organization',
        slug='second-organization'
    )


@pytest.fixture
def project(organization):
    return Project.objects.create(
        organization=organization,
        name='Test Project',
        description='Test project description'
    )


@pytest.fixture
def second_project(second_organization):
    return Project.objects.create(
        organization=second_organization,
        name='Second Project',
        description='Second organization project'
    )


@pytest.mark.django_db
def test_project_tenant_isolation(
    organization,
    second_organization,
    project,
    second_project,
):
    projects=ProjectService.get_projects(organization)

    assert project in projects
    assert second_project not in projects


@pytest.mark.django_db
def test_cannot_access_project_from_another_organization(
    organization,
    second_project,
):
    with pytest.raises(Http404):
        ProjectService.get_project(
            organization,
            second_project.id
        )


@pytest.mark.django_db
def test_project_soft_delete(
    organization,
    project,
):
    ProjectService.delete_project(
        organization,
        project.id
    )

    assert not Project.objects.filter(
        id=project.id
    ).exists()

    assert Project.all_objects.filter(
        id=project.id
    ).exists()


@pytest.mark.django_db
def test_project_update_endpoint_ignores_is_deleted_field(
    authenticated_client,
    project,
):
    response=authenticated_client.put(
        f'/api/v1/projects/{project.id}/',
        {'name':project.name,'is_deleted':True},
        format='json',
    )

    assert response.status_code==200
    project.refresh_from_db()
    assert project.is_deleted is False


@pytest.mark.django_db
def test_project_member_must_belong_to_organization(
    organization,
    project,
):
    from .services import ProjectMemberService

    outsider=User.objects.create_user(
        email='outsider@example.com',
        password='testpass123'
    )

    with pytest.raises(
        ValueError,
        match='User must belong to the organization.'
    ):
        ProjectMemberService.add_member(
            organization,
            project.id,
            outsider
        )


@pytest.mark.django_db
def test_generate_export_includes_all_project_tasks(
    organization,
    project,
    owner,
):
    from tasks.models import Task

    from .tasks import generate_export

    Task.objects.create(
        project=project,
        created_by=owner,
        title='Task One',
        status='TODO',
    )
    Task.objects.create(
        project=project,
        created_by=owner,
        title='Task Two',
        status='DONE',
    )

    job=ExportJob.objects.create(
        project=project,
        user=owner,
        type='CSV',
    )

    generate_export.run(job.id)

    job.refresh_from_db()

    assert job.status==ExportJob.StatusChoices.Completed
    assert job.file_path is not None

    with open(job.file_path) as csvfile:
        content=csvfile.read()

    assert 'Task One' in content
    assert 'Task Two' in content


@pytest.mark.django_db
def test_generate_export_is_idempotent_when_already_completed(
    organization,
    project,
    owner,
):
    from .tasks import generate_export

    job=ExportJob.objects.create(
        project=project,
        user=owner,
        type='CSV',
        status=ExportJob.StatusChoices.Completed,
        file_url='/api/v1/projects/exports/1/download/',
    )

    result=generate_export.run(job.id)

    assert result==job.file_url


@pytest.mark.django_db
def test_export_create_returns_202(
    authenticated_client,
    project,
):
    from unittest.mock import patch

    with patch('projects.services.generate_export.delay') as mock_delay:
        response=authenticated_client.post(
            reverse('export-list-create',kwargs={'version':'v1'}),
            {'project':project.id,'type':'CSV'},
            format='json',
        )

    assert response.status_code==202
    mock_delay.assert_called_once()


@pytest.mark.django_db
def test_export_download_not_ready_returns_409(
    authenticated_client,
    project,
    user,
):
    job=ExportJob.objects.create(
        project=project,
        user=user,
        type='CSV',
    )

    response=authenticated_client.get(
        reverse('export-download',kwargs={'version':'v1','pk':job.id})
    )

    assert response.status_code==409


@pytest.mark.django_db
def test_add_project_member_endpoint(authenticated_client,project,user):
    response=authenticated_client.post(
        reverse(
            'project-member-list-create',
            kwargs={'version':'v1','project_id':project.id},
        ),
        {'user':user.id},
        format='json',
    )

    assert response.status_code==201
    assert ProjectMember.objects.filter(project=project,user=user).exists()


@pytest.mark.django_db
def test_list_project_members_endpoint(authenticated_client,project,user):
    ProjectMember.objects.create(project=project,user=user)

    response=authenticated_client.get(
        reverse(
            'project-member-list-create',
            kwargs={'version':'v1','project_id':project.id},
        ),
    )

    assert response.status_code==200
    assert len(response.data['results'])==1


@pytest.mark.django_db
def test_remove_project_member_endpoint(authenticated_client,project,user):
    ProjectMember.objects.create(project=project,user=user)

    response=authenticated_client.delete(
        reverse(
            'project-member-detail',
            kwargs={'version':'v1','project_id':project.id,'user_id':user.id},
        ),
    )

    assert response.status_code==204
    assert not ProjectMember.objects.filter(project=project,user=user).exists()


@pytest.mark.django_db
def test_owner_can_restore_soft_deleted_project(
    api_client,
    owner,
    organization,
    owner_membership,
    project,
):
    project.delete()

    api_client.force_authenticate(user=owner)
    api_client.credentials(HTTP_X_ORG_ID=str(organization.id))

    response=api_client.put(
        reverse('project-restore',kwargs={'version':'v1','pk':project.id}),
        {'name':project.name},
        format='json',
    )

    assert response.status_code==200
    project.refresh_from_db()
    assert project.is_deleted is False


@pytest.mark.django_db
def test_member_cannot_restore_soft_deleted_project(
    api_client,
    user,
    organization,
    membership,
    project,
):
    project.delete()

    api_client.force_authenticate(user=user)
    api_client.credentials(HTTP_X_ORG_ID=str(organization.id))

    response=api_client.put(
        reverse('project-restore',kwargs={'version':'v1','pk':project.id}),
        {'name':project.name},
        format='json',
    )

    assert response.status_code==403
