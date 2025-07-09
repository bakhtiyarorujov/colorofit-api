from rest_framework import serializers
from .models import User

# Request Serializer
class GoogleTokenRequestSerializer(serializers.Serializer):
    token = serializers.CharField(help_text="Google ID token from client")

# Response Serializer
class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class GoogleLoginResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    tokens = serializers.DictField(child=serializers.CharField())


class AppleLoginSerializer(serializers.Serializer):
    token = serializers.CharField()
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)


class AppleLoginResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    tokens = serializers.DictField(child=serializers.CharField())


class UserAimDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'age',
            'gender'
            'height',
            'weight',
            'aimed_weight',
            'aimed_date',
            'life_style',
        )
    