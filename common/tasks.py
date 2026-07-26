from celery import shared_task
from django.utils import timezone
from projects.models import ExportJob
import logging

logger=logging.getLogger(__name__)

@shared_task
def cleanup_old_exports():
    deleted,_=ExportJob.objects.filter(
        status=ExportJob.StatusChoices.Completed,
        completed_at__lt=timezone.now()-timezone.timedelta(days=30),
    ).delete()
    logger.info(f'Deleted{deleted}old export jobs.')