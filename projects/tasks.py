import csv
import logging
import os

from celery import shared_task
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from tasks.models import Task

from .models import ExportJob

logger=logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 10},
)
def generate_export(self,export_job_id):
    job=ExportJob.objects.select_related('project').get(id=export_job_id)

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

        project_tasks=Task.objects.filter(
            project=job.project,
        ).select_related(
            'assignee',
        ).order_by(
            'status',
            'position',
            'id',
        )

        with open(filepath,'w',newline='') as csvfile:
            writer=csv.writer(csvfile)
            writer.writerow(['ID','Title','Status','Priority','Assignee','Due Date','Created At'])
            for task in project_tasks:
                writer.writerow([
                    task.id,
                    task.title,
                    task.status,
                    task.priority,
                    task.assignee.email if task.assignee else '',
                    task.due_date.isoformat() if task.due_date else '',
                    task.created_at.isoformat(),
                ])

        job.status = ExportJob.StatusChoices.Completed
        job.file_path = filepath
        job.file_url = reverse('export-download',kwargs={'version':'v1','pk':job.id})
        job.completed_at = timezone.now()

        job.save(
            update_fields=[
                'status',
                'file_path',
                'file_url',
                'completed_at',
            ]
        )
        logger.info('Export job %s completed successfully.',job.id)
        return job.file_url

    except Exception:
        logger.exception('Export job %s failed.',job.id)
        job.status=ExportJob.StatusChoices.Failed
        job.save(update_fields=['status'])
        raise
