from django.urls import path

from tasks.consumers import TaskConsumer

websocket_urlpatterns=[
    path('ws/projects/<int:project_id>/tasks/',TaskConsumer.as_asgi()),
]
