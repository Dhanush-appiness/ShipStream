from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Project,ExportJob
from .serializers import ProjectSerializer,ExportJobSerializer
from .services import ProjectService,ExportJobService
from common.permissions import HasOrganizationAccess
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page


@method_decorator(cache_page(60), name='dispatch')
class ProjectListCreateView(generics.ListCreateAPIView):
    serializer_class=ProjectSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_queryset(self):
        return ProjectService.get_projects(self.request.organization)

    def perform_create(self,serializer):
        project=ProjectService.create_project(
            organization=self.request.organization,
            validated_data=serializer.validated_data
        )
        serializer.instance=project

class ProjectRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class=ProjectSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_object(self):
        return ProjectService.get_project(
            self.request.organization,
            self.kwargs['pk']
        )

    def perform_update(self,serializer):
        project=ProjectService.update_project(
            organization=self.request.organization,
            project_id=self.kwargs['pk'],
            validated_data=serializer.validated_data
        )
        serializer.instance = project

    def perform_destroy(self,instance):
        ProjectService.delete_project(
            organization=self.request.organization,
            project_id=self.kwargs['pk']
        )


class ExportJobListCreateView(generics.ListCreateAPIView):
    serializer_class=ExportJobSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_queryset(self):
        return ExportJobService.get_jobs(
            self.request.organization,
        )

    def perform_create(self, serializer):
        job=ExportJobService.create_job(
            self.request.user,
            self.request.organization,
            serializer.validated_data,
        )
        serializer.instance=job

class ExportJobRetrieveView(generics.RetrieveAPIView):
    serializer_class=ExportJobSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_object(self):
        return ExportJobService.get_job(
            self.request.organization,
            self.kwargs['pk'],
        )
