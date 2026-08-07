from django.urls import path

from .views import (
    InvitationAcceptView,
    InvitationCreateView,
    OrganizationDetailView,
    OrganizationView,
    current_tenant,
)

urlpatterns=[
    path('create/',OrganizationView.as_view(),name='create-organization'),
    path('',OrganizationView.as_view(),name='list-organizations'),
    path('me/current/',current_tenant,name='current-tenant'),
    path('invitations/',InvitationCreateView.as_view(),name='create-invitation'),
    path('invitations/accept/',InvitationAcceptView.as_view(),name='accept-invitation'),
    path('<slug:slug>/',OrganizationDetailView.as_view(),name='retrieve-organization'),

]
