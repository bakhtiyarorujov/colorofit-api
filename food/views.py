import base64
from datetime import date
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse, OpenApiParameter
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
import requests as rq
from .models import FoodItem, WaterIntake, MealType
from rest_framework.permissions import IsAuthenticated
from .serializers import FoodRecognitionRequestSerializer, FoodItemSerializer, FoodItemUpdateSerializer \
    , WaterIntakeSerializer, AddRecipeRequestSerializer
from django.db.models import Sum
from django.contrib.auth import get_user_model

CLARIFAI_MODEL_URL = "https://clarifai.com/clarifai/main/models/food-item-recognition"
CLARIFAI_PAT = "c4b6fbbfd9384b92a35be2a0de5e97ab" 
SPOONACULAR_API_KEY = "1a5198d38ce94b5ca46b6dc2f8e31cf3"
# Create your views here.

User = get_user_model()





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

    response = rq.post(url, headers=headers, json=data, timeout=30)
    response.raise_for_status()
    return response.json()


class SpoonacularAPIError(Exception):
    """Custom exception for Spoonacular API errors"""


class SpoonacularDataError(Exception):
    """Custom exception for Spoonacular data parsing errors"""


def get_spoonacular_data(food_name: str):
    """
    Get nutrition data from Spoonacular API for a given food name.
    Uses complexSearch endpoint with addRecipeNutrition=true to get nutrition info.
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

    # Create a dictionary to map nutrient names to their values
    nutrient_map = {}
    for nutrient in nutrients:
        name = nutrient.get("name", "").lower()
        amount = nutrient.get("amount", 0)
        nutrient_map[name] = float(amount or 0)

    # Extract nutrition values with fallbacks
    return {
        "food_name": recipe.get("title", food_name),
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
        "vitaminA": nutrient_map.get("vitamin a", 0),
        "vitaminC": nutrient_map.get("vitamin c", 0),
    }


def get_spoonacular_recipe_by_id(recipe_id: int):
    """
    Get nutrition data from Spoonacular API by recipe ID.
    Uses recipe information endpoint with includeNutrition=true.
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

    # Create a dictionary to map nutrient names to their values
    nutrient_map = {}
    for nutrient in nutrients:
        name = nutrient.get("name", "").lower()
        amount = nutrient.get("amount", 0)
        nutrient_map[name] = float(amount or 0)

    # Extract nutrition values with fallbacks
    return {
        "food_name": recipe.get("title", f"Recipe {recipe_id}"),
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
        "vitaminA": nutrient_map.get("vitamin a", 0),
        "vitaminC": nutrient_map.get("vitamin c", 0),
    }


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

            food_name = concepts[0]["name"]

            # Step 2: Get nutrition data from Spoonacular
            nutrition_data = get_spoonacular_data(food_name)

            # Step 3: Create FoodItem object
            # We use request.user because permission_classes=[IsAuthenticated]
            food_item = FoodItem.objects.create(  # pylint: disable=no-member
                user=request.user,
                name=nutrition_data['food_name'],
                calories=nutrition_data['calories'],
                protein=nutrition_data['protein'],
                carbohydrates=nutrition_data['carbohydrates'],
                fats=nutrition_data['fat'], # Note: Model field is 'fats', helper key is 'fat'
                # meal_type is left null as it wasn't provided in the request
            )

            # Prepare response data (combine API data with the new DB ID)
            response_data = nutrition_data.copy()
            response_data['id'] = food_item.id
            response_data['name'] = food_item.name  # Add 'name' field for consistency with FoodItemSerializer
            response_data['created_at'] = food_item.date

            return Response(response_data, status=status.HTTP_201_CREATED)

        except (KeyError, ValueError) as e:
            return Response({"error": f"Data processing error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except (SpoonacularAPIError, SpoonacularDataError) as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:  # pylint: disable=broad-except
            # It is good practice to log the specific error here for debugging
            import traceback
            error_details = traceback.format_exc()
            return Response({
                "error": str(e),
                "details": error_details
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
            meal_type = None
            
            # First try to find by name (preferred method)
            if meal_type_name:
                meal_type_name_lower = meal_type_name.lower().strip()
                # Map frontend names to backend names
                meal_type_mapping = {
                    'breakfast': 'Breakfast',
                    'lunch': 'Lunch',
                    'snacks': 'Snacks',
                    'snack': 'Snacks',
                    'dinner': 'Dinner',
                }
                backend_meal_type_name = meal_type_mapping.get(meal_type_name_lower, meal_type_name)
                
                try:
                    meal_type = MealType.objects.get(name__iexact=backend_meal_type_name)  # pylint: disable=no-member
                except MealType.DoesNotExist:  # pylint: disable=no-member
                    # Meal type not found by name, will remain None (backend will default to snacks)
                    pass
            
            # If not found by name, try by ID (fallback)
            if meal_type is None and meal_type_id:
                try:
                    meal_type = MealType.objects.get(id=meal_type_id)  # pylint: disable=no-member
                except MealType.DoesNotExist:  # pylint: disable=no-member
                    # Meal type not found by ID, will remain None (backend will default to snacks)
                    pass

            # Step 3: Create FoodItem object
            food_item = FoodItem.objects.create(  # pylint: disable=no-member
                user=request.user,
                name=nutrition_data['food_name'],
                calories=nutrition_data['calories'],
                protein=nutrition_data['protein'],
                carbohydrates=nutrition_data['carbohydrates'],
                fats=nutrition_data['fat'],
                meal_type=meal_type
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
            return Response({"error": f"Data processing error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except (SpoonacularAPIError, SpoonacularDataError) as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:  # pylint: disable=broad-except
            import traceback
            error_details = traceback.format_exc()
            return Response({
                "error": str(e),
                "details": error_details
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
        from datetime import datetime, timedelta
        if date_param:
            # Parse the date string and filter by date (ignoring time)
            try:
                target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
                # Filter by date range (start of day to end of day)
                start_datetime = datetime.combine(target_date, datetime.min.time())
                end_datetime = start_datetime + timedelta(days=1)
                queryset = queryset.filter(date__gte=start_datetime, date__lt=end_datetime)
            except ValueError:
                # If date format is invalid, return empty result
                return Response({
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
        
        # 4. Group food items by meal type
        grouped_data = {
            'breakfast': [],
            'lunch': [],
            'snacks': [],
            'dinner': []
        }
        
        # Serialize each food item and group by meal type
        serializer = FoodItemSerializer(queryset, many=True)
        
        for item_data in serializer.data:
            meal_type_name = item_data.get('meal_type_name', '').lower() if item_data.get('meal_type_name') else None
            
            # Normalize meal type name to match our keys
            if meal_type_name:
                if 'breakfast' in meal_type_name:
                    grouped_data['breakfast'].append(item_data)
                elif 'lunch' in meal_type_name:
                    grouped_data['lunch'].append(item_data)
                elif 'snack' in meal_type_name:
                    grouped_data['snacks'].append(item_data)
                elif 'dinner' in meal_type_name:
                    grouped_data['dinner'].append(item_data)
                else:
                    # If meal type doesn't match, add to snacks as default
                    grouped_data['snacks'].append(item_data)
            else:
                # If no meal type, add to snacks as default
                grouped_data['snacks'].append(item_data)
        
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
    description="Creates a new water intake record for the current user (defaults to today's date).",
    examples=[
        OpenApiExample(
            'Example Request',
            value={"intake_type": 1}, # 1 is the ID of a WaterIntakeType (e.g. 200ml)
            request_only=True
        )
    ]
)
class WaterIntakeCreateView(generics.CreateAPIView):
    queryset = WaterIntake.objects.all()  # pylint: disable=no-member
    serializer_class = WaterIntakeSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        # Automatically assign the currently logged-in user
        serializer.save(user=self.request.user)


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
        target_date = date_param if date_param else date.today()

        # 2. Filter by user and date, then aggregate the sum of the related type's amount
        # We use 'intake_type__amount_ml' to follow the ForeignKey relationship
        aggregation = WaterIntake.objects.filter(  # pylint: disable=no-member
            user=request.user, 
            date=target_date
        ).aggregate(total_ml=Sum('intake_type__amount_ml'))

        # 3. Handle the result (result is None if no records exist)
        total_ml = aggregation['total_ml'] or 0
        
        # 4. Convert to Liters
        total_liters = total_ml / 1000

        # 5. Return formatted response (2 decimal places)
        return Response({
            "date": target_date,
            "total_liters": f"{total_liters:.2f}"
        })