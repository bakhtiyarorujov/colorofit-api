import os
import time
import uuid

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
from colorofit.i18n import error_payload
from rest_framework.generics import UpdateAPIView, RetrieveAPIView, ListAPIView, RetrieveUpdateAPIView, CreateAPIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from .serializers import GoogleTokenRequestSerializer, GoogleLoginResponseSerializer \
    , AppleLoginSerializer, AppleLoginResponseSerializer, UserAimDetailSerializer, TargetDetailSerializer \
    , UserProfileSerializer, AlertPreferenceSerializer, FeedbackSerializer, is_profile_complete
from django.core.files.uploadedfile import InMemoryUploadedFile
from .services.nutrition_ai import build_nutrition_advice
User = get_user_model()


# --- OAuth configuration (env-driven, with safe fallbacks) ---
# NOTE: this fallback is only used if GOOGLE_OAUTH_CLIENT_ID is unset in the
# environment. 2026-08-21: this had been pointed at project 197516977632 (an
# unrelated/orphaned GCP project) by a previous "fix" commit — the mobile
# app's real project is 504818468430 (calorilens-bb4d5). Set the real env var
# on the server; don't rely on this fallback in production.
GOOGLE_OAUTH_CLIENT_ID = os.environ.get(
    "GOOGLE_OAUTH_CLIENT_ID",
    "504818468430-q53sdgsag9i3oe7a898c3trg1nc2fim6.apps.googleusercontent.com",
)


class OptionalJWTAuthentication(JWTAuthentication):
    """JWTAuthentication that treats a missing/invalid/expired token as
    "not authenticated" instead of rejecting the whole request.

    GoogleLoginAPIView is `permission_classes = [AllowAny]`, but the project's
    DEFAULT_AUTHENTICATION_CLASSES (plain JWTAuthentication) still runs first
    and raises AuthenticationFailed for a bad Authorization header — which
    DRF turns into a hard 401 *before* AllowAny is ever consulted. The mobile
    app attaches a guest's access token here (to upgrade that guest account
    on Google sign-in); if that token happens to be stale/expired, a normal
    Google login must still succeed instead of getting rejected outright.
    """

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except AuthenticationFailed:
            return None

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
def _auth_payload(user):
    """Login response body shared by Google/guest — same shape, plus
    `profile_complete` and `is_guest`."""
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        },
        "tokens": get_tokens_for_user(user),
        "profile_complete": is_profile_complete(user),
        "is_guest": bool(getattr(user, "is_guest", False)),
    }


def _resolve_google_user(request, email, first_name, last_name):
    """Find-or-create the account for a Google login. If the request comes from
    an in-progress guest and the email is free, upgrade that SAME guest account
    (its data is preserved) instead of creating a new one."""
    current = request.user if request.user.is_authenticated else None
    existing = User.objects.filter(email=email).first()

    if current is not None and getattr(current, "is_guest", False) and existing is None:
        current.email = email
        if not current.first_name:
            current.first_name = first_name
        if not current.last_name:
            current.last_name = last_name
        current.is_guest = False
        current.save(update_fields=["email", "first_name", "last_name", "is_guest"])
        return current

    if existing is not None:
        return existing
    return User.objects.create(
        username=email, email=email, first_name=first_name, last_name=last_name,
    )


class GoogleLoginAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication]

    def post(self, request):
        token_id = request.data.get("token")

        if not token_id:
            return Response(error_payload(request, "token_required"), status=status.HTTP_400_BAD_REQUEST)

        try:
            idinfo = id_token.verify_oauth2_token(
                token_id,
                requests.Request(),
                GOOGLE_OAUTH_CLIENT_ID
            )
            email = idinfo['email']
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')

            user = _resolve_google_user(request, email, first_name, last_name)
            return Response(_auth_payload(user))

        except ValueError:
            return Response(error_payload(request, "invalid_token"), status=status.HTTP_400_BAD_REQUEST)


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
        except (ExpiredSignatureError, JWTClaimsError, JWTError):
            return Response(
                error_payload(request, "invalid_apple_token"),
                status=status.HTTP_400_BAD_REQUEST,
            )
        except http_requests.RequestException:
            return Response(
                error_payload(request, "apple_unreachable"),
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        email = decoded.get('email')
        if not email:
            return Response(error_payload(request, "email_missing_apple"), status=status.HTTP_400_BAD_REQUEST)

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
    tags=["Authentication"],
    summary="Guest sign-in",
    description=(
        "Creates an anonymous guest account and returns JWT tokens. The app "
        "stores them and works normally; a later Google sign-in upgrades this "
        "same account so guest data is preserved."
    ),
)
class GuestLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        user = User.objects.create(
            username=f"guest_{uuid.uuid4().hex}", is_guest=True
        )
        return Response(_auth_payload(user), status=status.HTTP_201_CREATED)


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
    summary="AI-augmented nutrition plan",
    description=(
        "Returns the same deterministic targets as `target-details/` (the "
        "formula stays the source of truth for calories) plus an `ai` block: "
        "an intelligently rebalanced protein/fat/carb split and a short "
        "personalised summary + tips generated by Claude. Falls back to the "
        "formula's own macro split with a null summary when the AI layer is "
        "unavailable. Pass `?lang=az|en|ru` to choose the advice language."
    ),
    parameters=[
        OpenApiParameter(
            name="lang", type=str, location=OpenApiParameter.QUERY, required=False,
            description="Advice language: az, en, or ru (default en).",
        ),
    ],
)
class NutritionAdviceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        targets = TargetDetailSerializer(user).data
        lang = request.query_params.get("lang", "en")
        advice = build_nutrition_advice(user, targets, lang)
        return Response({**targets, "ai": advice})


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


@extend_schema(
    tags=["User"],
    summary="Delete account",
    description="Permanently deletes the authenticated user and all their data "
                "(food logs, water intake, targets — cascaded). Required by the "
                "Apple App Store and Google Play. Irreversible.",
)
class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user
        user.delete()  # FoodItem / WaterIntake FKs cascade
        return Response(status=status.HTTP_204_NO_CONTENT)

