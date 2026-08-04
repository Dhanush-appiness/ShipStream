import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import PasswordReset

logger=logging.getLogger(__name__)

@shared_task(bind=True,max_retries=3)
def send_password_reset_email(self,password_reset_id):
    try:
        password_reset=PasswordReset.objects.get(id=password_reset_id)

        if password_reset.used_at is not None:
            return

        if password_reset.expires_at<=timezone.now():
            return

        reset_link=f'{settings.FRONTEND_URL}/password-reset/confirm?token={password_reset.token}'

        send_mail(
            subject='Reset your ShipStream password',
            message=(
                'A password reset was requested for your ShipStream account.\n\n'
                f'Reset your password here:\n{reset_link}'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[password_reset.user.email],
            fail_silently=False,
        )

        logger.info(
            f'Password reset email sent to {password_reset.user.email}'
        )

    except PasswordReset.DoesNotExist:
        logger.warning(
            f'Password reset {password_reset_id} does not exist'
        )

    except Exception as exc:
        logger.exception(f'Failed to send password reset email: {exc}')
        raise self.retry(exc=exc,countdown=60)
