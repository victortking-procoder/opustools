# authentication/views.py

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.contrib.auth import login, logout, get_user_model
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer
from django.middleware.csrf import get_token

User = get_user_model() # Get the currently active user model

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            "user": UserSerializer(user, context=self.get_serializer_context()).data,
            "token": token.key,
            "message": "User registered successfully."
        }, status=status.HTTP_201_CREATED)

class LoginView(APIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = LoginSerializer # Although not a generic view, useful for documentation

    def post(self, request, format=None):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        login(request, user) # This sets the session cookie (optional, for session auth)
        token, created = Token.objects.get_or_create(user=user)

        response = Response({
            "user": UserSerializer(user).data, # Use the updated UserSerializer
            "token": token.key,
            "message": "Logged in successfully."
        })
        response.set_cookie('csrftoken', get_token(request))
        return response

class LogoutView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        request.user.auth_token.delete() # Delete the user's token
        logout(request) # Clear session (if using session auth)
        response = Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)
        response.delete_cookie('csrftoken') # Clear CSRF cookie on logout
        response.delete_cookie('sessionid') # Clear session cookie on logout (if applicable)
        return response

# Modified UserDetailView to allow updates (PATCH/PUT)
class UserDetailUpdateView(generics.RetrieveUpdateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserSerializer # This serializer will be used for both retrieve and update

    def get_object(self):
        return self.request.user

    # You can add custom logic for partial updates if needed, but serializer handles most
    def partial_update(self, request, *args, **kwargs):
        # Allow username and email to be updated, and also first_name/last_name
        # Ensure that only allowed fields are updated.
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


class GetCSRFToken(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, format=None):
        csrf_token = get_token(request)
        return Response({'csrfToken': csrf_token}, status=status.HTTP_200_OK)