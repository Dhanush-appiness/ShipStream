from django.urls import path
from .views import OrganizationView,OrganizationDetailView,current_tenant

urlpatterns=[
    path('create/',OrganizationView.as_view(),name='create-organization'),
    path('',OrganizationView.as_view(),name='list-organizations'),
    path('<slug:slug>/',OrganizationDetailView.as_view(),name='retrieve-organization'),
]