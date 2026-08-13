import factory

from accounts.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model=User
        skip_postgeneration_save=True

    email=factory.Sequence(lambda n:f'user{n}@example.com')
    is_verified=True

    @factory.post_generation
    def password(obj:User,create,extracted,**kwargs):
        obj.set_password(extracted or 'testpass123')
        if create:
            obj.save()
