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
    'breakfast': 'Breakfast', 'lunch': 'Lunch', 'snacks': 'Snacks',
    'snack': 'Snacks', 'dinner': 'Dinner',
}

MEAL_TYPE_GROUPING_MAP = {
    'breakfast': 'breakfast', 'lunch': 'lunch', 'snacks': 'snacks',
    'snack': 'snacks', 'dinner': 'dinner',
}

DATE_FORMATS = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']

User = get_user_model()

# --- Helpers ---
def parse_date_custom(date_string: str) -> date:
    for f in DATE_FORMATS:
        try: return datetime.strptime(date_string, f).date()
        except ValueError: continue
    raise ValueError(f"Invalid date: {date_string}")

def resolve_meal_type(id=None, name=None):
    mt = None
    if name:
        n = MEAL_TYPE_MAPPING.get(name.lower().strip(), name)
        try: mt = MealType.objects.get(name__iexact=n)
        except MealType.DoesNotExist: pass
    if mt is None and id:
        try: mt = MealType.objects.get(id=id)
        except MealType.DoesNotExist: pass
    return mt

def group_food_items_by_meal_type(data):
    grouped = {'breakfast': [], 'lunch': [], 'snacks': [], 'dinner': []}
    for item in data:
        name = item.get('meal_type_name', '').lower() if item.get('meal_type_name') else ''
        key = MEAL_TYPE_GROUPING_MAP.get(name, 'snacks')
        grouped[key].append(item)
    return grouped

def extract_nutrition_data(nutrients):
    m = {n.get("name", "").lower(): float(n.get("amount", 0) or 0) for n in nutrients}
    return {
        "calories": m.get("calories", 0), "protein": m.get("protein", 0),
        "fat": m.get("fat", 0), "carbohydrates": m.get("carbohydrates", 0),
        "saturated_fat": m.get("saturated fat", 0), "trans_fat": m.get("trans fat", 0),
        "fiber": m.get("fiber", 0), "sugar": m.get("sugar", 0),
        "cholesterol": m.get("cholesterol", 0), "sodium": m.get("sodium", 0),
        "calcium": m.get("calcium", 0), "iron": m.get("iron", 0),
        "potassium": m.get("potassium", 0), "zinc": m.get("zinc", 0),
        "vitaminA": m.get("vitamin a", 0), "vitaminC": m.get("vitamin c", 0),
        "vitaminD": m.get("vitamin d", 0), "vitaminE": m.get("vitamin e", 0), "vitaminK": m.get("vitamin k", 0),
    }

# --- Views ---
class FoodRecognitionView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = FoodRecognitionRequestSerializer(data=request.data)
        if not serializer.is_valid(): return Response(serializer.errors, status=400)
        try:
            img = base64.b64encode(serializer.validated_data["image"].read()).decode("utf-8")
            url = "https://api.clarifai.com/v2/models/food-item-v1-recognition/outputs"
            headers = {"Authorization": f"Key {CLARIFAI_PAT}", "Content-Type": "application/json"}
            payload = {"user_app_id": {"user_id": "clarifai", "app_id": "main"}, "inputs": [{"data": {"image": {"base64": img}}}]}
            prediction = rq.post(url, headers=headers, json=payload, timeout=30).json()
            concepts = prediction["outputs"][0]["data"]["concepts"]
            if not concepts: return Response({"error": "No food found"}, status=500)
            
            # Spoonacular
            s_url = "https://api.spoonacular.com/recipes/complexSearch"
            s_params = {"query": concepts[0]["name"], "number": 1, "addRecipeNutrition": "true", "apiKey": SPOONACULAR_API_KEY}
            s_res = rq.get(s_url, params=s_params, timeout=30).json()
            if not s_res.get("results"): return Response({"error": "No nutrition found"}, status=500)
            
            recipe = s_res["results"][0]
            nutri = extract_nutrition_data(recipe.get("nutrition", {}).get("nutrients", []))
            mt = resolve_meal_type(serializer.validated_data.get("meal_type"), serializer.validated_data.get("meal_type_name"))
            
            food = FoodItem.objects.create(
                user=request.user, name=recipe.get("title", concepts[0]["name"]),
                calories=nutri['calories'], protein=nutri['protein'],
                carbohydrates=nutri['carbohydrates'], fats=nutri['fat'], meal_type=mt
            )
            res = nutri.copy()
            res.update({'id': food.id, 'name': food.name, 'created_at': food.date})
            return Response(res, status=201)
        except Exception as e: return Response({"error": str(e)}, status=500)

class FoodItemByDateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        d_param = request.query_params.get('date')
        try:
            td = parse_date_custom(d_param) if d_param else date.today()
            start = datetime.combine(td, datetime.min.time())
            qs = FoodItem.objects.filter(user=request.user, date__gte=start, date__lt=start+timedelta(days=1)).order_by('-date')
            data = FoodItemSerializer(qs, many=True).data
            # Decimal fix for SQLite
            for item in data:
                for f in ['calories', 'protein', 'carbohydrates', 'fats']:
                    if item.get(f) is not None: item[f] = float(item[f])
            return Response(group_food_items_by_meal_type(data))
        except Exception as e: return Response({'error': str(e)}, status=400)

class DailyStatsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        d_param = request.query_params.get('date')
        try:
            td = parse_date_custom(d_param) if d_param else timezone.now().date()
            s = FoodItem.objects.filter(user=request.user, date__date=td).aggregate(
                cal=Sum('calories'), pro=Sum('protein'), carb=Sum('carbohydrates'), fat=Sum('fats'),
                va=Sum('vitamin_a'), vc=Sum('vitamin_c'), vd=Sum('vitamin_d'), ve=Sum('vitamin_e'), vk=Sum('vitamin_k'),
                ca=Sum('mineral_calcium'), fe=Sum('mineral_iron'), na=Sum('mineral_sodium'), k=Sum('mineral_potassium'), zn=Sum('mineral_zink')
            )
            f = lambda v: round(float(v or 0), 2)
            return Response({
                "overall": {"calories": f(s['cal']), "protein": f(s['pro']), "carbohydrates": f(s['carb']), "fats": f(s['fat'])},
                "vitamins": {"vitamin_a": f(s['va']), "vitamin_c": f(s['vc']), "vitamin_d": f(s['vd']), "vitamin_e": f(s['ve']), "vitamin_k": f(s['vk'])},
                "minerals": {"mineral_calcium": f(s['ca']), "mineral_iron": f(s['fe']), "mineral_sodium": f(s['na']), "mineral_potassium": f(s['k']), "mineral_zink": f(s['zn'])}
            })
        except Exception as e: return Response({'error': str(e)}, status=400)

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
    def perform_create(self, s):
        it = s.validated_data.get('intake_type') or self.request.user.water_intake_type_preference
        if not it: raise ValidationError("No preference set")
        s.save(user=self.request.user, intake_type=it)

class WaterIntakeDeleteView(generics.DestroyAPIView):
    serializer_class = WaterIntakeSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return WaterIntake.objects.filter(user=self.request.user)

class WaterIntakeDailyTotalView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        d = parse_date_custom(request.query_params.get('date')) if request.query_params.get('date') else date.today()
        agg = WaterIntake.objects.filter(user=request.user, date=d).aggregate(t=Sum('intake_type__amount_ml'))
        return Response({"date": str(d), "total_liters": f"{(agg['t'] or 0)/1000:.2f}"})

class WeeklyFoodStatsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        today = date.today()
        start = today - timedelta(days=today.weekday())
        s = FoodItem.objects.filter(user=request.user, date__date__range=[start, today]).aggregate(
            cal=Sum('calories'), pro=Sum('protein'), carb=Sum('carbohydrates'), fat=Sum('fats'),
            va=Sum('vitamin_a'), vc=Sum('vitamin_c'), vd=Sum('vitamin_d'), ve=Sum('vitamin_e'), vk=Sum('vitamin_k'),
            ca=Sum('mineral_calcium'), fe=Sum('mineral_iron'), na=Sum('mineral_sodium'), k=Sum('mineral_potassium'), zn=Sum('mineral_zink')
        )
        f = lambda v: round(float(v or 0), 2)
        return Response({
            "week_range": f"{start} to {today}",
            "overall": {"calories": f(s['cal']), "protein": f(s['pro']), "carbohydrates": f(s['carb']), "fats": f(s['fat'])},
            "vitamins": {"vitamin_a": f(s['va']), "vitamin_c": f(s['vc']), "vitamin_d": f(s['vd']), "vitamin_e": f(s['ve']), "vitamin_k": f(s['vk'])},
            "minerals": {"mineral_calcium": f(s['ca']), "mineral_iron": f(s['fe']), "mineral_sodium": f(s['na']), "mineral_potassium": f(s['k']), "mineral_zink": f(s['zn'])}
        })

class RangeFoodStatsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        s_str, e_str = request.query_params.get('start_date'), request.query_params.get('end_date')
        if not s_str or not e_str: return Response({"error": "Dates required"}, status=400)
        s_d, e_d = parse_date_custom(s_str), parse_date_custom(e_str)
        st = FoodItem.objects.filter(user=request.user, date__date__range=[s_d, e_d]).aggregate(
            cal=Sum('calories'), pro=Sum('protein'), carb=Sum('carbohydrates'), fat=Sum('fats'),
            va=Sum('vitamin_a'), vc=Sum('vitamin_c'), vd=Sum('vitamin_d'), ve=Sum('vitamin_e'), vk=Sum('vitamin_k'),
            ca=Sum('mineral_calcium'), fe=Sum('mineral_iron'), na=Sum('mineral_sodium'), k=Sum('mineral_potassium'), zn=Sum('mineral_zink')
        )
        f = lambda v: round(float(v or 0), 2)
        data = {
            "range": {"start": s_str, "end": e_str},
            "overall": {"calories": f(st['cal']), "protein": f(st['pro']), "carbohydrates": f(st['carb']), "fats": f(st['fat'])},
            "vitamins": {"vitamin_a": f(st['va']), "vitamin_c": f(st['vc']), "vitamin_d": f(st['vd']), "vitamin_e": f(st['ve']), "vitamin_k": f(st['vk'])},
            "minerals": {"mineral_calcium": f(st['ca']), "mineral_iron": f(st['fe']), "mineral_sodium": f(st['na']), "mineral_potassium": f(st['k']), "mineral_zink": f(st['zn'])}
        }
        return Response(FoodStatsResponseSerializer(data).data)

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

class AddRecipeView(APIView): # Ehtiyat üçün sonda saxladım
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = AddRecipeRequestSerializer(data=request.data)
        if not serializer.is_valid(): return Response(serializer.errors, status=400)
        try:
            url = f"https://api.spoonacular.com/recipes/{serializer.validated_data['recipe_id']}/information"
            params = {"includeNutrition": "true", "apiKey": SPOONACULAR_API_KEY}
            r = rq.get(url, params=params, timeout=30).json()
            nutri = extract_nutrition_data(r.get("nutrition", {}).get("nutrients", []))
            mt = resolve_meal_type(serializer.validated_data.get("meal_type"), serializer.validated_data.get("meal_type_name"))
            food = FoodItem.objects.create(
                user=request.user, name=r.get("title", "Recipe"),
                calories=nutri['calories'], protein=nutri['protein'],
                carbohydrates=nutri['carbohydrates'], fats=nutri['fat'],
                meal_type=mt, trans_fat=nutri['trans_fat'], saturated_fat=nutri['saturated_fat'],
                vitamin_a=nutri['vitaminA'], vitamin_c=nutri['vitaminC'], vitamin_d=nutri['vitaminD'],
                vitamin_e=nutri['vitaminE'], vitamin_k=nutri['vitaminK'],
                mineral_calcium=nutri['calcium'], mineral_iron=nutri['iron'],
                mineral_sodium=nutri['sodium'], mineral_potassium=nutri['potassium'], mineral_zink=nutri['zinc'],
            )
            res = nutri.copy()
            res.update({'id': food.id, 'name': food.name, 'created_at': food.date})
            return Response(res, status=201)
        except Exception as e: return Response({"error": str(e)}, status=500)