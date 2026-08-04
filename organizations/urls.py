from django.urls import path

from .views import (
    InvitationAcceptView,
    InvitationCreateView,
    OrganizationDetailView,
    OrganizationView,
)

urlpatterns=[
    path('create/',OrganizationView.as_view(),name='create-organization'),
    path('',OrganizationView.as_view(),name='list-organizations'),
    path('invitations/',InvitationCreateView.as_view(),name='create-invitation'),
    path('invitations/accept/',InvitationAcceptView.as_view(),name='accept-invitation'),
    path('<slug:slug>/',OrganizationDetailView.as_view(),name='retrieve-organization'),

]
