from rest_framework.exceptions import PermissionDenied

from organizations.models import Membership


class TenantMixin:
    """
    Resolves the current tenant after DRF authentication.
    """

    def get_organization(self):
        org_id=self.request.headers.get('X-Org-ID')
        if not org_id:
            raise PermissionDenied('X-Org-ID header is required.')
        membership = (
            Membership.objects
            .select_related('organization')
            .filter(
                user=self.request.user,
                organization_id=org_id,
            )
            .first()
        )
        if not membership:
            raise PermissionDenied(
                'You are not a member of this organization.'
            )
        return membership.organization
