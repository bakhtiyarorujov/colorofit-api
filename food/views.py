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


def get_spoonacular_nutrition_from_image(image_bytes: bytes):
    """
    Spoonacular API istifadə edərək şəkildən makro və mikro elementləri alır.
    """
    url = "https://api.spoonacular.com/recipes/guessNutrition"
    
    files = {
        'file': ('image.jpg', image_bytes, 'image/jpeg')
    }
    
    params = {
        'apiKey': SPOONACULAR_API_KEY
    }
    
    response = rq.post(url, files=files, params=params)
    
    if response.status_code != 200:
        raise Exception(f"Spoonacular API error: {response.status_code} - {response.text}")
    
    result = response.json()
    
    # Spoonacular-dan gələn məlumatları formatla
    calories = result.get("calories", {}).get("value", 0)
    protein = result.get("protein", {}).get("value", 0)
    fat = result.get("fat", {}).get("value", 0)
    carbs = result.get("carbs", {}).get("value", 0)
    
    # Mikro elementlər
    vitamins = result.get("vitamins", {})
    minerals = result.get("minerals", {})
    
    # Vitaminlər
    vitamin_a = vitamins.get("A", {}).get("value", 0) if vitamins.get("A") else 0
    vitamin_c = vitamins.get("C", {}).get("value", 0) if vitamins.get("C") else 0
    vitamin_d = vitamins.get("D", {}).get("value", 0) if vitamins.get("D") else 0
    vitamin_e = vitamins.get("E", {}).get("value", 0) if vitamins.get("E") else 0
    vitamin_k = vitamins.get("K", {}).get("value", 0) if vitamins.get("K") else 0
    vitamin_b1 = vitamins.get("B1", {}).get("value", 0) if vitamins.get("B1") else 0
    vitamin_b2 = vitamins.get("B2", {}).get("value", 0) if vitamins.get("B2") else 0
    vitamin_b3 = vitamins.get("B3", {}).get("value", 0) if vitamins.get("B3") else 0
    vitamin_b5 = vitamins.get("B5", {}).get("value", 0) if vitamins.get("B5") else 0
    vitamin_b6 = vitamins.get("B6", {}).get("value", 0) if vitamins.get("B6") else 0
    vitamin_b12 = vitamins.get("B12", {}).get("value", 0) if vitamins.get("B12") else 0
    folate = vitamins.get("FOLATE", {}).get("value", 0) if vitamins.get("FOLATE") else 0
    
    # Minerallar
    calcium = minerals.get("CA", {}).get("value", 0) if minerals.get("CA") else 0
    iron = minerals.get("FE", {}).get("value", 0) if minerals.get("FE") else 0
    magnesium = minerals.get("MG", {}).get("value", 0) if minerals.get("MG") else 0
    phosphorus = minerals.get("P", {}).get("value", 0) if minerals.get("P") else 0
    potassium = minerals.get("K", {}).get("value", 0) if minerals.get("K") else 0
    sodium = minerals.get("NA", {}).get("value", 0) if minerals.get("NA") else 0
    zinc = minerals.get("ZN", {}).get("value", 0) if minerals.get("ZN") else 0
    copper = minerals.get("CU", {}).get("value", 0) if minerals.get("CU") else 0
    manganese = minerals.get("MN", {}).get("value", 0) if minerals.get("MN") else 0
    selenium = minerals.get("SE", {}).get("value", 0) if minerals.get("SE") else 0
    
    # Əlavə makro elementlər
    fiber = result.get("fiber", {}).get("value", 0) if result.get("fiber") else 0
    sugar = result.get("sugar", {}).get("value", 0) if result.get("sugar") else 0
    saturated_fat = result.get("saturatedFat", {}).get("value", 0) if result.get("saturatedFat") else 0
    trans_fat = result.get("transFat", {}).get("value", 0) if result.get("transFat") else 0
    cholesterol = result.get("cholesterol", {}).get("value", 0) if result.get("cholesterol") else 0
    
    # Yemək adı
    food_name = result.get("title", "Unknown Food")
    
    return {
        "food_name": food_name,
        "name": food_name,  # Flutter app expects both 'food_name' and 'name'
        "calories": float(calories) if calories else 0,
        "protein": float(protein) if protein else 0,
        # Flutter app expects camelCase for some fields
        "fat": float(fat) if fat else 0,  # For database
        "totalFat": float(fat) if fat else 0,  # For Flutter app
        "saturated_fat": float(saturated_fat) if saturated_fat else 0,  # For database
        "saturatedFat": float(saturated_fat) if saturated_fat else 0,  # For Flutter app
        "trans_fat": float(trans_fat) if trans_fat else 0,  # For database
        "transFat": float(trans_fat) if trans_fat else 0,  # For Flutter app
        "carbohydrates": float(carbs) if carbs else 0,  # For database
        "carbs": float(carbs) if carbs else 0,  # For Flutter app
        "fiber": float(fiber) if fiber else 0,
        "sugar": float(sugar) if sugar else 0,
        "cholesterol": float(cholesterol) if cholesterol else 0,
        "sodium": float(sodium) if sodium else 0,
        # Vitaminlər
        "vitaminA": float(vitamin_a) if vitamin_a else 0,
        "vitaminC": float(vitamin_c) if vitamin_c else 0,
        "vitaminD": float(vitamin_d) if vitamin_d else 0,
        "vitaminE": float(vitamin_e) if vitamin_e else 0,
        "vitaminK": float(vitamin_k) if vitamin_k else 0,
        "vitaminB1": float(vitamin_b1) if vitamin_b1 else 0,
        "vitaminB2": float(vitamin_b2) if vitamin_b2 else 0,
        "vitaminB3": float(vitamin_b3) if vitamin_b3 else 0,
        "vitaminB5": float(vitamin_b5) if vitamin_b5 else 0,
        "vitaminB6": float(vitamin_b6) if vitamin_b6 else 0,
        "vitaminB12": float(vitamin_b12) if vitamin_b12 else 0,
        "folate": float(folate) if folate else 0,
        # Minerallar
        "calcium": float(calcium) if calcium else 0,
        "iron": float(iron) if iron else 0,
        "magnesium": float(magnesium) if magnesium else 0,
        "phosphorus": float(phosphorus) if phosphorus else 0,
        "potassium": float(potassium) if potassium else 0,
        "zinc": float(zinc) if zinc else 0,
        "copper": float(copper) if copper else 0,
        "manganese": float(manganese) if manganese else 0,
        "selenium": float(selenium) if selenium else 0,
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
            
            # Spoonacular API istifadə edərək şəkildən birbaşa makro və mikro elementləri al
            nutrition_data = get_spoonacular_nutrition_from_image(image_bytes)

            # FoodItem object yarat
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
            response_data['name'] = nutrition_data['food_name']  # Flutter app expects 'name' field
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