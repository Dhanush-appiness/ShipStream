from rest_framework.response import Response
from rest_framework import status
from .serializers import OrganizationSerializer
from .services import create_organization, list_organizations, get_organization,update_organization, delete_organization
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import GenericAPIView
from .pagination import OrganizationPagination
from .filters import OrganizationFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

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
        
        queryset=list_organizations()
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
        
        organization=get_organization(slug)
        serializer=OrganizationSerializer(organization)
        return Response(serializer.data)
    
    def put(self,request,slug,*args,**kwargs):
        """
        Update the organization
        """
        organization=get_organization(slug)
        serializer=OrganizationSerializer(organization,data=request.data)
        if serializer.is_valid():
            updated_organization=update_organization(
                slug,
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
        delete_organization(slug)
        return Response(
            {
                'message':'Organization deleted successfully'
            },
            status=status.HTTP_200_OK
        )
        
        


        