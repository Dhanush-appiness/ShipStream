from rest_framework.request import Request

from organizations.models import Organization


class OrganizationRequest(Request):
    organization: Organization | None
