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
    , AppleLoginSerializer, AppleLoginResponseSerializer, UserAimDetailSerializer, TargetDetailSerializer\
    , FoodRecognitionRequestSerializer
from clarifai.client.model import Model
from django.core.files.uploadedfile import InMemoryUploadedFile
import base64
import requests as rq
User = get_user_model()

CLARIFAI_MODEL_URL = "https://clarifai.com/clarifai/main/models/food-item-recognition"
CLARIFAI_PAT = "c4b6fbbfd9384b92a35be2a0de5e97ab" 
NUTRITIONIX_APP_ID = "26d50180"
NUTRITIONIX_APP_KEY = "6e668f1850c515e975cb92818685fa82"

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


class TargetDetailView(RetrieveAPIView):
    serializer_class = TargetDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


def predict_clarifai_by_base64(base64_image: str, pat: str, model_id: str = "food-item-v1-recognition", app_id: str = "main"):

    url = f"https://api.clarifai.com/v2/models/{model_id}/outputs"

    headers = {
        "Authorization": f"Key {pat}",
        "Content-Type": "application/json"
    }

    data = {
        "user_app_id": {
            "user_id": "clarifai",  # or your actual user ID
            "app_id": app_id
        },
        "inputs": [
            {
                "data": {
                    "image": {
                        "base64": base64_image
                    }
                }
            }
        ]
    }

    response = rq.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def get_nutritionix_data(food_name: str):
    url = "https://trackapi.nutritionix.com/v2/natural/nutrients"
    headers = {
        "x-app-id": NUTRITIONIX_APP_ID,
        "x-app-key": NUTRITIONIX_APP_KEY,
        "Content-Type": "application/json"
    }
    data = {"query": food_name}

    response = rq.post(url, headers=headers, json=data)
    if response.status_code != 200:
        raise Exception(f"Nutritionix API error: {response.status_code}")

    result = response.json()
    food = result["foods"][0]

    nutrient_id_to_key = {
        301: 'calcium',
        303: 'iron',
        320: 'vitaminA',
        401: 'vitaminC',
    }

    vitamins_and_minerals = {k: 0.0 for k in nutrient_id_to_key.values()}
    for nutrient in food.get("full_nutrients", []):
        attr_id = nutrient.get("attr_id")
        value = nutrient.get("value")
        if attr_id in nutrient_id_to_key:
            vitamins_and_minerals[nutrient_id_to_key[attr_id]] = float(value or 0)

    return {
        "food_name": food.get("food_name"),
        "calories": food.get("nf_calories", 0),
        "protein": food.get("nf_protein", 0),
        "fat": food.get("nf_total_fat", 0),
        "saturated_fat": food.get("nf_saturated_fat", 0),
        "trans_fat": food.get("nf_trans_fatty_acid", 0),
        "carbohydrates": food.get("nf_total_carbohydrate", 0),
        "fiber": food.get("nf_dietary_fiber", 0),
        "sugar": food.get("nf_sugars", 0),
        "cholesterol": food.get("nf_cholesterol", 0),
        "sodium": food.get("nf_sodium", 0),
        **vitamins_and_minerals,
    }




@extend_schema(
    request=FoodRecognitionRequestSerializer,
    responses={
        200: OpenApiResponse(
            description="Successfully recognized the food",
            examples=[
                OpenApiExample(
                    'Success',
                    value={"prediction": "pizza"}
                )
            ]
        ),
        400: OpenApiResponse(
            description="No image provided or invalid request",
            examples=[
                OpenApiExample(
                    'No Image',
                    value={"error": "No image provided"},
                    status_codes=["400"]
                )
            ]
        ),
        500: OpenApiResponse(
            description="Prediction error or internal server issue",
            examples=[
                OpenApiExample(
                    'Prediction Failure',
                    value={"error": "Model prediction failed"},
                    status_codes=["500"]
                )
            ]
        )
    },
    tags=["Food Recognition"],
    summary="Recognize food from image",
    description="Uploads an image and returns the top predicted food label using the Clarifai model."
)
class FoodRecognitionView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = FoodRecognitionRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        image_file = serializer.validated_data["image"]

        try:
            image_bytes = image_file.read()
            base64_image = base64.b64encode(image_bytes).decode("utf-8")

            # Step 1: Predict food name
            prediction = predict_clarifai_by_base64(base64_image, CLARIFAI_PAT)
            concepts = prediction["outputs"][0]["data"]["concepts"]

            if not concepts:
                return Response({"error": "No prediction returned"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            food_name = concepts[0]["name"]  # Top prediction

            # Step 2: Get nutrition data from Nutritionix
            nutrition_data = get_nutritionix_data(food_name)

            return Response(nutrition_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)