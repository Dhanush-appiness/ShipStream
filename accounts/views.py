from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import RegisterSerializer, LoginSerializer, LogoutSerializer
from .services import register_user, login_user, logout_user
from rest_framework.permissions import AllowAny,IsAuthenticated
from drf_spectacular.utils import extend_schema

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
    def post(self,request,*args,**kwargs):
        """
        Register a new user.
        """
        
        serializer=RegisterSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            user=register_user(serializer.validated_data)
            return Response(
                {'message':'User created successfully',
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
