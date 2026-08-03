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
