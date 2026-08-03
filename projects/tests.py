import pytest
from django.http import Http404

from accounts.models import User
from organizations.models import Organization

from .models import Project
from .services import ProjectService


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
