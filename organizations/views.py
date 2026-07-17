from rest_framework.response import Response
from rest_framework import status
from .serializers import OrganizationSerializer
from .services import create_organization, list_organizations, get_organization,update_organization, delete_organization
from rest_framework.views import APIView

class OrganizationView(APIView):
    """
    Handle organization creation and listing.
    """
    
    def post(self,request):
        """
        Create a new organization.
        """
    
        serializer=OrganizationSerializer(data=request.data)
        if serializer.is_valid():
            organization=create_organization(serializer.validated_data)
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

    def get(self,request):
        """
        Retrieve all organizations.
        """
        
        organizations=list_organizations()
        serializer=OrganizationSerializer(organizations,many=True)
        return Response(serializer.data)


class OrganizationDetailView(APIView):
    """
    Handle operations on a single organization.
    """
     
    def get(self,request,slug):
        """
        Retrieve a single organization by slug.
        """
        
        organization=get_organization(slug)
        serializer=OrganizationSerializer(organization)
        return Response(serializer.data)
    
    def put(self,request,slug):
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
    
    def delete(self,request,slug):
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
        
        


        