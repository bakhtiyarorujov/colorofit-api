import base64
from datetime import date
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse, OpenApiParameter
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
import requests as rq
from .models import FoodItem, WaterIntake, WaterIntakeType
from rest_framework.permissions import IsAuthenticated
from .serializers import FoodRecognitionRequestSerializer, FoodItemSerializer, FoodItemUpdateSerializer \
    , WaterIntakeSerializer
from django.db.models import Sum
from django.contrib.auth import get_user_model

CLARIFAI_MODEL_URL = "https://clarifai.com/clarifai/main/models/food-item-recognition"
CLARIFAI_PAT = "c4b6fbbfd9384b92a35be2a0de5e97ab" 
NUTRITIONIX_APP_ID = "26d50180"
NUTRITIONIX_APP_KEY = "6e668f1850c515e975cb92818685fa82"
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

            # Step 2: Get nutrition data
            nutrition_data = get_nutritionix_data(food_name)

            # Step 3: Create FoodItem object
            # We use request.user because permission_classes=[IsAuthenticated]
            food_item = FoodItem.objects.create(
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
            response_data['created_at'] = food_item.date

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            # It is good practice to log the specific error here for debugging
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        queryset = FoodItem.objects.filter(user=request.user)
        
        # 2. Get the date from URL parameters (e.g., ?date=2025-12-08)
        date_param = request.query_params.get('date')

        # 3. Apply the filter if the date exists
        if date_param:
            # We use 'date__date' to ignore the time component and match only the day
            queryset = queryset.filter(date__date=date_param)
            
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
        return FoodItem.objects.filter(user=self.request.user)
    

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
        return FoodItem.objects.filter(user=self.request.user)


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
    queryset = WaterIntake.objects.all()
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
        return WaterIntake.objects.filter(user=self.request.user)
    

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
        aggregation = WaterIntake.objects.filter(
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