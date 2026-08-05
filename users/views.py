import os
import time

import requests as http_requests
from rest_framework.views import APIView
from rest_framework.response import Response
from datetime import date
from rest_framework import status
from google.oauth2 import id_token
from jose import jwt
from jose.exceptions import JWTError, ExpiredSignatureError, JWTClaimsError
from google.auth.transport import requests
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse, OpenApiParameter
from .utils import get_tokens_for_user
from rest_framework.generics import UpdateAPIView, RetrieveAPIView, ListAPIView, RetrieveUpdateAPIView, CreateAPIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from .serializers import GoogleTokenRequestSerializer, GoogleLoginResponseSerializer \
    , AppleLoginSerializer, AppleLoginResponseSerializer, UserAimDetailSerializer, TargetDetailSerializer \
    , UserProfileSerializer, AlertPreferenceSerializer, FeedbackSerializer, is_profile_complete
from django.core.files.uploadedfile import InMemoryUploadedFile
User = get_user_model()


# --- OAuth configuration (env-driven, with safe fallbacks) ---
GOOGLE_OAUTH_CLIENT_ID = os.environ.get(
    "GOOGLE_OAUTH_CLIENT_ID",
    "504818468430-q53sdgsag9i3oe7a898c3trg1nc2fim6.apps.googleusercontent.com",
)

APPLE_ISSUER = "https://appleid.apple.com"
APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"
# The `aud` claim of an Apple identity token equals the app's client id
# (the iOS bundle id for native Sign in with Apple).
APPLE_CLIENT_IDS = [
    c.strip() for c in os.environ.get(
        "APPLE_CLIENT_IDS", "az.cuzdan.calorilens"
    ).split(",") if c.strip()
]

# Simple in-process cache of Apple's public keys (they rotate rarely).
_apple_jwks_cache = {"keys": None, "fetched_at": 0.0}
_APPLE_JWKS_TTL = 60 * 60  # 1 hour


def _get_apple_jwks():
    """Fetch (and cache) Apple's public signing keys."""
    now = time.time()
    if _apple_jwks_cache["keys"] and now - _apple_jwks_cache["fetched_at"] < _APPLE_JWKS_TTL:
        return _apple_jwks_cache["keys"]
    resp = http_requests.get(APPLE_KEYS_URL, timeout=10)
    resp.raise_for_status()
    keys = resp.json().get("keys", [])
    _apple_jwks_cache["keys"] = keys
    _apple_jwks_cache["fetched_at"] = now
    return keys


def verify_apple_identity_token(token: str) -> dict:
    """Verify an Apple identity token's signature, issuer and audience.

    Returns the decoded claims on success; raises jose JWTError-family
    exceptions on any verification failure.
    """
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")

    keys = _get_apple_jwks()
    signing_key = next((k for k in keys if k.get("kid") == kid), None)
    if signing_key is None:
        # Key set may have rotated; force a refresh once.
        _apple_jwks_cache["keys"] = None
        keys = _get_apple_jwks()
        signing_key = next((k for k in keys if k.get("kid") == kid), None)
    if signing_key is None:
        raise JWTError("No matching Apple public key for token 'kid'.")

    # Verify signature + issuer, then check audience against our client ids.
    claims = jwt.decode(
        token,
        signing_key,
        algorithms=["RS256"],
        issuer=APPLE_ISSUER,
        options={"verify_aud": False},
    )
    if claims.get("aud") not in APPLE_CLIENT_IDS:
        raise JWTClaimsError("Apple token audience does not match this app.")
    return claims



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
            idinfo = id_token.verify_oauth2_token(
                token_id,
                requests.Request(),
                GOOGLE_OAUTH_CLIENT_ID
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
                "tokens": tokens,
                "profile_complete": is_profile_complete(user),
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
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AppleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token']
        first_name = serializer.validated_data.get('first_name', '')
        last_name = serializer.validated_data.get('last_name', '')

        try:
            # Verify the token's signature, issuer and audience against Apple's
            # public keys before trusting any claim.
            decoded = verify_apple_identity_token(token)
        except (ExpiredSignatureError, JWTClaimsError, JWTError) as e:
            return Response(
                {"error": "Invalid Apple token", "details": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except http_requests.RequestException:
            return Response(
                {"error": "Could not reach Apple to verify the token. Try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

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
        
@extend_schema(
    tags=["User"]
)
class UserAimDetailUpdateView(UpdateAPIView):
    serializer_class = UserAimDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

@extend_schema(
    tags=["User"]
)
class TargetDetailView(RetrieveAPIView):
    serializer_class = TargetDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


@extend_schema(
    tags=["User"],
    summary="Get / Update current user's profile",
    description=(
        "GET returns the authenticated user's full profile. "
        "PATCH allows updating name, bio, profile_picture, and body metrics. "
        "Use multipart/form-data when uploading a profile picture."
    ),
)
class UserProfileView(RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self):
        return self.request.user


@extend_schema(
    tags=["User"],
    summary="Get / Update alert (notification) preferences",
    description=(
        "GET returns the current user's notification toggles. "
        "PATCH updates any subset of: alert_meal_reminders, "
        "alert_water_reminders, alert_weekly_summary, alert_goal_achievements."
    ),
)
class AlertPreferenceView(RetrieveUpdateAPIView):
    serializer_class = AlertPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


@extend_schema(
    tags=["User"],
    summary="Submit feedback",
    description="Create a feedback entry (rating 0..5 + free-form message). Authenticated users only.",
)
class FeedbackCreateView(CreateAPIView):
    serializer_class = FeedbackSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

