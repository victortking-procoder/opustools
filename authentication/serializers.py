# authentication/serializers.py

from rest_framework import serializers
from django.contrib.auth.models import User # Ensure you import the correct User model
from django.contrib.auth import authenticate

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        # Include first_name and last_name, and ensure they are writable
        fields = ('id', 'username', 'email', 'first_name', 'last_name')
        read_only_fields = ('username',) # Username is usually not editable

    def update(self, instance, validated_data):
        # We're handling email, first_name, last_name updates here.
        # Username is set to read_only_fields.
        instance.email = validated_data.get('email', instance.email)
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.save()
        return instance

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2', 'first_name', 'last_name') # Also allow these in registration
        extra_kwargs = {'password': {'write_only': True}}

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return data

    def create(self, validated_data):
        validated_data.pop('password2') # Remove password2 before creating user
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''), # Use .get for optional fields
            last_name=validated_data.get('last_name', '')
        )
        return user

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=False) # Make username/email optional, can login with either
    email = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if not (username or email):
            msg = 'Must include either "username" or "email".'
            raise serializers.ValidationError(msg, code='authorization')

        if username:
            user = authenticate(request=self.context.get('request'), username=username, password=password)
        elif email:
            # Authenticate by email
            try:
                user_obj = User.objects.get(email=email)
                user = authenticate(request=self.context.get('request'), username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None # User with this email doesn't exist
            
        if not user:
            msg = 'Unable to log in with provided credentials.'
            raise serializers.ValidationError(msg, code='authorization')

        data['user'] = user
        return data

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, style={'input_type': 'password'})