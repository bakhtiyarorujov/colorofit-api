import base64
import logging
import os
from datetime import date, datetime, timedelta
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse, OpenApiParameter
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
import requests as rq
from .models import FoodItem, WaterIntake, MealType, WaterIntakeType
from rest_framework.permissions import IsAuthenticated, AllowAny
from .serializers import FoodRecognitionRequestSerializer, FoodItemSerializer, FoodItemUpdateSerializer \
    , WaterIntakeSerializer, AddRecipeRequestSerializer, FoodStatsResponseSerializer, WaterIntakePreferenceSerializer \
    , MealTypeListSerializer, WaterIntakeTypeSerializer, WaterIntakePreferenceGoalUpdateSerializer
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

# Constants
SPOONACULAR_API_KEY = os.environ.get("SPOONACULAR_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

# Meal type mapping
MEAL_TYPE_MAPPING = {
    'breakfast': 'Breakfast',
    'lunch': 'Lunch',
    'snacks': 'Snacks',
    'snack': 'Snacks',
    'dinner': 'Dinner',
}

MEAL_TYPE_GROUPING_MAP = {
    'breakfast': 'breakfast',
    'lunch': 'lunch',
    'snacks': 'snacks',
    'snack': 'snacks',
    'dinner': 'dinner',
}

# Date formats
DATE_FORMATS = [
    '%Y-%m-%d',      # 2026-12-02
    '%m/%d/%Y',      # 12/2/2026 or 12/02/2026
    '%d/%m/%Y',      # 2/12/2026 or 02/12/2026
    '%Y/%m/%d',      # 2026/12/02
]

User = get_user_model()


# Helper Functions
def parse_date(date_string: str) -> date:
    """
    Parse date string in multiple formats.
    
    Args:
        date_string: Date string in various formats
        
    Returns:
        date object
        
    Raises:
        ValueError: If date cannot be parsed
    """
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(date_string, date_format).date()
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse date: {date_string}")


def resolve_meal_type(meal_type_id=None, meal_type_name=None):
    """
    Resolve meal type by ID or name.
    
    Args:
        meal_type_id: Optional meal type ID
        meal_type_name: Optional meal type name
        
    Returns:
        MealType instance or None
    """
    meal_type = None
    
    # First try to find by name (preferred method)
    if meal_type_name:
        meal_type_name_lower = meal_type_name.lower().strip()
        backend_meal_type_name = MEAL_TYPE_MAPPING.get(meal_type_name_lower, meal_type_name)
        
        try:
            meal_type = MealType.objects.get(name__iexact=backend_meal_type_name)  # pylint: disable=no-member
        except MealType.DoesNotExist:  # pylint: disable=no-member
            logger.warning("Meal type not found by name: %s", backend_meal_type_name)
    
    # If not found by name, try by ID (fallback)
    if meal_type is None and meal_type_id:
        try:
            meal_type = MealType.objects.get(id=meal_type_id)  # pylint: disable=no-member
        except MealType.DoesNotExist:  # pylint: disable=no-member
            logger.warning("Meal type not found by ID: %s", meal_type_id)
    
    return meal_type


def group_food_items_by_meal_type(food_items_data):
    """
    Group food items by meal type.
    
    Args:
        food_items_data: List of serialized food item data
        
    Returns:
        Dictionary with meal type keys and food item lists
    """
    grouped_data = {
        'breakfast': [],
        'lunch': [],
        'snacks': [],
        'dinner': []
    }
    
    for item_data in food_items_data:
        meal_type_name = item_data.get('meal_type_name', '').strip() if item_data.get('meal_type_name') else None
        
        if meal_type_name:
            meal_type_name_lower = meal_type_name.lower()
            # Try exact match first
            matched_key = MEAL_TYPE_GROUPING_MAP.get(meal_type_name_lower)
            if matched_key:
                grouped_data[matched_key].append(item_data)
            elif 'breakfast' in meal_type_name_lower:
                grouped_data['breakfast'].append(item_data)
            elif 'lunch' in meal_type_name_lower:
                grouped_data['lunch'].append(item_data)
            elif 'snack' in meal_type_name_lower:
                grouped_data['snacks'].append(item_data)
            elif 'dinner' in meal_type_name_lower:
                grouped_data['dinner'].append(item_data)
            else:
                grouped_data['snacks'].append(item_data)
        else:
            grouped_data['snacks'].append(item_data)
    
    return grouped_data


def extract_nutrition_data(nutrients):
    """
    Extract nutrition data from nutrients list.
    
    Args:
        nutrients: List of nutrient dictionaries from API
        
    Returns:
        Dictionary mapping nutrient names to values
    """
    nutrient_map = {}
    for nutrient in nutrients:
        name = nutrient.get("name", "").lower()
        amount = nutrient.get("amount", 0)
        nutrient_map[name] = float(amount or 0)
    
    return {
        "calories": nutrient_map.get("calories", 0),
        "protein": nutrient_map.get("protein", 0),
        "fat": nutrient_map.get("fat", 0),
        "saturated_fat": nutrient_map.get("saturated fat", 0),
        "trans_fat": nutrient_map.get("trans fat", 0),
        "carbohydrates": nutrient_map.get("carbohydrates", 0),
        "fiber": nutrient_map.get("fiber", 0),
        "sugar": nutrient_map.get("sugar", 0),
        "cholesterol": nutrient_map.get("cholesterol", 0),
        "sodium": nutrient_map.get("sodium", 0),
        "calcium": nutrient_map.get("calcium", 0),
        "iron": nutrient_map.get("iron", 0),
        "potassium": nutrient_map.get("potassium", 0),
        "zinc": nutrient_map.get("zinc", 0),
        "vitaminA": nutrient_map.get("vitamin a", 0),
        "vitaminC": nutrient_map.get("vitamin c", 0),
        "vitaminD": nutrient_map.get("vitamin d", 0),
        "vitaminE": nutrient_map.get("vitamin e", 0),
        "vitaminK": nutrient_map.get("vitamin k", 0),
    }


class GeminiAPIError(Exception):
    """Custom exception for Gemini API errors"""


def predict_food_with_gemini(base64_image: str, api_key: str = None):
    """
    Use Gemini multimodal model to recognize food and estimate nutrition in one call.
    Returns dict matching extract_nutrition_data() output plus 'food_name'.
    """
    api_key = api_key or GEMINI_API_KEY
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )

    prompt = (
        "You are a nutrition expert. Analyze the food in this image. "
        "Identify the dish (including regional dishes like Azerbaijani plov, dolma, qutab if present). "
        "Estimate the visible portion size in grams, then return realistic nutrition values "
        "for that portion. All numeric values must be numbers (not strings). "
        "If the image does not contain food, set food_name to an empty string and all numbers to 0."
    )

    response_schema = {
        "type": "OBJECT",
        "properties": {
            "food_name": {"type": "STRING"},
            "estimated_grams": {"type": "NUMBER"},
            "calories": {"type": "NUMBER"},
            "protein": {"type": "NUMBER"},
            "fat": {"type": "NUMBER"},
            "saturated_fat": {"type": "NUMBER"},
            "trans_fat": {"type": "NUMBER"},
            "carbohydrates": {"type": "NUMBER"},
            "fiber": {"type": "NUMBER"},
            "sugar": {"type": "NUMBER"},
            "cholesterol": {"type": "NUMBER"},
            "sodium": {"type": "NUMBER"},
            "calcium": {"type": "NUMBER"},
            "iron": {"type": "NUMBER"},
            "potassium": {"type": "NUMBER"},
            "zinc": {"type": "NUMBER"},
            "vitaminA": {"type": "NUMBER"},
            "vitaminC": {"type": "NUMBER"},
            "vitaminD": {"type": "NUMBER"},
            "vitaminE": {"type": "NUMBER"},
            "vitaminK": {"type": "NUMBER"},
        },
        "required": ["food_name", "calories", "protein", "fat", "carbohydrates"],
    }

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}},
            ]
        }],
        "generationConfig": {
            "response_mime_type": "application/json",
            "response_schema": response_schema,
            "temperature": 0.2,
        },
    }

    try:
        response = rq.post(url, json=payload, timeout=45)
    except rq.exceptions.RequestException as e:
        raise GeminiAPIError(f"Gemini API request failed: {str(e)}") from e

    if response.status_code != 200:
        raise GeminiAPIError(
            f"Gemini API error: {response.status_code} - {response.text[:300]}"
        )

    try:
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        import json as _json
        result = _json.loads(text)
    except (ValueError, KeyError, IndexError) as e:
        raise GeminiAPIError(f"Failed to parse Gemini response: {str(e)}") from e

    # Normalize: ensure all expected keys exist with numeric defaults
    keys_numeric = [
        "calories", "protein", "fat", "saturated_fat", "trans_fat",
        "carbohydrates", "fiber", "sugar", "cholesterol", "sodium",
        "calcium", "iron", "potassium", "zinc",
        "vitaminA", "vitaminC", "vitaminD", "vitaminE", "vitaminK",
    ]
    normalized = {k: float(result.get(k, 0) or 0) for k in keys_numeric}
    normalized["food_name"] = (result.get("food_name") or "").strip()
    normalized["estimated_grams"] = float(result.get("estimated_grams", 0) or 0)
    return normalized


class SpoonacularAPIError(Exception):
    """Custom exception for Spoonacular API errors"""


class SpoonacularDataError(Exception):
    """Custom exception for Spoonacular data parsing errors"""


def get_spoonacular_data(food_name: str):
    """
    Get nutrition data from Spoonacular API for a given food name.
    Uses complexSearch endpoint with addRecipeNutrition=true to get nutrition info.
    
    Args:
        food_name: Name of the food to search for
        
    Returns:
        Dictionary with nutrition data
        
    Raises:
        SpoonacularAPIError: If API request fails
        SpoonacularDataError: If data parsing fails
    """
    url = "https://api.spoonacular.com/recipes/complexSearch"
    params = {
        "query": food_name,
        "number": 1,
        "addRecipeNutrition": "true",
        "apiKey": SPOONACULAR_API_KEY
    }

    try:
        response = rq.get(url, params=params, timeout=30)
    except rq.exceptions.RequestException as e:
        raise SpoonacularAPIError(f"Spoonacular API request failed: {str(e)}") from e
    
    if response.status_code != 200:
        error_text = response.text[:200] if response.text else "No error details"
        raise SpoonacularAPIError(f"Spoonacular API error: {response.status_code} - {error_text}")

    try:
        result = response.json()
    except ValueError as e:
        raise SpoonacularDataError(f"Invalid JSON response from Spoonacular API: {str(e)}") from e

    results = result.get("results", [])
    
    if not results:
        raise SpoonacularDataError(f"No results found for food: {food_name}")

    recipe = results[0]
    nutrition = recipe.get("nutrition", {})
    
    if not nutrition:
        raise SpoonacularDataError(f"No nutrition data found for food: {food_name}")
    
    nutrients = nutrition.get("nutrients", [])

    if not nutrients:
        raise SpoonacularDataError(f"No nutrients found in nutrition data for food: {food_name}")

    # Extract nutrition values using helper function
    nutrition_data = extract_nutrition_data(nutrients)
    nutrition_data["food_name"] = recipe.get("title", food_name)
    
    return nutrition_data


def get_spoonacular_recipe_by_id(recipe_id: int):
    """
    Get nutrition data from Spoonacular API by recipe ID.
    Uses recipe information endpoint with includeNutrition=true.
    
    Args:
        recipe_id: Spoonacular recipe ID
        
    Returns:
        Dictionary with nutrition data
        
    Raises:
        SpoonacularAPIError: If API request fails
        SpoonacularDataError: If data parsing fails
    """
    url = f"https://api.spoonacular.com/recipes/{recipe_id}/information"
    params = {
        "includeNutrition": "true",
        "apiKey": SPOONACULAR_API_KEY
    }

    try:
        response = rq.get(url, params=params, timeout=30)
    except rq.exceptions.RequestException as e:
        raise SpoonacularAPIError(f"Spoonacular API request failed: {str(e)}") from e
    
    if response.status_code != 200:
        error_text = response.text[:200] if response.text else "No error details"
        raise SpoonacularAPIError(f"Spoonacular API error: {response.status_code} - {error_text}")

    try:
        recipe = response.json()
    except ValueError as e:
        raise SpoonacularDataError(f"Invalid JSON response from Spoonacular API: {str(e)}") from e

    nutrition = recipe.get("nutrition", {})
    
    if not nutrition:
        raise SpoonacularDataError(f"No nutrition data found for recipe ID: {recipe_id}")
    
    nutrients = nutrition.get("nutrients", [])

    if not nutrients:
        raise SpoonacularDataError(f"No nutrients found in nutrition data for recipe ID: {recipe_id}")

    # Extract nutrition values using helper function
    nutrition_data = extract_nutrition_data(nutrients)
    nutrition_data["food_name"] = recipe.get("title", f"Recipe {recipe_id}")

    return nutrition_data


@extend_schema(
    request=FoodRecognitionRequestSerializer,
    responses={
        201: OpenApiResponse(
            description="Successfully recognized food and saved to database",
            examples=[
                OpenApiExample(
                    'Success',
                    value={
                        "id": 15,
                        "food_name": "pizza",
                        "calories": 266,
                        "protein": 11,
                        "carbohydrates": 33,
                        "fat": 10
                    }
                )
            ]
        ),
        # ... other error responses (400, 500) remain the same
    },
    tags=["Food"],
    summary="Recognize and Save Food",
    description="Uploads an image, recognizes the food, fetches nutrition data, and saves a FoodItem to the database."
)
class FoodRecognitionView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = 'food_scan'

    # Reject oversized uploads before reading them into memory / base64.
    MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB

    def post(self, request):
        serializer = FoodRecognitionRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        image_file = serializer.validated_data["image"]

        if getattr(image_file, "size", 0) > self.MAX_IMAGE_BYTES:
            return Response(
                {"error": "Image is too large. Maximum size is 8 MB."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        try:
            image_bytes = image_file.read()
            base64_image = base64.b64encode(image_bytes).decode("utf-8")

            # Recognize food + estimate nutrition in a single Gemini call.
            nutrition_data = predict_food_with_gemini(base64_image)

            if not nutrition_data.get("food_name"):
                return Response(
                    {"error": "No food detected in the image"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Step 3: Get meal_type if provided
            meal_type_id = serializer.validated_data.get("meal_type")
            meal_type_name = serializer.validated_data.get("meal_type_name")
            meal_type = resolve_meal_type(meal_type_id, meal_type_name)

            # Step 4: Create FoodItem object
            # We use request.user because permission_classes=[IsAuthenticated]
            food_item = FoodItem.objects.create(  # pylint: disable=no-member
                user=request.user,
                name=nutrition_data['food_name'],
                calories=nutrition_data['calories'],
                protein=nutrition_data['protein'],
                carbohydrates=nutrition_data['carbohydrates'],
                fats=nutrition_data['fat'], # Note: Model field is 'fats', helper key is 'fat'
                meal_type=meal_type  # Can be None if not provided
            )

            # Prepare response data (combine API data with the new DB ID)
            response_data = nutrition_data.copy()
            response_data['id'] = food_item.id
            response_data['name'] = food_item.name  # Add 'name' field for consistency with FoodItemSerializer
            response_data['created_at'] = food_item.date

            return Response(response_data, status=status.HTTP_201_CREATED)

        except (KeyError, ValueError) as e:
            logger.warning("Food recognition data error: %s", e)
            return Response({"error": "Could not process the recognition result."}, status=status.HTTP_502_BAD_GATEWAY)
        except GeminiAPIError as e:
            logger.error("Gemini API error: %s", e)
            return Response({"error": "Food recognition service is unavailable. Try again."}, status=status.HTTP_502_BAD_GATEWAY)
        except (SpoonacularAPIError, SpoonacularDataError) as e:
            logger.error("Spoonacular error: %s", e)
            return Response({"error": "Nutrition lookup failed. Try again."}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:  # pylint: disable=broad-except
            # Log the full traceback server-side; never leak internals to clients.
            logger.exception("Unexpected error in FoodRecognitionView")
            return Response(
                {"error": "Something went wrong while processing the image."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema(
    request=AddRecipeRequestSerializer,
    responses={
        201: OpenApiResponse(
            description="Successfully added recipe to database",
            examples=[
                OpenApiExample(
                    'Success',
                    value={
                        "id": 16,
                        "food_name": "Pasta Carbonara",
                        "calories": 450,
                        "protein": 20,
                        "carbohydrates": 55,
                        "fat": 15
                    }
                )
            ]
        ),
    },
    tags=["Food"],
    summary="Add Recipe from Spoonacular",
    description="Adds a recipe from Spoonacular by recipe ID to the user's food log. Optionally specify meal type."
)
class AddRecipeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = 'recipe_search'

    def post(self, request):
        serializer = AddRecipeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        recipe_id = serializer.validated_data["recipe_id"]
        meal_type_id = serializer.validated_data.get("meal_type")
        meal_type_name = serializer.validated_data.get("meal_type_name")

        try:
            # Step 1: Get nutrition data from Spoonacular by recipe ID
            nutrition_data = get_spoonacular_recipe_by_id(recipe_id)

            # Step 2: Get meal_type if provided
            meal_type = resolve_meal_type(meal_type_id, meal_type_name)

            # Step 3: Create FoodItem object
            food_item = FoodItem.objects.create(  # pylint: disable=no-member
                user=request.user,
                name=nutrition_data['food_name'],
                calories=nutrition_data['calories'],
                protein=nutrition_data['protein'],
                carbohydrates=nutrition_data['carbohydrates'],
                fats=nutrition_data['fat'],
                meal_type=meal_type,
                trans_fat=nutrition_data['trans_fat'],
                saturated_fat=nutrition_data['saturated_fat'],
                vitamin_a=nutrition_data['vitaminA'],
                vitamin_c=nutrition_data['vitaminC'],
                vitamin_d=nutrition_data['vitaminD'],
                vitamin_e=nutrition_data['vitaminE'],
                vitamin_k=nutrition_data['vitaminK'],
                mineral_calcium=nutrition_data['calcium'],
                mineral_iron=nutrition_data['iron'],
                mineral_sodium=nutrition_data['sodium'],
                mineral_potassium=nutrition_data['potassium'],
                mineral_zink=nutrition_data['zinc'],
            )

            # Prepare response data - EXACT same format as QR code scan process
            response_data = nutrition_data.copy()
            response_data['id'] = food_item.id
            response_data['name'] = food_item.name
            response_data['created_at'] = food_item.date
            # Note: Not including meal_type in response to match QR code format
            # meal_type is saved in DB but not in response, same as QR code process

            return Response(response_data, status=status.HTTP_201_CREATED)

        except (KeyError, ValueError) as e:
            logger.warning("Add-recipe data error: %s", e)
            return Response({"error": "Could not process the recipe data."}, status=status.HTTP_502_BAD_GATEWAY)
        except (SpoonacularAPIError, SpoonacularDataError) as e:
            logger.error("Spoonacular error: %s", e)
            return Response({"error": "Nutrition lookup failed. Try again."}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unexpected error in AddRecipeView")
            return Response(
                {"error": "Something went wrong while adding the recipe."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema(
    tags=["Food"],
    summary="Get food items by date",
    description="Retrieve a list of food items consumed by the user on a specific date, grouped by meal type (breakfast, lunch, snacks, dinner).",
    parameters=[
        OpenApiParameter(
            name='date', 
            description='Filter by date (Format: YYYY-MM-DD)', 
            required=True, 
            type=str
        ),
    ]
)
class FoodItemByDateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Start with all items belonging to the current user
        queryset = FoodItem.objects.filter(user=request.user)  # pylint: disable=no-member
        
        # 2. Get the date from URL parameters (e.g., ?date=2025-12-08)
        date_param = request.query_params.get('date')

        # 3. Apply the filter - if date provided use it, otherwise use today
        if date_param:
            try:
                target_date = parse_date(date_param)
                # Filter by date range (start of day to end of day)
                start_datetime = datetime.combine(target_date, datetime.min.time())
                end_datetime = start_datetime + timedelta(days=1)
                queryset = queryset.filter(date__gte=start_datetime, date__lt=end_datetime)
            except ValueError:
                # If date format is invalid, return error response
                return Response({
                    'error': f'Invalid date format: {date_param}. Supported formats: YYYY-MM-DD, M/D/YYYY, D/M/YYYY',
                    'breakfast': [],
                    'lunch': [],
                    'snacks': [],
                    'dinner': []
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            # If no date provided, default to today
            today = date.today()
            start_datetime = datetime.combine(today, datetime.min.time())
            end_datetime = start_datetime + timedelta(days=1)
            queryset = queryset.filter(date__gte=start_datetime, date__lt=end_datetime)
            
        queryset = queryset.order_by('-date').select_related('meal_type')
        
        # 4. Serialize and group food items by meal type
        serializer = FoodItemSerializer(queryset, many=True)
        grouped_data = group_food_items_by_meal_type(serializer.data)
        
        return Response(grouped_data, status=status.HTTP_200_OK)
    

@extend_schema(
    tags=["Food"],
    summary="Update meal type",
    description="Update the meal type (Breakfast, Lunch, etc.) for a specific food item entry.",
)
class FoodItemUpdateView(generics.UpdateAPIView):
    serializer_class = FoodItemUpdateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only update their own items
        return FoodItem.objects.filter(user=self.request.user)  # pylint: disable=no-member
    

@extend_schema(
    tags=["Food"],
    summary="Delete a food item",
    description="Deletes a specific food item log. This action cannot be undone."
)
class FoodItemDeleteView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        # Users can only delete their own items
        return FoodItem.objects.filter(user=self.request.user)  # pylint: disable=no-member


@extend_schema(
    tags=["Water Intake"],
    summary="Log water intake",
    description="Creates a new water intake record for the current user (defaults to today's date)."
)
class WaterIntakeCreateView(generics.CreateAPIView):
    queryset = WaterIntake.objects.all()
    serializer_class = WaterIntakeSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        # 1. Check if intake_type was provided in the request body
        intake_type = serializer.validated_data.get('intake_type')

        # 2. If not provided, try to use the user's preference
        if not intake_type:
            intake_type = user.water_intake_type_preference
            
        # 3. If still no intake_type, raise an error
        if not intake_type:
            raise ValidationError(
                {"intake_type": "No intake type provided and no user preference set."}
            )

        serializer.save(user=user, intake_type=intake_type)


@extend_schema(
    tags=["Water Intake"],
    summary="Delete water intake log",
    description="Deletes a specific water intake record."
)
class WaterIntakeDeleteView(generics.DestroyAPIView):
    serializer_class = WaterIntakeSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        # Ensure user can only delete their own records
        return WaterIntake.objects.filter(user=self.request.user)  # pylint: disable=no-member
    

@extend_schema(
    tags=["Water Intake"],
    summary="Get total water intake in Liters",
    description="Returns the total water consumed on a specific date in Liters (formatted to 2 decimal places).",
    parameters=[
        OpenApiParameter(
            name='date',
            description='Filter by date (Format: YYYY-MM-DD). Defaults to today if not provided.',
            required=False,
            type=str
        ),
    ],
    responses={
        200: OpenApiExample(
            'Success',
            value={"date": "2025-12-09", "total_liters": "2.50"}
        )
    }
)
class WaterIntakeDailyTotalView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Get the date from params, or default to today
        date_param = request.query_params.get('date')
        
        if date_param:
            try:
                target_date = parse_date(date_param)
            except ValueError:
                return Response({
                    'error': f'Invalid date format: {date_param}. Supported formats: YYYY-MM-DD, M/D/YYYY, D/M/YYYY'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            target_date = date.today()

        # 2. Filter by user and date, get logs and aggregate
        logs_qs = WaterIntake.objects.filter(  # pylint: disable=no-member
            user=request.user,
            date=target_date
        ).select_related('intake_type').order_by('-id')

        aggregation = logs_qs.aggregate(total_ml=Sum('intake_type__amount_ml'))
        total_ml = aggregation['total_ml'] or 0
        total_liters = total_ml / 1000

        # 3. Get user goal (ml) — default to 2000 if not set
        goal_ml = request.user.water_intake_goal_ml or 2000
        progress = min(round((total_ml / goal_ml) * 100, 2), 100) if goal_ml else 0

        # 4. Serialize today's logs so client can show/delete them
        logs = [
            {
                "id": log.id,
                "intake_type_id": log.intake_type_id,
                "intake_type_name": log.intake_type.name if log.intake_type else None,
                "amount_ml": log.intake_type.amount_ml if log.intake_type else 0,
            }
            for log in logs_qs
        ]

        return Response({
            "date": str(target_date),
            "total_ml": total_ml,
            "total_liters": f"{total_liters:.2f}",
            "water_intake_goal_ml": goal_ml,
            "progress_percent": progress,
            "logs": logs,
        })

@extend_schema(
    methods=['GET'], # Ensures this schema only applies to the GET method
    tags=["Food Statistics"],
    summary="Get daily nutritional statistics",
    description="Returns aggregated calories, macros, vitamins, and minerals for a specific date.",
    parameters=[
        OpenApiParameter(
            name='date',
            description='Filter by date (Format: YYYY-MM-DD). Defaults to today if not provided.',
            required=False,
            type=str
        ),
    ],
    responses={
        200: OpenApiExample(
            'Success',
            value={
                "overall": {
                    "calories": 250.00,
                    "protein": 5.00,
                    "carbohydrates": 30.00,
                    "fats": 10.00
                },
                "vitamins": {
                    "vitamin_a": 500.00,
                    "vitamin_c": 20.00,
                    "vitamin_d": 2.00,
                    "vitamin_e": 3.00,
                    "vitamin_k": 15.00
                },
                "minerals": {
                    "mineral_calcium": 100.00,
                    "mineral_iron": 2.00,
                    "mineral_sodium": 150.00,
                    "mineral_potassium": 300.00,
                    "mineral_zink": 1.00
                }
            }
        )
    }
)
class DailyStatsView(APIView):
    permission_classes = [IsAuthenticated]
    queryset = FoodItem.objects.none()
    def get(self, request):
        # Filter for today's food items for the logged-in user
        today = timezone.now().date()
        queryset = FoodItem.objects.filter(
            user=request.user, 
            date__date=today
        )

        # Aggregate all fields in one query
        stats = queryset.aggregate(
            total_calories=Sum('calories'),
            total_protein=Sum('protein'),
            total_carbohydrates=Sum('carbohydrates'),
            total_fats=Sum('fats'),
            total_a=Sum('vitamin_a'),
            total_c=Sum('vitamin_c'),
            total_d=Sum('vitamin_d'),
            total_e=Sum('vitamin_e'),
            total_k=Sum('vitamin_k'),
            total_calcium=Sum('mineral_calcium'),
            total_iron=Sum('mineral_iron'),
            total_sodium=Sum('mineral_sodium'),
            total_potassium=Sum('mineral_potassium'),
            total_zink=Sum('mineral_zink'),
        )

        # Format the response to match your JSON structure
        # Use 'or 0' to handle cases where no items are logged yet (returning 0 instead of null)
        data = {
            "overall": {
                "calories": stats['total_calories'] or 0,
                "protein": stats['total_protein'] or 0,
                "carbohydrates": stats['total_carbohydrates'] or 0,
                "fats": stats['total_fats'] or 0
            },
            "vitamins": {
                "vitamin_a": stats['total_a'] or 0,
                "vitamin_c": stats['total_c'] or 0,
                "vitamin_d": stats['total_d'] or 0,
                "vitamin_e": stats['total_e'] or 0,
                "vitamin_k": stats['total_k'] or 0
            },
            "minerals": {
                "mineral_calcium": stats['total_calcium'] or 0,
                "mineral_iron": stats['total_iron'] or 0,
                "mineral_sodium": stats['total_sodium'] or 0,
                "mineral_potassium": stats['total_potassium'] or 0,
                "mineral_zink": stats['total_zink'] or 0
            }
        }

        return Response(data)


@extend_schema(
    methods=['GET'],
    tags=["Food Statistics"],
    summary="Get current week nutritional statistics",
    description="Returns aggregated nutritional data from the start of the current week (Monday) to today.",
    responses={
        200: OpenApiExample(
            'Success',
            value={
                "week_range": "2026-01-05 to 2026-01-11",
                "overall": {"calories": 12500.0, "protein": 450.0, "carbohydrates": 1500.0, "fats": 350.0},
                "vitamins": {"vitamin_a": 3500.0, "vitamin_c": 150.0, "vitamin_d": 14.0, "vitamin_e": 21.0, "vitamin_k": 105.0},
                "minerals": {"mineral_calcium": 700.0, "mineral_iron": 14.0, "mineral_sodium": 1050.0, "mineral_potassium": 2100.0, "mineral_zink": 7.0}
            }
        )
    }
)
class WeeklyFoodStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = date.today()
        # Find the start of the week (Monday)
        # weekday() returns 0 for Monday, 6 for Sunday
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        # Aggregate data between start_of_week and today
        stats = FoodItem.objects.filter(
            user=request.user,
            date__date__range=[start_of_week, today]
        ).aggregate(
            cal=Sum('calories'), pro=Sum('protein'), carb=Sum('carbohydrates'), fat=Sum('fats'),
            v_a=Sum('vitamin_a'), v_c=Sum('vitamin_c'), v_d=Sum('vitamin_d'),
            v_e=Sum('vitamin_e'), v_k=Sum('vitamin_k'),
            m_ca=Sum('mineral_calcium'), m_fe=Sum('mineral_iron'),
            m_na=Sum('mineral_sodium'), m_k=Sum('mineral_potassium'), m_zn=Sum('mineral_zink')
        )

        # Per-day breakdown (Mon..Sun)
        day_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        days_payload = []
        for i in range(7):
            current = start_of_week + timedelta(days=i)
            day_stats = FoodItem.objects.filter(
                user=request.user,
                date__date=current
            ).aggregate(
                cal=Sum('calories'),
                pro=Sum('protein'),
                carb=Sum('carbohydrates'),
                fat=Sum('fats'),
            )
            days_payload.append({
                "date": current.isoformat(),
                "day_label": day_labels[i],
                "calories": float(day_stats['cal'] or 0),
                "protein": float(day_stats['pro'] or 0),
                "carbohydrates": float(day_stats['carb'] or 0),
                "fats": float(day_stats['fat'] or 0),
            })

        return Response({
            "week_range": f"{start_of_week} to {end_of_week}",
            "overall": {
                "calories": stats['cal'] or 0,
                "protein": stats['pro'] or 0,
                "carbohydrates": stats['carb'] or 0,
                "fats": stats['fat'] or 0
            },
            "days": days_payload,
            "vitamins": {
                "vitamin_a": stats['v_a'] or 0,
                "vitamin_c": stats['v_c'] or 0,
                "vitamin_d": stats['v_d'] or 0,
                "vitamin_e": stats['v_e'] or 0,
                "vitamin_k": stats['v_k'] or 0
            },
            "minerals": {
                "mineral_calcium": stats['m_ca'] or 0,
                "mineral_iron": stats['m_fe'] or 0,
                "mineral_sodium": stats['m_na'] or 0,
                "mineral_potassium": stats['m_k'] or 0,
                "mineral_zink": stats['m_zn'] or 0
            }
        })


@extend_schema(
    methods=['GET'],
    tags=["Food Statistics"],
    summary="Get nutritional statistics for a custom range",
    description="Returns aggregated nutritional data between a start_date and an end_date.",
    parameters=[
        OpenApiParameter(name='start_date', description='Start date (YYYY-MM-DD)', required=True, type=str),
        OpenApiParameter(name='end_date', description='End date (YYYY-MM-DD)', required=True, type=str),
    ],
    responses={
        200: OpenApiExample(
            'Success',
            value={
                "range": {"start": "2026-01-01", "end": "2026-01-07"},
                "overall": {"calories": 15000.0, "protein": 600.0, "carbohydrates": 1800.0, "fats": 400.0},
                "vitamins": {"vitamin_a": 4000.0, "vitamin_c": 200.0, "vitamin_d": 15.0, "vitamin_e": 25.0, "vitamin_k": 120.0},
                "minerals": {"mineral_calcium": 800.0, "mineral_iron": 15.0, "mineral_sodium": 1200.0, "mineral_potassium": 2500.0, "mineral_zink": 8.0}
            }
        ),
        400: OpenApiExample('Error', value={"error": "Invalid date format. Use YYYY-MM-DD."})
    }
)
class RangeFoodStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Get parameters
        start_str = request.query_params.get('start_date')
        end_str = request.query_params.get('end_date')

        # 2. Validate parameters
        if not start_str or not end_str:
            return Response(
                {"error": "Both start_date and end_date are required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start_date = parse_date(start_str)
            end_date = parse_date(end_str)
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if start_date > end_date:
            return Response(
                {"error": "start_date cannot be after end_date."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Aggregate data across the range
        stats = FoodItem.objects.filter(
            user=request.user,
            date__date__range=[start_date, end_date]
        ).aggregate(
            cal=Sum('calories'), pro=Sum('protein'), carb=Sum('carbohydrates'), fat=Sum('fats'),
            v_a=Sum('vitamin_a'), v_c=Sum('vitamin_c'), v_d=Sum('vitamin_d'), 
            v_e=Sum('vitamin_e'), v_k=Sum('vitamin_k'),
            m_ca=Sum('mineral_calcium'), m_fe=Sum('mineral_iron'), 
            m_na=Sum('mineral_sodium'), m_k=Sum('mineral_potassium'), m_zn=Sum('mineral_zink')
        )

        # 4. Return nested response
        data = {
            "range": {
                "start": start_str,
                "end": end_str
            },
            "overall": {
                "calories": stats['cal'] or 0,
                "protein": stats['pro'] or 0,
                "carbohydrates": stats['carb'] or 0,
                "fats": stats['fat'] or 0
            },
            "vitamins": {
                "vitamin_a": stats['v_a'] or 0,
                "vitamin_c": stats['v_c'] or 0,
                "vitamin_d": stats['v_d'] or 0,
                "vitamin_e": stats['v_e'] or 0,
                "vitamin_k": stats['v_k'] or 0
            },
            "minerals": {
                "mineral_calcium": stats['m_ca'] or 0,
                "mineral_iron": stats['m_fe'] or 0,
                "mineral_sodium": stats['m_na'] or 0,
                "mineral_potassium": stats['m_k'] or 0,
                "mineral_zink": stats['m_zn'] or 0
            }
        }
        serializer = FoodStatsResponseSerializer(data)
        return Response(serializer.data)


@extend_schema(
    methods=['GET'],
    tags=["Water Intake"],
    summary="List water intake types",
    description="Retrieve a list of all available water intake types (e.g., 200ml, 500ml)."
)
class WaterIntakeTypeListView(generics.ListAPIView):
    """
    View to list all available water intake types (e.g., 200ml, 500ml).
    """
    queryset = WaterIntakeType.objects.all()  # pylint: disable=no-member
    serializer_class = WaterIntakeTypeSerializer
    permission_classes = [AllowAny]

@extend_schema(
    methods=['PATCH'],
    tags=["Water Intake"],
    summary="Set water intake type preference",
    description="Updates the logged-in user's preferred water intake container/type.",
    request=WaterIntakePreferenceSerializer,
    responses={
        200: OpenApiExample(
            'Success',
            value={"message": "Water intake preference updated successfully.", "type_id": 1}
        ),
        400: OpenApiExample(
            'Error',
            value={"water_intake_type_id": ["Invalid pk \"999\" - object does not exist."]}
        )
    }
)
class SetWaterIntakePreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        # Initialize serializer with request data and current user instance
        serializer = WaterIntakePreferenceSerializer(data=request.data)
        
        if serializer.is_valid():
            # Update the user field
            user = request.user
            user.water_intake_type_preference = serializer.validated_data['water_intake_type_preference']
            user.save()
            
            return Response({
                "message": "Water intake preference updated successfully.",
                "type_id": user.water_intake_type_preference.id
            }, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class MealTypeListView(generics.ListAPIView):
    """
    View to list all meal types (e.g., Breakfast, Lunch, Dinner, Snacks).
    """
    queryset = MealType.objects.all()  # pylint: disable=no-member
    serializer_class = MealTypeListSerializer
    permission_classes = [IsAuthenticated]

@extend_schema(
    tags=['Water Intake'],
    summary="Update water intake goal and preference",
    description="Updates the authenticated user's water goal (ml) and type preference.",
    # Define the request body example
    request=WaterIntakePreferenceGoalUpdateSerializer,
    examples=[
        OpenApiExample(
            'Valid Request Example',
            value={
                'water_intake_goal_ml': 2500,
                'water_intake_type_preference': 1 # Assuming ID of WaterIntakeType
            },
            request_only=True,
            response_only=False,
        ),
    ],
    # Define the response body example (usually the updated object)
    responses={
        200: WaterIntakePreferenceGoalUpdateSerializer,
    }
)
class WaterIntakeGoalPreferenceUpdateView(generics.UpdateAPIView):
    serializer_class = WaterIntakePreferenceGoalUpdateSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

# ---------------------------------------------------------------------------
# Spoonacular proxy (keeps the API key server-side, off the mobile binary)
# ---------------------------------------------------------------------------

class SpoonacularRecipeSearchView(APIView):
    """
    GET /food/recipes/search/?query=<term>&number=<n>
    Proxies Spoonacular complexSearch with nutrition included.
    """
    permission_classes = [IsAuthenticated]
    throttle_scope = 'recipe_search'

    def get(self, request):
        query = request.query_params.get('query', '').strip()
        number = request.query_params.get('number', '50')
        if not query:
            return Response({'detail': 'query is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            resp = rq.get(
                'https://api.spoonacular.com/recipes/complexSearch',
                params={
                    'query': query,
                    'number': number,
                    'addRecipeNutrition': 'true',
                    'apiKey': SPOONACULAR_API_KEY,
                },
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning('Spoonacular search error %s: %s', resp.status_code, resp.text[:200])
                return Response({'detail': 'Upstream error', 'status': resp.status_code},
                                status=status.HTTP_502_BAD_GATEWAY)
            return Response(resp.json(), status=status.HTTP_200_OK)
        except rq.RequestException as e:
            logger.exception('Spoonacular search exception: %s', e)
            return Response({'detail': 'Network error'}, status=status.HTTP_502_BAD_GATEWAY)


class SpoonacularRecipeDetailView(APIView):
    """
    GET /food/recipes/<int:recipe_id>/
    Proxies Spoonacular recipe information (with nutrition).
    """
    permission_classes = [IsAuthenticated]
    throttle_scope = 'recipe_search'

    def get(self, request, recipe_id):
        try:
            resp = rq.get(
                f'https://api.spoonacular.com/recipes/{recipe_id}/information',
                params={
                    'apiKey': SPOONACULAR_API_KEY,
                    'includeNutrition': 'true',
                },
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning('Spoonacular detail error %s: %s', resp.status_code, resp.text[:200])
                return Response({'detail': 'Upstream error', 'status': resp.status_code},
                                status=status.HTTP_502_BAD_GATEWAY)
            return Response(resp.json(), status=status.HTTP_200_OK)
        except rq.RequestException as e:
            logger.exception('Spoonacular detail exception: %s', e)
            return Response({'detail': 'Network error'}, status=status.HTTP_502_BAD_GATEWAY)
