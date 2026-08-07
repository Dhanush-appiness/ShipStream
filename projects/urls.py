from django.urls import path

from .views import (
    ExportJobDownloadView,
    ExportJobListCreateView,
    ExportJobRetrieveView,
    ProjectArchiveView,
    ProjectListCreateView,
    ProjectMemberDeleteView,
    ProjectMemberListCreateView,
    ProjectRestoreView,
    ProjectRetrieveUpdateDestroyView,
)

urlpatterns = [
    path('',ProjectListCreateView.as_view()),
    path('<int:pk>/',ProjectRetrieveUpdateDestroyView.as_view()),
    path('exports/',ExportJobListCreateView.as_view(),name='export-list-create',),
    path('exports/<int:pk>/',ExportJobRetrieveView.as_view(),name='export-detail',),
    path('exports/<int:pk>/download/',ExportJobDownloadView.as_view(),name='export-download',),
    path('<int:pk>/archive/',ProjectArchiveView.as_view(),name='project-archive'),
    path('<int:pk>/restore/',ProjectRestoreView.as_view(),name='project-restore'),
    path('<int:project_id>/members/',ProjectMemberListCreateView.as_view(),name='project-member-list-create'),
    path('<int:project_id>/members/<int:user_id>/',ProjectMemberDeleteView.as_view(),name='project-member-detail'),
]
