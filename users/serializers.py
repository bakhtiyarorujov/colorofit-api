from rest_framework import serializers


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