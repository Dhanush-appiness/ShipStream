import os
from typing import cast

from django.http import FileResponse
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import (
    HasOrganizationAccess,
    IsOrganizationAdmin,
    IsOrganizationMemberOrReadOnly,
)
from common.types import OrganizationRequest

from .models import ExportJob
from .serializers import ExportJobSerializer, ProjectMemberSerializer, ProjectSerializer
from .services import ExportJobService, ProjectMemberService, ProjectService


class ProjectListCreateView(generics.ListCreateAPIView):
    serializer_class=ProjectSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess,IsOrganizationMemberOrReadOnly,]

    def get_queryset(self):
        return ProjectService.get_projects(cast(OrganizationRequest,self.request).organization)

    def perform_create(self,serializer):
        project=ProjectService.create_project(
            organization=cast(OrganizationRequest,self.request).organization,
            validated_data=serializer.validated_data
        )
        serializer.instance=project

class ProjectRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class=ProjectSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess,IsOrganizationMemberOrReadOnly,]

    def get_object(self):
        return ProjectService.get_project(
            cast(OrganizationRequest,self.request).organization,
            self.kwargs['pk']
        )

    def perform_update(self,serializer):
        project=ProjectService.update_project(
            organization=cast(OrganizationRequest,self.request).organization,
            project_id=self.kwargs['pk'],
            validated_data=serializer.validated_data
        )
        serializer.instance = project

    def perform_destroy(self,instance):
        ProjectService.delete_project(
            organization=cast(OrganizationRequest,self.request).organization,
            project_id=self.kwargs['pk']
        )


class ExportJobListCreateView(generics.ListCreateAPIView):
    serializer_class=ExportJobSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess,IsOrganizationMemberOrReadOnly,]

    def get_queryset(self):
        return ExportJobService.get_jobs(
            cast(OrganizationRequest,self.request).organization,
        )

    def perform_create(self, serializer):
        job=ExportJobService.create_job(
            self.request.user,
            cast(OrganizationRequest,self.request).organization,
            serializer.validated_data,
        )
        serializer.instance=job

    def create(self,request,*args,**kwargs):
        serializer=self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers=self.get_success_headers(serializer.data)
        return Response(
            serializer.data,
            status=status.HTTP_202_ACCEPTED,
            headers=headers,
        )

class ExportJobRetrieveView(generics.RetrieveAPIView):
    serializer_class=ExportJobSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_object(self):
        return ExportJobService.get_job(
            cast(OrganizationRequest,self.request).organization,
            self.kwargs['pk'],
        )


class ExportJobDownloadView(APIView):
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get(self,request,*args,**kwargs):
        job=ExportJobService.get_job(
            cast(OrganizationRequest,request).organization,
            self.kwargs['pk'],
        )

        if job.status!=ExportJob.StatusChoices.Completed or not job.file_path:
            return Response(
                {'detail':'Export is not ready yet.'},
                status=status.HTTP_409_CONFLICT,
            )

        if not os.path.exists(job.file_path):
            return Response(
                {'detail':'Export file is missing.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return FileResponse(
            open(job.file_path,'rb'),
            as_attachment=True,
            filename=f'export_{job.id}.csv',
        )


class ProjectArchiveView(generics.UpdateAPIView):
    serializer_class=ProjectSerializer
    permission_classes=[
        IsAuthenticated,
        HasOrganizationAccess,
        IsOrganizationAdmin,
    ]

    def update(self,request,*args,**kwargs):
        project=ProjectService.archive_project(
            cast(OrganizationRequest,self.request).organization,
            self.kwargs['pk']
        )
        serializer=self.get_serializer(project)
        return Response(serializer.data)


class ProjectRestoreView(generics.UpdateAPIView):
    serializer_class=ProjectSerializer
    permission_classes=[
        IsAuthenticated,
        HasOrganizationAccess,
        IsOrganizationAdmin,
    ]

    def update(self,request,*args,**kwargs):
        project=ProjectService.restore_project(
            cast(OrganizationRequest,self.request).organization,
            self.kwargs['pk']
        )
        serializer=self.get_serializer(project)
        return Response(serializer.data)


class ProjectMemberListCreateView(generics.ListCreateAPIView):
    serializer_class=ProjectMemberSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess,IsOrganizationMemberOrReadOnly,]

    def get_queryset(self):
        return ProjectMemberService.get_members(
            cast(OrganizationRequest,self.request).organization,
            self.kwargs['project_id'],
        )

    def perform_create(self,serializer):
        try:
            member=ProjectMemberService.add_member(
                cast(OrganizationRequest,self.request).organization,
                self.kwargs['project_id'],
                serializer.validated_data['user'],
            )
        except ValueError as exc:
            raise ValidationError(str(exc))
        serializer.instance=member


class ProjectMemberDeleteView(generics.DestroyAPIView):
    serializer_class=ProjectMemberSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess,IsOrganizationMemberOrReadOnly,]

    def get_object(self):
        return ProjectMemberService.get_member(
            cast(OrganizationRequest,self.request).organization,
            self.kwargs['project_id'],
            self.kwargs['user_id'],
        )

    def perform_destroy(self,instance):
        ProjectMemberService.remove_member(instance)
