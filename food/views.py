import base64
import logging
from django.utils.dateparse import parse_date
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
from rest_framework.permissions import IsAuthenticated
from .serializers import (
    FoodRecognitionRequestSerializer, FoodItemSerializer, FoodItemUpdateSerializer,
    WaterIntakeSerializer, AddRecipeRequestSerializer, FoodStatsResponseSerializer,
    WaterIntakePreferenceSerializer, MealTypeListSerializer
)
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

# Constants
CLARIFAI_MODEL_URL = "https://clarifai.com/clarifai/main/models/food-item-recognition"
CLARIFAI_PAT = "c4b6fbbfd9384b92a35be2a0de5e97ab" 
SPOONACULAR_API_KEY = "1a5198d38ce94b5ca46b6dc2f8e31cf3"

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
    '%m/%d/%Y',      # 12/2/2026
    '%d/%m/%Y',      # 2/12/2026
    '%Y/%m/%d',      # 2026/12/02
]

User = get_user_model()

# --- Helper Functions ---

def parse_date_custom(date_string: str) -> date:
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(date_string, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {date_string}")

def resolve_meal_type(meal_type_id=None, meal_type_name=None):
    meal_type = None
    if meal_type_name:
        meal_type_name_lower = meal_type_name.lower().strip()
        backend_meal_type_name = MEAL_TYPE_MAPPING.get(meal_type_name_lower, meal_type_name)
        try:
            meal_type = MealType.objects.get(name__iexact=backend_meal_type_name)
        except MealType.DoesNotExist:
            logger.warning("Meal type not found by name: %s", backend_meal_type_name)
    if meal_type is None and meal_type_id:
        try:
            meal_type = MealType.objects.get(id=meal_type_id)
        except MealType.DoesNotExist:
            logger.warning("Meal type not found by ID: %s", meal_type_id)
    return meal_type

def group_food_items_by_meal_type(food_items_data):
    grouped_data = {'breakfast': [], 'lunch': [], 'snacks': [], 'dinner': []}
    for item_data in food_items_data:
        meal_type_name = item_data.get('meal_type_name', '').strip() if item_data.get('meal_type_name') else None
        if meal_type_name:
            name_lower = meal_type_name.lower()
            matched_key = MEAL_TYPE_GROUPING_MAP.get(name_lower)
            if matched_key:
                grouped_data[matched_key].append(item_data)
            else:
                grouped_data['snacks'].append(item_data)
        else:
            grouped_data['snacks'].append(item_data)
    return grouped_data

def extract_nutrition_data(nutrients):
    nutrient_map = {n.get("name", "").lower(): float(n.get("amount", 0) or 0) for n in nutrients}
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

def predict_clarifai_by_base64(base64_image: str, pat: str, model_id: str = "food-item-v1-recognition", app_id: str = "main"):
    url = f"https://api.clarifai.com/v2/models/{model_id}/outputs"
    headers = {"Authorization": f"Key {pat}", "Content-Type": "application/json"}
    data = {"user_app_id": {"user_id": "clarifai", "app_id": app_id}, "inputs": [{"data": {"image": {"base64": base64_image}}}]}
    response = rq.post(url, headers=headers, json=data, timeout=30)
    response.raise_for_status()
    return response.json()

class SpoonacularAPIError(Exception): pass
class SpoonacularDataError(Exception): pass

def get_spoonacular_data(food_name: str):
    url = "https://api.spoonacular.com/recipes/complexSearch"
    params = {"query": food_name, "number": 1, "addRecipeNutrition": "true", "apiKey": SPOONACULAR_API_KEY}
    response = rq.get(url, params=params, timeout=30)
    if response.status_code != 200: raise SpoonacularAPIError(f"Spoonacular error: {response.status_code}")
    result = response.json()
    results = result.get("results", [])
    if not results: raise SpoonacularDataError("No results found")
    recipe = results[0]
    nutrition = recipe.get("nutrition", {})
    nutrients = nutrition.get("nutrients", [])
    data = extract_nutrition_data(nutrients)
    data["food_name"] = recipe.get("title", food_name)
    return data

def get_spoonacular_recipe_by_id(recipe_id: int):
    url = f"https://api.spoonacular.com/recipes/{recipe_id}/information"
    params = {"includeNutrition": "true", "apiKey": SPOONACULAR_API_KEY}
    response = rq.get(url, params=params, timeout=30)
    if response.status_code != 200: raise SpoonacularAPIError("Spoonacular error")
    recipe = response.json()
    nutrients = recipe.get("nutrition", {}).get("nutrients", [])
    data = extract_nutrition_data(nutrients)
    data["food_name"] = recipe.get("title", f"Recipe {recipe_id}")
    return data

# --- Views ---

class FoodRecognitionView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = FoodRecognitionRequestSerializer(data=request.data)
        if not serializer.is_valid(): return Response(serializer.errors, status=400)
        try:
            image_bytes = serializer.validated_data["image"].read()
            base64_image = base64.b64encode(image_bytes).decode("utf-8")
            prediction = predict_clarifai_by_base64(base64_image, CLARIFAI_PAT)
            concepts = prediction["outputs"][0]["data"]["concepts"]
            if not concepts: return Response({"error": "No prediction"}, status=500)
            nutrition_data = get_spoonacular_data(concepts[0]["name"])
            meal_type = resolve_meal_type(serializer.validated_data.get("meal_type"), serializer.validated_data.get("meal_type_name"))
            food_item = FoodItem.objects.create(
                user=request.user, name=nutrition_data['food_name'],
                calories=nutrition_data['calories'], protein=nutrition_data['protein'],
                carbohydrates=nutrition_data['carbohydrates'], fats=nutrition_data['fat'],
                meal_type=meal_type
            )
            res = nutrition_data.copy()
            res.update({'id': food_item.id, 'name': food_item.name, 'created_at': food_item.date})
            return Response(res, status=201)
        except Exception as e: return Response({"error": str(e)}, status=500)

class AddRecipeView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = AddRecipeRequestSerializer(data=request.data)
        if not serializer.is_valid(): return Response(serializer.errors, status=400)
        try:
            nutrition_data = get_spoonacular_recipe_by_id(serializer.validated_data["recipe_id"])
            meal_type = resolve_meal_type(serializer.validated_data.get("meal_type"), serializer.validated_data.get("meal_type_name"))
            food_item = FoodItem.objects.create(
                user=request.user, name=nutrition_data['food_name'],
                calories=nutrition_data['calories'], protein=nutrition_data['protein'],
                carbohydrates=nutrition_data['carbohydrates'], fats=nutrition_data['fat'],
                meal_type=meal_type, trans_fat=nutrition_data['trans_fat'],
                saturated_fat=nutrition_data['saturated_fat'], vitamin_a=nutrition_data['vitaminA'],
                vitamin_c=nutrition_data['vitaminC'], vitamin_d=nutrition_data['vitaminD'],
                vitamin_e=nutrition_data['vitaminE'], vitamin_k=nutrition_data['vitaminK'],
                mineral_calcium=nutrition_data['calcium'], mineral_iron=nutrition_data['iron'],
                mineral_sodium=nutrition_data['sodium'], mineral_potassium=nutrition_data['potassium'],
                mineral_zink=nutrition_data['zinc'],
            )
            res = nutrition_data.copy()
            res.update({'id': food_item.id, 'name': food_item.name, 'created_at': food_item.date})
            return Response(res, status=201)
        except Exception as e: return Response({"error": str(e)}, status=500)

class FoodItemByDateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        date_param = request.query_params.get('date')
        queryset = FoodItem.objects.filter(user=request.user)
        try:
            target_date = parse_date_custom(date_param) if date_param else date.today()
            start = datetime.combine(target_date, datetime.min.time())
            end = start + timedelta(days=1)
            queryset = queryset.filter(date__gte=start, date__lt=end).order_by('-date').select_related('meal_type')
            serializer = FoodItemSerializer(queryset, many=True)
            return Response(group_food_items_by_meal_type(serializer.data))
        except ValueError: return Response({'error': 'Invalid date'}, status=400)

class FoodItemUpdateView(generics.UpdateAPIView):
    serializer_class = FoodItemUpdateSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return FoodItem.objects.filter(user=self.request.user)

class FoodItemDeleteView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return FoodItem.objects.filter(user=self.request.user)

class WaterIntakeCreateView(generics.CreateAPIView):
    serializer_class = WaterIntakeSerializer
    permission_classes = [IsAuthenticated]
    def perform_create(self, serializer):
        it = serializer.validated_data.get('intake_type') or self.request.user.water_intake_type_preference
        if not it: raise ValidationError({"intake_type": "No preference set."})
        serializer.save(user=self.request.user, intake_type=it)

class WaterIntakeDeleteView(generics.DestroyAPIView):
    serializer_class = WaterIntakeSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return WaterIntake.objects.filter(user=self.request.user)

class WaterIntakeDailyTotalView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        d_param = request.query_params.get('date')
        try:
            td = parse_date_custom(d_param) if d_param else date.today()
            agg = WaterIntake.objects.filter(user=request.user, date=td).aggregate(total=Sum('intake_type__amount_ml'))
            liters = (agg['total'] or 0) / 1000
            return Response({"date": str(td), "total_liters": f"{liters:.2f}"})
        except ValueError: return Response({'error': 'Invalid date'}, status=400)

class DailyStatsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        d_param = request.query_params.get('date')
        try:
            td = parse_date_custom(d_param) if d_param else timezone.now().date()
            stats = FoodItem.objects.filter(user=request.user, date__date=td).aggregate(
                cal=Sum('calories'), pro=Sum('protein'), carb=Sum('carbohydrates'), fat=Sum('fats'),
                va=Sum('vitamin_a'), vc=Sum('vitamin_c'), vd=Sum('vitamin_d'), ve=Sum('vitamin_e'), vk=Sum('vitamin_k'),
                ca=Sum('mineral_calcium'), fe=Sum('mineral_iron'), na=Sum('mineral_sodium'), k=Sum('mineral_potassium'), zn=Sum('mineral_zink')
            )
            return Response({
                "overall": {"calories": stats['cal'] or 0, "protein": stats['pro'] or 0, "carbohydrates": stats['carb'] or 0, "fats": stats['fat'] or 0},
                "vitamins": {"vitamin_a": stats['va'] or 0, "vitamin_c": stats['vc'] or 0, "vitamin_d": stats['vd'] or 0, "vitamin_e": stats['ve'] or 0, "vitamin_k": stats['vk'] or 0},
                "minerals": {"mineral_calcium": stats['ca'] or 0, "mineral_iron": stats['fe'] or 0, "mineral_sodium": stats['na'] or 0, "mineral_potassium": stats['k'] or 0, "mineral_zink": stats['zn'] or 0}
            })
        except ValueError: return Response({'error': 'Invalid date'}, status=400)

class WeeklyFoodStatsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        today = date.today()
        start = today - timedelta(days=today.weekday())
        stats = FoodItem.objects.filter(user=request.user, date__date__range=[start, today]).aggregate(
            cal=Sum('calories'), pro=Sum('protein'), carb=Sum('carbohydrates'), fat=Sum('fats'),
            va=Sum('vitamin_a'), vc=Sum('vitamin_c'), vd=Sum('vitamin_d'), ve=Sum('vitamin_e'), vk=Sum('vitamin_k'),
            ca=Sum('mineral_calcium'), fe=Sum('mineral_iron'), na=Sum('mineral_sodium'), k=Sum('mineral_potassium'), zn=Sum('mineral_zink')
        )
        return Response({
            "week_range": f"{start} to {today}",
            "overall": {"calories": stats['cal'] or 0, "protein": stats['pro'] or 0, "carbohydrates": stats['carb'] or 0, "fats": stats['fat'] or 0},
            "vitamins": {"vitamin_a": stats['va'] or 0, "vitamin_c": stats['vc'] or 0, "vitamin_d": stats['vd'] or 0, "vitamin_e": stats['ve'] or 0, "vitamin_k": stats['vk'] or 0},
            "minerals": {"mineral_calcium": stats['ca'] or 0, "mineral_iron": stats['fe'] or 0, "mineral_sodium": stats['na'] or 0, "mineral_potassium": stats['k'] or 0, "mineral_zink": stats['zn'] or 0}
        })

class RangeFoodStatsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        s_str, e_str = request.query_params.get('start_date'), request.query_params.get('end_date')
        if not s_str or not e_str: return Response({"error": "Dates required"}, status=400)
        try:
            s_d, e_d = parse_date_custom(s_str), parse_date_custom(e_str)
            stats = FoodItem.objects.filter(user=request.user, date__date__range=[s_d, e_d]).aggregate(
                cal=Sum('calories'), pro=Sum('protein'), carb=Sum('carbohydrates'), fat=Sum('fats'),
                va=Sum('vitamin_a'), vc=Sum('vitamin_c'), vd=Sum('vitamin_d'), ve=Sum('vitamin_e'), vk=Sum('vitamin_k'),
                ca=Sum('mineral_calcium'), fe=Sum('mineral_iron'), na=Sum('mineral_sodium'), k=Sum('mineral_potassium'), zn=Sum('mineral_zink')
            )
            data = {
                "range": {"start": s_str, "end": e_str},
                "overall": {"calories": stats['cal'] or 0, "protein": stats['pro'] or 0, "carbohydrates": stats['carb'] or 0, "fats": stats['fat'] or 0},
                "vitamins": {"vitamin_a": stats['va'] or 0, "vitamin_c": stats['vc'] or 0, "vitamin_d": stats['vd'] or 0, "vitamin_e": stats['ve'] or 0, "vitamin_k": stats['vk'] or 0},
                "minerals": {"mineral_calcium": stats['ca'] or 0, "mineral_iron": stats['fe'] or 0, "mineral_sodium": stats['na'] or 0, "mineral_potassium": stats['k'] or 0, "mineral_zink": stats['zn'] or 0}
            }
            return Response(FoodStatsResponseSerializer(data).data)
        except ValueError: return Response({'error': 'Invalid date'}, status=400)

class WaterIntakeTypeListView(generics.ListAPIView):
    queryset = WaterIntakeType.objects.all()
    serializer_class = WaterIntakeSerializer
    permission_classes = [IsAuthenticated]

class SetWaterIntakePreferenceView(APIView):
    permission_classes = [IsAuthenticated]
    def patch(self, request):
        serializer = WaterIntakePreferenceSerializer(data=request.data)
        if serializer.is_valid():
            request.user.water_intake_type_preference = serializer.validated_data['water_intake_type_preference']
            request.user.save()
            return Response({"message": "Updated", "type_id": request.user.water_intake_type_preference.id})
        return Response(serializer.errors, status=400)

class MealTypeListView(generics.ListAPIView):
    queryset = MealType.objects.all()
    serializer_class = MealTypeListSerializer
    permission_classes = [IsAuthenticated]