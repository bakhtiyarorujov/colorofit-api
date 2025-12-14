import logging
from datetime import date
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse, OpenApiParameter
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .models import FoodItem, WaterIntake, WaterIntakeType
from rest_framework.permissions import IsAuthenticated
from .serializers import FoodRecognitionRequestSerializer, FoodItemSerializer, FoodItemUpdateSerializer \
    , WaterIntakeSerializer
from django.db.models import Sum
from django.contrib.auth import get_user_model
from .services import OCRService, IngredientParser, SpoonacularService

logger = logging.getLogger(__name__)

User = get_user_model()





@extend_schema(
    request=FoodRecognitionRequestSerializer,
    responses={
        201: OpenApiResponse(
            description="Successfully extracted recipe, analyzed nutrition, and saved to database",
            examples=[
                OpenApiExample(
                    'Success',
                    value={
                        "id": 15,
                        "food_name": "Chicken Pasta",
                        "calories": 450.5,
                        "protein": 25.3,
                        "carbohydrates": 45.2,
                        "fats": 15.8,
                        "servings": 2,
                        "created_at": "2025-12-11T10:30:00Z"
                    }
                )
            ]
        ),
        400: OpenApiResponse(description="Invalid input or validation error"),
        500: OpenApiResponse(description="Server error during processing"),
    },
    tags=["Food"],
    summary="Analyze Recipe from Image",
    description=(
        "Uploads an image of a food recipe, extracts text using OCR, "
        "normalizes ingredients, and calculates nutrition data using Spoonacular API. "
        "Saves the recipe as a FoodItem in the database."
    )
)
class FoodRecognitionView(APIView):
    """
    API endpoint for analyzing recipe images and extracting nutrition data.
    
    Process:
    1. Extract text from recipe image using OCR
    2. Normalize text into ingredient lines
    3. Analyze nutrition using Spoonacular API
    4. Save to database as FoodItem
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Process recipe image and return nutrition data.
        
        Expected input:
        - image: Image file (JPEG, PNG, etc.)
        - servings: Optional integer (default: 1)
        """
        # Validate input
        serializer = FoodRecognitionRequestSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"Invalid request data: {serializer.errors}")
            return Response(
                {"error": "Invalid input", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        image_file = serializer.validated_data["image"]
        servings = serializer.validated_data.get("servings", 1)

        try:
            # Step 1: Extract text from image using OCR
            logger.info("Starting OCR text extraction")
            ocr_service = OCRService()
            raw_text = ocr_service.extract_text(image_file)
            
            if not raw_text or len(raw_text.strip()) < 10:
                return Response(
                    {"error": "Could not extract sufficient text from image. Please ensure the image contains readable recipe text."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Step 2: Normalize text into ingredient lines
            logger.info("Normalizing ingredient text")
            ingredient_parser = IngredientParser()
            ingredient_lines = ingredient_parser.normalize_text(raw_text)
            
            if not ingredient_lines:
                return Response(
                    {"error": "Could not parse ingredients from extracted text. Please ensure the image contains a valid recipe."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Step 3: Format ingredients for Spoonacular API
            formatted_ingredients = ingredient_parser.format_for_spoonacular(ingredient_lines)

            # Step 4: Get nutrition data from Spoonacular
            logger.info(f"Analyzing nutrition for {len(ingredient_lines)} ingredients")
            spoonacular_service = SpoonacularService()
            nutrition_data = spoonacular_service.analyze_recipe_nutrition(
                formatted_ingredients,
                servings=servings
            )

            # Step 5: Create FoodItem object
            food_item = FoodItem.objects.create(
                user=request.user,
                name=nutrition_data['food_name'],
                calories=nutrition_data['calories'],
                protein=nutrition_data['protein'],
                carbohydrates=nutrition_data['carbohydrates'],
                fats=nutrition_data['fats'],
            )

            # Step 6: Prepare response data with macros and micros
            response_data = {
                'id': food_item.id,
                'food_name': nutrition_data['food_name'],
                # Macronutrients
                'calories': nutrition_data['calories'],
                'protein': nutrition_data['protein'],
                'carbohydrates': nutrition_data['carbohydrates'],
                'fats': nutrition_data['fats'],
                'fiber': nutrition_data.get('fiber', 0),
                'sugar': nutrition_data.get('sugar', 0),
                'saturated_fat': nutrition_data.get('saturated_fat', 0),
                'trans_fat': nutrition_data.get('trans_fat', 0),
                'cholesterol': nutrition_data.get('cholesterol', 0),
                'sodium': nutrition_data.get('sodium', 0),
                # Micronutrients
                'vitamins': nutrition_data.get('vitamins', {}),
                'minerals': nutrition_data.get('minerals', {}),
                # Other
                'servings': nutrition_data.get('servings', servings),
                'created_at': food_item.date,
                'ingredients_count': len(ingredient_lines),
            }

            logger.info(f"Successfully processed recipe: {nutrition_data['food_name']}")
            return Response(response_data, status=status.HTTP_201_CREATED)

        except ValueError as e:
            logger.error(f"Validation error: {e}")
            return Response(
                {"error": "Invalid input", "details": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error processing recipe: {e}", exc_info=True)
            return Response(
                {"error": "Failed to process recipe image", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
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