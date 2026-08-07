import factory


class TaskFactory(factory.django.DjangoModelFactory):
    class Meta:
        model='tasks.Task'

    project=factory.SubFactory('projects.factories.ProjectFactory')
    title=factory.Sequence(lambda n:f'Task {n}')
    status='TODO'
    priority='MEDIUM'
