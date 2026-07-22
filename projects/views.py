from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Project
from .serializers import ProjectSerializer
from .services import ProjectService


class ProjectListCreateView(generics.ListCreateAPIView):
    serializer_class=ProjectSerializer
    permission_classes=[IsAuthenticated]

    def get_queryset(self):
        return ProjectService.get_projects(self.request.user)

    def perform_create(self,serializer):
        project=ProjectService.create_project(
            user=self.request.user,
            validated_data=serializer.validated_data
        )
        serializer.instance=project

class ProjectRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class=ProjectSerializer
    permission_classes=[IsAuthenticated]

    def get_object(self):
        return ProjectService.get_project(
            self.request.user,
            self.kwargs["pk"]
        )

    def perform_update(self,serializer):
        project=ProjectService.update_project(
            user=self.request.user,
            project_id=self.kwargs["pk"],
            validated_data=serializer.validated_data
        )
        serializer.instance = project

    def perform_destroy(self,instance):
        ProjectService.delete_project(
            user=self.request.user,
            project_id=self.kwargs["pk"]
        )
