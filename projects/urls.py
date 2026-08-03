from django.urls import path

from .views import (
    ExportJobListCreateView,
    ExportJobRetrieveView,
    ProjectArchiveView,
    ProjectListCreateView,
    ProjectRetrieveUpdateDestroyView,
)

urlpatterns = [
    path('',ProjectListCreateView.as_view()),
    path('<int:pk>/',ProjectRetrieveUpdateDestroyView.as_view()),
    path('exports/',ExportJobListCreateView.as_view(),name='export-list-create',),
    path('exports/<int:pk>/',ExportJobRetrieveView.as_view(),name='export-detail',),
    path('<int:pk>/archive/',ProjectArchiveView.as_view(),name='project-archive'),
]
