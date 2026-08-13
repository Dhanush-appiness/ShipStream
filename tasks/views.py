from typing import cast

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import (
    HasOrganizationAccess,
    IsOrganizationAdmin,
    IsOrganizationMemberOrReadOnly,
)
from common.types import OrganizationRequest

from .filters import TaskFilter
from .pagination import ActivityCursorPagination
from .serializers import (
    ActivityLogSerializer,
    CommentSerializer,
    LabelSerializer,
    NotificationSerializer,
    TaskLabelSerializer,
    TaskReorderSerializer,
    TaskSerializer,
)
from .services import (
    ActivityLogService,
    CommentService,
    LabelService,
    NotificationService,
    TaskLabelService,
    TaskService,
)


class TaskListCreateView(generics.ListCreateAPIView):
    serializer_class=TaskSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess,IsOrganizationMemberOrReadOnly,]
    filter_backends=[DjangoFilterBackend,OrderingFilter]
    filterset_class=TaskFilter
    ordering_fields=['created_at','due_date','priority','position','status']

    def get_queryset(self):
        query=self.request.query_params.get('search')

        if query:
            return TaskService.search_tasks(
                cast(OrganizationRequest,self.request).organization,
                query,
            )

        return TaskService.get_tasks(
            cast(OrganizationRequest,self.request).organization
        )

    def perform_create(self,serializer):
        TaskService.create_task(
            serializer,
            self.request.user,
            cast(OrganizationRequest,self.request).organization,
        )


class TaskRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class=TaskSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess,IsOrganizationMemberOrReadOnly,]

    def get_object(self):
        return TaskService.get_task(
            self.kwargs['pk'],
            cast(OrganizationRequest,self.request).organization,
        )

    def perform_update(self,serializer):
        task=self.get_object()
        TaskService.update_task(
            task,
            self.request.user,
            serializer.validated_data,
        )

    def perform_destroy(self,instance):
        TaskService.delete_task(instance,self.request.user,)


class TaskReorderView(APIView):
    permission_classes=[IsAuthenticated,HasOrganizationAccess,IsOrganizationMemberOrReadOnly,]

    def patch(self,request,pk,*args,**kwargs):
        serializer=TaskReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task=TaskService.reorder_task(
            cast(OrganizationRequest,request).organization,
            pk,
            serializer.validated_data['status'],
            serializer.validated_data['position'],
            request.user,
        )

        return Response(
            TaskSerializer(task).data,
            status=status.HTTP_200_OK,
        )


class TaskRestoreView(APIView):
    permission_classes=[IsAuthenticated,HasOrganizationAccess,IsOrganizationAdmin,]

    def patch(self,request,pk,*args,**kwargs):
        task=TaskService.restore_task(
            cast(OrganizationRequest,request).organization,
            pk,
            request.user,
        )

        return Response(
            TaskSerializer(task).data,
            status=status.HTTP_200_OK,
        )

class TaskDashboardView(APIView):
    permission_classes=[
        IsAuthenticated,
        HasOrganizationAccess,
    ]

    def get(self,request,*args,**kwargs):
        dashboard=TaskService.get_dashboard(
            cast(OrganizationRequest,request).organization
        )

        return Response(
            dashboard,
            status=status.HTTP_200_OK,
        )

class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class=CommentSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess,IsOrganizationMemberOrReadOnly,]

    def get_queryset(self):
        return CommentService.get_comments(
            self.kwargs['task_id'],
            cast(OrganizationRequest,self.request).organization,
        )

    def perform_create(self,serializer):
        CommentService.create_comment(
            serializer,
            self.request.user,
            cast(OrganizationRequest,self.request).organization,
        )


class CommentRetrieveUpdateDestroyView(
    generics.RetrieveUpdateDestroyAPIView
):
    serializer_class=CommentSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess,IsOrganizationMemberOrReadOnly,]

    def get_object(self):
        return CommentService.get_comment(
            self.kwargs['pk'],
            cast(OrganizationRequest,self.request).organization,
        )

    def perform_update(self,serializer):
        comment=self.get_object()
        CommentService.update_comment(
            comment,
            serializer.validated_data,
        )

    def perform_destroy(self,instance):
        CommentService.delete_comment(instance)


class LabelListCreateView(generics.ListCreateAPIView):
    serializer_class=LabelSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess,IsOrganizationMemberOrReadOnly,]

    def get_queryset(self):
        return LabelService.get_labels(
            cast(OrganizationRequest,self.request).organization
        )

    def perform_create(self, serializer):
        LabelService.create_label(
            serializer,
            cast(OrganizationRequest,self.request).organization,
        )


class LabelRetrieveUpdateDestroyView(
    generics.RetrieveUpdateDestroyAPIView
):
    serializer_class=LabelSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess,IsOrganizationMemberOrReadOnly,]

    def get_object(self):
        return LabelService.get_label(
            self.kwargs['pk'],
            cast(OrganizationRequest,self.request).organization,
        )

    def perform_update(self,serializer):
        label=self.get_object()

        LabelService.update_label(
            label,
            serializer.validated_data,
        )

    def perform_destroy(self,instance):
        LabelService.delete_label(instance)


class TaskLabelListCreateView(generics.ListCreateAPIView):
    serializer_class=TaskLabelSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess,IsOrganizationMemberOrReadOnly,]

    def get_queryset(self):
        return TaskLabelService.get_task_labels(
            cast(OrganizationRequest,self.request).organization
        )

    def perform_create(self,serializer):
        TaskLabelService.create_task_label(
            serializer,
            cast(OrganizationRequest,self.request).organization,
        )


class TaskLabelRetrieveUpdateDestroyView(
    generics.RetrieveUpdateDestroyAPIView
):
    serializer_class=TaskLabelSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess,IsOrganizationMemberOrReadOnly,]

    def get_object(self):
        return TaskLabelService.get_task_label(
            self.kwargs['pk'],
            cast(OrganizationRequest,self.request).organization,
        )

    def perform_update(self,serializer):
        obj=self.get_object()
        TaskLabelService.update_task_label(
            obj,
            serializer.validated_data,
        )

    def perform_destroy(self, instance):
        TaskLabelService.delete_task_label(instance)


class ActivityLogListView(generics.ListAPIView):
    serializer_class=ActivityLogSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]
    pagination_class=ActivityCursorPagination

    def get_queryset(self):
        return ActivityLogService.get_logs(
            cast(OrganizationRequest,self.request).organization
        )


class ActivityLogDetailView(generics.RetrieveAPIView):
    serializer_class=ActivityLogSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_object(self):
        return ActivityLogService.get_log(
            self.kwargs['pk'],
            cast(OrganizationRequest,self.request).organization,
        )


class NotificationListView(generics.ListAPIView):
    serializer_class=NotificationSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_queryset(self):
        return NotificationService.get_notifications(
            self.request.user,
            cast(OrganizationRequest,self.request).organization,
        )

class NotificationRetrieveView(generics.RetrieveAPIView):
    serializer_class=NotificationSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_object(self):
        return NotificationService.get_notification(
            self.kwargs['pk'],
            self.request.user,
            cast(OrganizationRequest,self.request).organization,
        )


class NotificationReadView(generics.UpdateAPIView):
    serializer_class=NotificationSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess,IsOrganizationMemberOrReadOnly,]

    def get_object(self):
        return NotificationService.get_notification(
            self.kwargs['pk'],
            self.request.user,
            cast(OrganizationRequest,self.request).organization,
        )

    def update(self, request, *args, **kwargs):
        notification=self.get_object()
        NotificationService.mark_as_read(
            notification
        )
        serializer=self.get_serializer(notification)
        return Response(serializer.data)
