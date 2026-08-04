import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from .models import Invitation

logger=logging.getLogger(__name__)


@shared_task(bind=True,max_retries=3)
def send_invitation_email(self,invitation_id):
    try:
        invitation=Invitation.objects.get(id=invitation_id)

        if invitation.status!=Invitation.StatusChoices.PENDING:
            return

        invite_link=f'{settings.FRONTEND_URL}/invitations/accept?token={invitation.token}'

        send_mail(
            subject='You have been invited to ShipStream',
            message=(
                f'You have been invited to join '
                f'{invitation.organization.name} as {invitation.role}.\n\n'
                f'Accept your invitation here:\n{invite_link}'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            fail_silently=False,
        )

        logger.info(f'Invitation email sent to {invitation.email}')

    except Invitation.DoesNotExist:
        logger.warning(f'Invitation {invitation_id} does not exist')

    except Exception as exc:
        logger.exception(f'Failed to send invitation email: {exc}')
        raise self.retry(exc=exc,countdown=60)
