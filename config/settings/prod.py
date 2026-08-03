import os

from .base import *  # noqa: F403

DEBUG=False

ALLOWED_HOSTS=[
    host.strip()
    for host in os.getenv('ALLOWED_HOSTS','').split(',')
    if host.strip()
]

SECURE_CONTENT_TYPE_NOSNIFF=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
