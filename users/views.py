from rest_framework.views import APIView
from rest_framework.response import Response
from datetime import date
from rest_framework import status
from google.oauth2 import id_token
from jose import jwt
from google.auth.transport import requests
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse, OpenApiParameter
from .utils import get_tokens_for_user
from rest_framework.generics import UpdateAPIView, RetrieveAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from .serializers import GoogleTokenRequestSerializer, GoogleLoginResponseSerializer \
    , AppleLoginSerializer, AppleLoginResponseSerializer, UserAimDetailSerializer, TargetDetailSerializer
User = get_user_model()


@extend_schema(
    request=GoogleTokenRequestSerializer,
    responses={
        200: OpenApiResponse(
            response=GoogleLoginResponseSerializer,
            description='Successful login with JWT tokens',
            examples=[
                OpenApiExample(
                    'Success',
                    value={
                        "user": {
                            "id": 1,
                            "email": "user@example.com",
                            "first_name": "Jane",
                            "last_name": "Doe"
                        },
                        "tokens": {
                            "access": "<access_token>",
                            "refresh": "<refresh_token>"
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Invalid or missing token",
            examples=[
                OpenApiExample(
                    'Missing token',
                    value={"error": "Token is required"},
                    status_codes=["400"]
                ),
                OpenApiExample(
                    'Invalid token',
                    value={"error": "Invalid token", "details": "Token verification failed"},
                    status_codes=["400"]
                )
            ]
        )
    },
    tags=["Authentication"],
    summary="Google Sign-In",
    description="Authenticate or register a user via Google ID token and return JWT access and refresh tokens."
)
class GoogleLoginAPIView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        token_id = request.data.get("token")

        if not token_id:
            return Response({"error": "Token is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Replace with your actual Google client ID
            idinfo = id_token.verify_oauth2_token(
                token_id,
                requests.Request(),
                "197516977632-8vbn2h7a5slg421nojbge2ftgaasogeg.apps.googleusercontent.com"
            )
            email = idinfo['email']
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')

            user, created = User.objects.get_or_create(email=email, defaults={
                'username': email,
                'first_name': first_name,
                'last_name': last_name,
            })

            tokens = get_tokens_for_user(user)

            return Response({
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
                "tokens": tokens
            })

        except ValueError as e:
            return Response({"error": "Invalid token", "details": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    request=AppleLoginSerializer,
    responses={
        200: OpenApiResponse(
            response=AppleLoginResponseSerializer,
            description='Successful login with JWT tokens via Apple ID',
            examples=[
                OpenApiExample(
                    'Success',
                    value={
                        "user": {
                            "id": 1,
                            "email": "user@example.com",
                            "first_name": "Jane",
                            "last_name": "Doe"
                        },
                        "tokens": {
                            "access": "<access_token>",
                            "refresh": "<refresh_token>"
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Invalid or missing token",
            examples=[
                OpenApiExample(
                    'Missing token',
                    value={"error": "Token is required"},
                    status_codes=["400"]
                ),
                OpenApiExample(
                    'Invalid token',
                    value={"error": "Invalid Apple token", "details": "Signature verification failed"},
                    status_codes=["400"]
                )
            ]
        )
    },
    tags=["Authentication"],
    summary="Apple Sign-In",
    description=(
        "Authenticate or register a user via Apple ID token and return JWT access and refresh tokens. "
        "The token is provided by Apple Sign-In via frontend (iOS or web)."
    )
)
class AppleLoginAPIView(APIView):
    def post(self, request):
        serializer = AppleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token']
        first_name = serializer.validated_data.get('first_name', '')
        last_name = serializer.validated_data.get('last_name', '')

        try:
            # Decode without verifying signature (for basic data extraction)
            decoded = jwt.get_unverified_claims(token)
            email = decoded.get('email')

            if not email:
                return Response({"error": "Email not present in Apple token"}, status=status.HTTP_400_BAD_REQUEST)

            user, created = User.objects.get_or_create(email=email, defaults={
                'username': email,
                'first_name': first_name,
                'last_name': last_name,
            })

            tokens = get_tokens_for_user(user)

            response_data = {
                "user": user,
                "tokens": tokens
            }

            response_serializer = AppleLoginResponseSerializer(response_data)
            return Response(response_serializer.data)

        except jwt.JWTError as e:
            return Response({"error": "Invalid Apple token", "details": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

class UserAimDetailUpdateView(UpdateAPIView):
    serializer_class = UserAimDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
    
    # def update(self, request, *args, **kwargs):
    #     partial = kwargs.pop('partial', False)
    #     instance = self.get_object()
    #     serializer = self.get_serializer(instance, data=request.data, partial=partial)
    #     serializer.is_valid(raise_exception=True)
    #     self.perform_update(serializer)

    #     calculated_data = self.calculate_targets(instance)

    #     return Response({
    #         "message": "User data updated successfully.",
    #         "data": serializer.data,
    #         "targets": calculated_data,
    #     }, status=status.HTTP_200_OK)

    # def calculate_targets(self, user):
    #     weight = float(user.weight)
    #     aimed_weight = float(user.aimed_weight)
    #     height = float(user.height)
    #     lifestyle = user.life_style  # e.g. "moderate"
    #     aimed_date = user.aimed_date
    #     gender = user.gender  # assume "male" or "female"
    #     age = int(user.age)  # assume age is available

    #     activity_factors = {
    #         "sedentary": 1.2,
    #         "light": 1.375,
    #         "moderate": 1.55,
    #         "active": 1.725,
    #         "very_active": 1.9,
    #     }

    #     # Step 1: BMR
    #     s = 5 if gender == "male" else -161
    #     bmr = 10 * weight + 6.25 * height - 5 * age + s

    #     # Step 2: TDEE
    #     activity_factor = activity_factors.get(lifestyle, 1.2)
    #     tdee = bmr * activity_factor

    #     # Step 3: Calorie deficit and target
    #     weight_loss_goal = weight - aimed_weight
    #     days_left = max((aimed_date - date.today()).days, 1)  # avoid division by zero
    #     total_deficit = weight_loss_goal * 7700
    #     daily_deficit = total_deficit / days_left
    #     calorie_target = tdee - daily_deficit

    #     return {
    #         "TDEE": round(tdee),
    #         "daily_deficit": round(daily_deficit),
    #         "calorie_target": round(calorie_target),
    #         "days_left": days_left
    #     }

class TargetDetailView(RetrieveAPIView):
    serializer_class = TargetDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
