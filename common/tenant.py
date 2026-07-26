from django.shortcuts import get_object_or_404
from organizations.models import Membership


def get_current_organization(user,org_id):
    membership=get_object_or_404(
        Membership.objects.select_related('organization'),
        user=user,
        organization_id=org_id,
    )
    return membership.organization