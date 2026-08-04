from .base import *  # noqa: F403

DEBUG=False

ALLOWED_HOSTS=[
    'testserver',
    'localhost',
    '127.0.0.1',
]

CACHES={
    'default':{
        'BACKEND':'django.core.cache.backends.locmem.LocMemCache',
    }
}

EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'

CELERY_TASK_ALWAYS_EAGER=True
CELERY_TASK_EAGER_PROPAGATES=True

DEFAULT_FROM_EMAIL='noreply@shipstream.test'
FRONTEND_URL='http://testserver'
