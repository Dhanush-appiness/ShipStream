from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from common.permissions import IsOrganizationAdmin

from .filters import OrganizationFilter
from .pagination import OrganizationPagination
from .serializers import (
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    OrganizationSerializer,
)
from .services import (
    accept_invitation,
    create_invitation,
    create_organization,
    delete_organization,
    get_organization,
    list_organizations,
    update_organization,
    user_can_manage_organization,
)


class OrganizationView(GenericAPIView):
    throttle_classes = [UserRateThrottle,AnonRateThrottle]
    """
    Handle organization creation and listing.
    """

    permission_classes=[IsAuthenticated]
    serializer_class=OrganizationSerializer
    pagination_class=OrganizationPagination
    filter_backends=[
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]
    filterset_class=OrganizationFilter
    search_fields=['name',]
    ordering_fields=['name','slug']
    def post(self,request,*args,**kwargs):
        """
        Create a new organization.
        """

        serializer=OrganizationSerializer(data=request.data)
        if serializer.is_valid():
            organization=create_organization(request.user,serializer.validated_data)
            return Response(
                {
                    'message':'Organization created successfully!',
                    'name':organization.name,
                    'slug':organization.slug,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def get(self,request,*args,**kwargs):
        """
        Retrieve all organizations.
        """

        queryset=list_organizations(request.user)
        queryset=self.filter_queryset(queryset)
        page=self.paginate_queryset(queryset)
        if page is not None:
            serializer=self.get_serializer(page,many=True)
            return self.get_paginated_response(serializer.data)
        serializer=self.get_serializer(queryset,many=True)
        return Response(serializer.data)


class OrganizationDetailView(APIView):
    """
    Handle operations on a single organization.
    """

    permission_classes=[IsAuthenticated]
    def get(self,request,slug,*args,**kwargs):
        """
        Retrieve a single organization by slug.
        """

        organization=get_organization(slug,request.user)
        serializer=OrganizationSerializer(organization)
        return Response(serializer.data)

    def put(self,request,slug,*args,**kwargs):
        """
        Update the organization
        """

        organization=get_organization(slug,request.user)
        if not user_can_manage_organization(request.user,organization):
            raise PermissionDenied('Only organization owners and admins can update this organization')
        serializer=OrganizationSerializer(organization,data=request.data)
        if serializer.is_valid():
            updated_organization=update_organization(
                organization,
                serializer.validated_data
            )
            return Response(
                {
                    'message':'Organization updated successfully!',
                    'name':updated_organization.name,
                    'slug':updated_organization.slug,
                },
                status=status.HTTP_200_OK
            )
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self,request,slug,*args,**kwargs):
        """
        Delete the organization
        """

        organization=get_organization(slug,request.user)
        if not user_can_manage_organization(request.user,organization):
            raise PermissionDenied('Only organization owners and admins can delete this organization')
        delete_organization(organization)
        return Response(
            {
                'message':'Organization deleted successfully'
            },
            status=status.HTTP_200_OK
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_tenant(request,*args,**kwargs):
    if request.organization:
        return Response({
            'organization_id':request.organization.id,
            'organization_name':request.organization.name,
        })
    return Response({
        'organization': None
    })

class InvitationCreateView(APIView):
    permission_classes=[IsAuthenticated,IsOrganizationAdmin]
    def post(self,request,*args,**kwargs):
        serializer=InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation=create_invitation(
            request.user,
            request.organization,
            serializer.validated_data,
        )
        return Response(
            {
                'message':'Invitation created successfully',
                'email':invitation.email,
                'role':invitation.role,
            },
            status=status.HTTP_201_CREATED,
        )


class InvitationAcceptView(APIView):
    permission_classes=[IsAuthenticated]
    def post(self,request,*args,**kwargs):
        serializer=InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership=accept_invitation(
        request.user,
        serializer.validated_data,
    )
        return Response(
        {
            'message':'Invitation accepted successfully',
            'organization':membership.organization.name,
            'role':membership.role,
        },
        status=status.HTTP_200_OK,
    )
