from organizations.models import Organization, Membership


class TenantMiddleware:
    def __init__(self,get_response):
        self.get_response=get_response

    def __call__(self,request):
        request.organization=None
        if request.user.is_authenticated:
            org_id=request.headers.get('X-Org-ID')
            if org_id:
                membership=(
                    Membership.objects
                    .select_related('organization')
                    .filter(
                        user=request.user,
                        organization_id=org_id,
                    )
                    .first()
                )
                if membership:
                    request.organization=membership.organization
        return self.get_response(request)