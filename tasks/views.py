from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Task
from .serializers import TaskSerializer,CommentSerializer,LabelSerializer,TaskLabelSerializer,ActivityLogSerializer,NotificationSerializer
from .services import TaskService,CommentService,LabelService,TaskLabelService,ActivityLogService,NotificationService
from common.permissions import HasOrganizationAccess


class TaskListCreateView(generics.ListCreateAPIView):
    serializer_class=TaskSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_queryset(self):
        return TaskService.get_tasks(self.request.organization)

    def perform_create(self,serializer):
        TaskService.create_task(
            serializer,
            self.request.user,
            self.request.organization,
        )


class TaskRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class=TaskSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_object(self):
        return TaskService.get_task(
            self.kwargs['pk'],
            self.request.organization,
        )

    def perform_update(self,serializer):
        task=self.get_object()
        TaskService.update_task(
            task,
            serializer.validated_data,
        )

    def perform_destroy(self,instance):
        TaskService.delete_task(instance)



class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class=CommentSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_queryset(self):
        return CommentService.get_comments(
            self.kwargs['task_id'],
            self.request.user,
        )

    def perform_create(self,serializer):
        CommentService.create_comment(
            serializer,
            self.request.user,
        )


class CommentRetrieveUpdateDestroyView(
    generics.RetrieveUpdateDestroyAPIView
):
    serializer_class=CommentSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_object(self):
        return CommentService.get_comment(
            self.kwargs['pk'],
            self.request.user,
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
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_queryset(self):
        return LabelService.get_labels(
            self.request.user
        )

    def perform_create(self, serializer):
        LabelService.create_label(
            serializer,
            self.request.user,
        )


class LabelRetrieveUpdateDestroyView(
    generics.RetrieveUpdateDestroyAPIView
):
    serializer_class=LabelSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_object(self):
        return LabelService.get_label(
            self.kwargs['pk'],
            self.request.user,
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
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_queryset(self):
        return TaskLabelService.get_task_labels(
            self.request.user
        )

    def perform_create(self,serializer):
        TaskLabelService.create_task_label(
            serializer,
            self.request.user,
        )


class TaskLabelRetrieveUpdateDestroyView(
    generics.RetrieveUpdateDestroyAPIView
):
    serializer_class=TaskLabelSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_object(self):
        return TaskLabelService.get_task_label(
            self.kwargs['pk'],
            self.request.user,
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

    def get_queryset(self):
        return ActivityLogService.get_logs(
            self.request.user
        )


class ActivityLogDetailView(generics.RetrieveAPIView):
    serializer_class=ActivityLogSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_object(self):
        return ActivityLogService.get_log(
            self.kwargs['pk'],
            self.request.user,
        )


class NotificationListView(generics.ListAPIView):
    serializer_class=NotificationSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_queryset(self):
        return NotificationService.get_notifications(
            self.request.user
        )

class NotificationRetrieveView(generics.RetrieveAPIView):
    serializer_class=NotificationSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_object(self):
        return NotificationService.get_notification(
            self.kwargs['pk'],
            self.request.user,
        )


class NotificationReadView(generics.UpdateAPIView):
    serializer_class=NotificationSerializer
    permission_classes=[IsAuthenticated,HasOrganizationAccess]

    def get_object(self):
        return NotificationService.get_notification(
            self.kwargs['pk'],
            self.request.user,
        )

    def update(self, request, *args, **kwargs):
        notification=self.get_object()
        NotificationService.mark_as_read(
            notification
        )
        serializer=self.get_serializer(notification)
        return Response(serializer.data)