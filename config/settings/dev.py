import os

from .base import *  # noqa: F403


DEBUG=True

ALLOWED_HOSTS=[
    'localhost',
    '127.0.0.1',
]

EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'

EMAIL_HOST=os.getenv('EMAIL_HOST')
EMAIL_PORT=int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER=os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD=os.getenv('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS=os.getenv('EMAIL_USE_TLS', 'True') == 'True'

DEFAULT_FROM_EMAIL=os.getenv('DEFAULT_FROM_EMAIL')
FRONTEND_URL='http://localhost:3000'
