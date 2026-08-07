import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

import config.routing
from common.ws_auth import JWTAuthMiddleware

os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.dev')
django_asgi_app=get_asgi_application()

application=ProtocolTypeRouter(
    {
        'http':django_asgi_app,
        'websocket':JWTAuthMiddleware(
            URLRouter(
                config.routing.websocket_urlpatterns
            )
        ),
    }
)
