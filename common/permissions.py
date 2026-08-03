from rest_framework.permissions import SAFE_METHODS, BasePermission

from organizations.models import Membership


class HasOrganizationAccess(BasePermission):
    def has_permission(self,request,view):
        if not request.user.is_authenticated:
            return False
        organization=getattr(request,'organization',None)
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
        organization=getattr(request,'organization',None)
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
        organization=getattr(request,'organization',None)
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
