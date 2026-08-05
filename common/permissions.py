from rest_framework.permissions import SAFE_METHODS, BasePermission

from common.types import OrganizationRequest
from organizations.models import Membership


def get_request_organization(request:OrganizationRequest,):
    organization=getattr(request,'organization',None)
    if organization is not None:
        return organization

    org_id=request.headers.get('X-Org-ID')
    if not org_id or not request.user.is_authenticated:
        return None

    membership=(
        Membership.objects
        .select_related('organization')
        .filter(
            user=request.user,
            organization_id=org_id,
        )
        .first()
    )

    if membership is None:
        return None

    request.organization=membership.organization
    return request.organization


class HasOrganizationAccess(BasePermission):
    def has_permission(self,request,view):
        if not request.user.is_authenticated:
            return False
        organization=get_request_organization(request)
        if organization is None:
            return False
        return Membership.objects.filter(
            user=request.user,
            organization=organization,
        ).exists()


class IsOrganizationMemberOrReadOnly(BasePermission):
    def has_permission(self,request,view):
        if request.method in SAFE_METHODS:
            return True
        organization=get_request_organization(request)
        if organization is None:
            return False
        return Membership.objects.filter(
            user=request.user,
            organization=organization,
            role__in=[
                Membership.RoleChoices.OWNER,
                Membership.RoleChoices.ADMIN,
                Membership.RoleChoices.MEMBER,
            ],
        ).exists()


class IsOrganizationAdmin(BasePermission):
    def has_permission(self,request,view):
        organization=get_request_organization(request)
        if organization is None:
            return False

        return Membership.objects.filter(
            user=request.user,
            organization=organization,
            role__in=[
                Membership.RoleChoices.OWNER,
                Membership.RoleChoices.ADMIN,
            ],
        ).exists()
