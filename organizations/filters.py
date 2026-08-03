import django_filters

from .models import Organization


class OrganizationFilter(django_filters.FilterSet):
    class Meta:
        model=Organization
        fields={'name':['exact','icontains'],
               'slug':['exact'],}

