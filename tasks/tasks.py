import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from organizations.models import Membership, Organization

from .models import Notification, Task

logger=logging.getLogger(__name__)


@shared_task
def test_task():
    logger.info('Celery is working!')
    return 'Success'

@shared_task(bind=True,max_retries=3)
def send_mention_notification_email(self,notification_id):
    try:
        notification=Notification.objects.select_related(
            'user',
            'task',
        ).get(id=notification_id)
        if notification.type!='MENTION':
            return
        send_mail(
        subject='You were mentioned in ShipStream',
        message=(
            f'{notification.body}\n\n'
            f'Task: {notification.task.title}'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[notification.user.email],
        fail_silently=False,
        )
        logger.info(
        f'Mention notification email sent to {notification.user.email}'
        )

    except Notification.DoesNotExist:
        logger.warning(
            f'Notification {notification_id} does not exist'
        )

    except Exception as exc:
        logger.exception(
            f'Failed to send mention notification email: {exc}'
        )
        raise self.retry(exc=exc,countdown=60)


@shared_task(bind=True,max_retries=3)
def send_weekly_digest(self,organization_id):
    try:
        organization=Organization.objects.get(
            id=organization_id,
            is_active=True,
        )

        open_tasks=Task.objects.for_organization(
            organization
        ).exclude(
            status='DONE'
        )

        overdue_tasks=open_tasks.filter(
            due_date__lt=timezone.localdate()
        )

        recipients=list(
            Membership.objects.filter(
                organization=organization,
            ).values_list(
                'user__email',
                flat=True,
            )
        )

        if not recipients:
            return

        send_mail(
            subject=f'Weekly ShipStream digest — {organization.name}',
            message=(
                f'Weekly summary for {organization.name}\n\n'
                f'Open tasks: {open_tasks.count()}\n'
                f'Overdue tasks: {overdue_tasks.count()}'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )

        logger.info(
            f'Weekly digest sent for organization {organization.id}'
        )

    except Organization.DoesNotExist:
        logger.warning(
            f'Organization {organization_id} does not exist'
        )

    except Exception as exc:
        logger.exception(
            f'Failed to send weekly digest: {exc}'
        )
        raise self.retry(exc=exc,countdown=60)

@shared_task
def send_all_weekly_digests():
    organization_ids=Organization.objects.filter(
        is_active=True,
    ).values_list(
        'id',
        flat=True,
    )

    for organization_id in organization_ids:
        send_weekly_digest.delay(organization_id)
