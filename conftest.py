import pytest
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Membership, Organization


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email='member@example.com',
        password='testpass123'
    )


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        email='owner@example.com',
        password='testpass123'
    )


@pytest.fixture
def guest(db):
    return User.objects.create_user(
        email='guest@example.com',
        password='testpass123'
    )


@pytest.fixture
def organization(db):
    return Organization.objects.create(
        name='Test Organization',
        slug='test-organization'
    )


@pytest.fixture
def membership(user,organization):
    return Membership.objects.create(
        user=user,
        organization=organization,
        role=Membership.RoleChoices.MEMBER
    )


@pytest.fixture
def owner_membership(owner,organization):
    return Membership.objects.create(
        user=owner,
        organization=organization,
        role=Membership.RoleChoices.OWNER
    )


@pytest.fixture
def guest_membership(guest,organization):
    return Membership.objects.create(
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
