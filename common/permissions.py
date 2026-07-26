from rest_framework.permissions import BasePermission


class HasOrganizationAccess(BasePermission):
    """
    Requires the authenticated user to supply X-Org-ID.
    The resolved organization is attached to request.organization.
    """

    def has_permission(self,request,view):
        from common.tenant import get_current_organization
        org_id = request.headers.get("X-Org-ID")
        if not org_id:
            return False
        try:
            request.organization=get_current_organization(
                request.user,
                org_id,
            )
            return True
        except Exception:
            return False