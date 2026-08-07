import logging
import secrets
from datetime import timedelta
from typing import cast

from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import PasswordReset, User
from .tasks import send_password_reset_email

logger=logging.getLogger(__name__)

def register_user(validated_data):
    """
    Register a new user after verifying that the email is unique.
    """

    email=validated_data['email']
    logger.info(f'Registration attempt for email: {email}')
    try:
        if User.objects.filter(email=email).exists():
            logger.warning(f'Registration failed. Email already exists: {email}')
            raise ValidationError('User already exists!')
        user=User(email=email,)
        user.set_password(validated_data['password'])
        user.save()
        logger.info(f'User registered successfully: {email}')
        return user
    except Exception as e:
        logger.error(f'Registration error: {str(e)}')
        raise

def login_user(validated_data):
    """
    Authenticate the user and generate JWT access and refresh tokens.
    """
    try:
        email=validated_data['email']
        password=validated_data['password']
        user=authenticate(username=email, password=password)
        if user is None:
            logger.warning(f'Invalid login attempt: {email}')
            raise AuthenticationFailed("Invalid username or password!")
        #if not user.is_verified:
         #   logger.warning(f'Email not verified: {email}')
          #  raise AuthenticationFailed("Please verify your email first!")
        refresh=cast(RefreshToken,RefreshToken.for_user(user))
        logger.info(f'User logged in successfully: {email}')
        return{
            'user':user,
            'access':str(refresh.access_token),
            'refresh':str(refresh),
        }
    except Exception as e:
        logger.error(f'Login failed: {str(e)}')
        raise

def logout_user(validated_data):
    """
    Blacklist the user's refresh token to log them out.
    """

    refresh=validated_data['refresh']
    try:
        token=RefreshToken(refresh)
        token.blacklist()
        logger.info('User logged out successfully')
    except Exception as e:
        logger.error(f'Logout failed: {str(e)}')
        raise


def request_password_reset(email):
    """
    Create a password reset token for the given email and schedule the
    reset email on Celery once the transaction commits. Deliberately lets
    User.DoesNotExist propagate to the caller rather than swallowing it -
    the view catches it and returns the same generic response either way,
    so this function doesn't need to know about that concealment itself.
    """

    try:
        user=User.objects.get(email=email)
        token=secrets.token_urlsafe(32)
        expires_at=timezone.now()+timedelta(hours=1)
        password_reset=PasswordReset.objects.create(
            user=user,
            token=token,
            expires_at=expires_at,
        )
        transaction.on_commit(
        lambda:send_password_reset_email.delay(password_reset.id)
    )
        return password_reset
    except User.DoesNotExist:
        logger.info(f'Password reset requested for unknown email: {email}')
        raise
    except Exception as e:
        logger.error(f'Password reset request failed for {email}: {str(e)}')
        raise

@transaction.atomic
def confirm_password_reset(token,new_password):
    """
    Set a new password given a valid, unused, unexpired reset token, then
    mark the token used_at so it can't be replayed. Wrapped in a single
    transaction so a failure between setting the password and marking the
    token used can't leave the token replayable.
    """
    try:
        password_reset=PasswordReset.objects.filter(token=token).first()
        if password_reset is None:
            raise ValueError('Invalid password reset token')
        if password_reset.used_at is not None:
            raise ValueError('Password reset token has already been used')
        if password_reset.expires_at<=timezone.now():
            raise ValueError('Password reset token has expired')
        user=password_reset.user
        user.set_password(new_password)
        user.save(update_fields=['password'])
        password_reset.used_at=timezone.now()
        password_reset.save(update_fields=['used_at'])
        logger.info(f'Password reset completed for: {user.email}')
        return user
    except Exception as e:
        logger.error(f'Password reset confirmation failed: {str(e)}')
        raise
