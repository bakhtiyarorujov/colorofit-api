from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import LifeStyle

User = get_user_model()

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if not username or not password:
            raise serializers.ValidationError("Username and password are required.")

        user = User.objects.filter(username=username).first()
        if user is None or not user.check_password(password):
            raise serializers.ValidationError("Invalid username or password.")

        return attrs