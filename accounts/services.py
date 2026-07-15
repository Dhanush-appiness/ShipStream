from .models import User


def register_user(validated_data):
    user=User(
        email=validated_data['email'],
    )
    user.set_password(validated_data['password'])
    user.save()
    return user