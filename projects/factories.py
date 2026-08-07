import factory


class ProjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model='projects.Project'

    organization=factory.SubFactory('organizations.factories.OrganizationFactory')
    name=factory.Sequence(lambda n:f'Project {n}')
    description='Test project description'
    status='ACTIVE'
