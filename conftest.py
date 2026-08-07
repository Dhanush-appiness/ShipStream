import pytest
from rest_framework.test import APIClient

from accounts.factories import UserFactory
from organizations.factories import MembershipFactory, OrganizationFactory
from organizations.models import Membership
from projects.factories import ProjectFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return UserFactory(email='member@example.com')


@pytest.fixture
def owner(db):
    return UserFactory(email='owner@example.com')


@pytest.fixture
def guest(db):
    return UserFactory(email='guest@example.com')


@pytest.fixture
def organization(db):
    return OrganizationFactory(
        name='Test Organization',
        slug='test-organization'
    )


@pytest.fixture
def membership(user,organization):
    return MembershipFactory(
        user=user,
        organization=organization,
        role=Membership.RoleChoices.MEMBER
    )


@pytest.fixture
def owner_membership(owner,organization):
    return MembershipFactory(
        user=owner,
        organization=organization,
        role=Membership.RoleChoices.OWNER
    )


@pytest.fixture
def guest_membership(guest,organization):
    return MembershipFactory(
        user=guest,
        organization=organization,
        role=Membership.RoleChoices.GUEST
    )


@pytest.fixture
def authenticated_client(api_client,user,membership,organization):
    api_client.force_authenticate(user=user)
    api_client.credentials(
        HTTP_X_ORG_ID=str(organization.id)
    )
    return api_client

@pytest.fixture
def project(organization):
    return ProjectFactory(
        organization=organization,
        name='Test Project',
        description='Test project description',
    )
