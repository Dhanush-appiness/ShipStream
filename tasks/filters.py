import django_filters

from .models import Task


class TaskFilter(django_filters.FilterSet):
    due_date_from=django_filters.DateFilter(
        field_name='due_date',
        lookup_expr='gte'
    )
    due_date_to=django_filters.DateFilter(
        field_name='due_date',
        lookup_expr='lte'
    )
    label=django_filters.NumberFilter(
        field_name='tasklabel__label_id'
    )

    class Meta:
        model=Task
        fields=[
            'status',
            'assignee',
            'label',
            'due_date_from',
            'due_date_to',
        ]
