from django.urls import path

from .views import (
                    ActivityLogDetailView,
                    ActivityLogListView,
                    CommentListCreateView,
                    CommentRetrieveUpdateDestroyView,
                    LabelListCreateView,
                    LabelRetrieveUpdateDestroyView,
                    NotificationListView,
                    NotificationReadView,
                    NotificationRetrieveView,
                    TaskDashboardView,
                    TaskLabelListCreateView,
                    TaskLabelRetrieveUpdateDestroyView,
                    TaskListCreateView,
                    TaskReorderView,
                    TaskRetrieveUpdateDestroyView,
)

urlpatterns = [
    #Tasks
    path('',TaskListCreateView.as_view(),name='task-list-create',),
    path('dashboard/',TaskDashboardView.as_view(),name='task-dashboard',),
    path('<int:pk>/',TaskRetrieveUpdateDestroyView.as_view(),name='task-detail',),
    path('<int:pk>/reorder/',TaskReorderView.as_view(),name='task-reorder',),
    #Comments
    path('<int:task_id>/comments/',CommentListCreateView.as_view(),name='comment-list-create',),
    path('comments/<int:pk>/',CommentRetrieveUpdateDestroyView.as_view(),name='comment-detail',),
    #Labels
    path('labels/',LabelListCreateView.as_view(),name='label-list-create',),
    path('labels/<int:pk>/',LabelRetrieveUpdateDestroyView.as_view(),name='label-detail',),
    #Task Labels
    path('task-labels/',TaskLabelListCreateView.as_view(),name='tasklabel-list-create',),
    path('task-labels/<int:pk>/',TaskLabelRetrieveUpdateDestroyView.as_view(),name='tasklabel-detail',),
    #Activity Logs
    path('activity/',ActivityLogListView.as_view(),name='activity-list',),
    path('activity/<int:pk>/',ActivityLogDetailView.as_view(),name='activity-detail',),
    #Notifications
    path('notifications/',NotificationListView.as_view(),name='notification-list',),
    path('notifications/<int:pk>/',NotificationRetrieveView.as_view(),name='notification-detail',),
    path('notifications/<int:pk>/read/',NotificationReadView.as_view(),name='notification-read',),
]
