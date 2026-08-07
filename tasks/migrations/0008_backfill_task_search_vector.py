from django.contrib.postgres.search import SearchVector
from django.db import migrations


def backfill_search_vector(apps,schema_editor):
    if schema_editor.connection.vendor!='postgresql':
        return
    Task=apps.get_model('tasks','Task')
    Task.objects.update(
        search_vector=SearchVector(
            'title',
            weight='A',
        ) + SearchVector(
            'description',
            weight='B',
        ),
    )


def noop(apps,schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0007_task_search_vector_and_indexes'),
    ]

    operations = [
        migrations.RunPython(backfill_search_vector,noop),
    ]
