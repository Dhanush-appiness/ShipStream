import csv
import logging
import os
from celery import shared_task
from django.conf import settings
from .models import ExportJob
from django.utils import timezone


logger=logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 10},
)
def generate_export(self,export_job_id):
    job=ExportJob.objects.get(id=export_job_id)

    # Idempotency
    if job.status==ExportJob.StatusChoices.Completed:
        return job.file_url

    try:
        job.status=ExportJob.StatusChoices.Processing
        job.save(update_fields=['status'])
        export_dir=os.path.join(settings.BASE_DIR,'exports')
        os.makedirs(export_dir,exist_ok=True)
        filename=f'export_{job.id}.csv'
        filepath=os.path.join(export_dir,filename)
        with open(filepath,'w',newline='') as csvfile:
            writer=csv.writer(csvfile)
            writer.writerow(['Project','Status'])
            writer.writerow([
                job.project.name,
                job.project.status,
            ])
        job.status = ExportJob.StatusChoices.Completed
        job.file_url = filepath
        job.completed_at = timezone.now()

        job.save(
            update_fields=[
                'status',
                'file_url',
                'completed_at',
            ]
        )
        logger.info('Export job %s completed successfully.',job.id)
        return filepath

    except Exception:
        logger.exception('Export job %s failed.',job.id)
        job.status=ExportJob.StatusChoices.Failed
        job.save(update_fields=['status'])
        raise