import factory


class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model='organizations.Organization'
        django_get_or_create=('slug',)

    name=factory.Sequence(lambda n:f'Organization {n}')
    slug=factory.Sequence(lambda n:f'organization-{n}')


class MembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model='organizations.Membership'

    user=factory.SubFactory('accounts.factories.UserFactory')
    organization=factory.SubFactory(OrganizationFactory)
    role='MEMBER'
