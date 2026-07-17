from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import RegisterSerializer, LoginSerializer, LogoutSerializer
from .services import register_user, login_user, logout_user

class RegisterView(APIView):
    """
    Handle user registration requests.
    """
    
    def post(self,request):
        """
        Register a new user.
        """
        
        serializer=RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user=register_user(serializer.validated_data)
            return Response(
                {'message':'User created successfully',
                'email':user.email},
                status=status.HTTP_201_CREATED
            )
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
    )

class LoginView(APIView):
    """
    Handle user login requests.
    """
    
    def post(self,request):
        """
        Authenticate the user and return JWT tokens.
        """
        
        serializer=LoginSerializer(data=request.data)
        if serializer.is_valid():
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
        return Response(
            serializer.errors, status=status.HTTP_400_BAD_REQUEST
        )

class LogoutView(APIView):
    """
    Handle user logout requests.
    """
    
    def post(self,request):
        """
        Logout the authenticated user by blacklisting the refresh token.
        """
        serializer=LogoutSerializer(data=request.data)
        if serializer.is_valid():
            logout_user(serializer.validated_data)
            return Response(
                {
                    'message':"Logged out successfully"
                },
                status=status.HTTP_200_OK
            )
            
        return Response(
            serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )