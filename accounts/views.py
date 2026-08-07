from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from common.throttling import AuthRateThrottle

from .serializers import (
    LoginSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
)
from .services import (
    confirm_password_reset,
    login_user,
    logout_user,
    register_user,
    request_password_reset,
)


@extend_schema(
    request=RegisterSerializer,
    responses=RegisterSerializer,
    summary='Register User',
    description='Creates new user account',
    tags=['Accounts'],
)
class RegisterView(APIView):
    """
    Handle user registration requests.
    """

    permission_classes=[AllowAny]
    throttle_classes=[AuthRateThrottle]
    def post(self,request,*args,**kwargs):
        """
        Register a new user.
        """

        serializer=RegisterSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            user=register_user(serializer.validated_data)
            return Response(
                {'message':'User created successfully',
                'id':user.id,
                'email':user.email},
                status=status.HTTP_201_CREATED
            )

@extend_schema(
    request=LoginSerializer,
    summary='Login User',
    description='Authenticate a user and return JWT tokens.',
    tags=['Accounts'],
)
class LoginView(APIView):
    """
    Handle user login requests.
    """

    permission_classes=[AllowAny]
    throttle_classes=[AuthRateThrottle]
    def post(self,request,*args,**kwargs):
        """
        Authenticate the user and return JWT tokens.
        """

        serializer=LoginSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            login_data=login_user(serializer.validated_data)
            return Response(
                {
                    'message':'Login successful',
                    'id':login_data['user'].id,
                    'email':login_data['user'].email,
                    'access':login_data['access'],
                    'refresh':login_data['refresh'],
                },
                status=status.HTTP_200_OK,
            )

@extend_schema(
    request=LogoutSerializer,
    summary='Logout User',
    description='Blacklist the refresh token.',
    tags=['Accounts'],
)
class LogoutView(APIView):
    """
    Handle user logout requests.
    """

    permission_classes=[IsAuthenticated]
    def post(self,request,*args,**kwargs):
        """
        Logout the authenticated user by blacklisting the refresh token.
        """
        serializer=LogoutSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            logout_user(serializer.validated_data)
            return Response(
                {
                    'message':"Logged out successfully"
                },
                status=status.HTTP_200_OK
            )

class PasswordResetRequestView(APIView):
    permission_classes=[AllowAny]
    throttle_classes=[AuthRateThrottle]

    def post(self,request,*args,**kwargs):
        serializer=PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email=serializer.validated_data['email']
        try:
            request_password_reset(email)
        except User.DoesNotExist:
            pass
        return Response(
            {
                'message':'If an account exists with this email, a password reset link has been sent.'
            },
            status=status.HTTP_200_OK,
        )

class PasswordResetConfirmView(APIView):
    permission_classes=[AllowAny]
    throttle_classes=[AuthRateThrottle]

    def post(self,request,*args,**kwargs):
        serializer=PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token=serializer.validated_data['token']
        new_password=serializer.validated_data['new_password']
        confirm_password_reset(token,new_password=new_password)
        return Response(
            {
                'message':'Password reset successfully!'
            },
            status=status.HTTP_200_OK,
        )
