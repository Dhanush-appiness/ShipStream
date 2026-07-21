from .models import User
from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken
import logging 

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
        logger.info(f'User attempted to login: {email}')
        user=authenticate(username=email, password=password)
        if user is None:
            logger.warning(f'Invalid login attempt: {email}')
            raise AuthenticationFailed("Invalid username or password!")
        #if not user.is_verified:
         #   logger.warning(f'Email not verified: {email}')
          #  raise AuthenticationFailed("Please verify your email first!")
        refresh=RefreshToken.for_user(user)
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
    logger.info(f'Logout attempt')
    try:
        token=RefreshToken(refresh)
        token.blacklist()
        logger.info(f'User logged out successfully')
    except Exception as e:
        logger.error(f'Logout failed: {str(e)}')
        raise
