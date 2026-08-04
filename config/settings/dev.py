from .base import *  # noqa: F403

DEBUG=True

ALLOWED_HOSTS=[
    'localhost',
    '127.0.0.1',
]

EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL='noreply@shipstream.local'
FRONTEND_URL='http://localhost:3000'
