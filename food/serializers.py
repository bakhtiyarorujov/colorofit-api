from rest_framework import serializers
from .models import FoodItem, WaterIntake


class FoodRecognitionRequestSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)
    meal_type = serializers.IntegerField(required=False, allow_null=True)
    meal_type_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class AddRecipeRequestSerializer(serializers.Serializer):
    recipe_id = serializers.IntegerField(required=True)
    meal_type = serializers.IntegerField(required=False, allow_null=True)
    meal_type_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class FoodItemSerializer(serializers.ModelSerializer):
    meal_type_name = serializers.CharField(source='meal_type.name', read_only=True, allow_null=True)
    
    class Meta:
        model = FoodItem
        fields = ['id', 'name', 'calories', 'protein', 'carbohydrates', 'fats', 'meal_type', 'meal_type_name', 'date']


class FoodItemUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodItem
        # Only include fields the user is allowed to change
        fields = ['meal_type']


class WaterIntakeSerializer(serializers.ModelSerializer):
    # This field allows us to see the actual amount in the response, 
    # even though we only send the ID to create it.
    amount_display = serializers.IntegerField(source='intake_type.amount_ml', read_only=True)

    class Meta:
        model = WaterIntake
        fields = ['id', 'intake_type', 'amount_display', 'date']
        read_only_fields = ['date']


class NutrientGroupSerializer(serializers.Serializer):
    # Overall
    calories = serializers.DecimalField(max_digits=10, decimal_places=2)
    protein = serializers.DecimalField(max_digits=10, decimal_places=2)
    carbohydrates = serializers.DecimalField(max_digits=10, decimal_places=2)
    fats = serializers.DecimalField(max_digits=10, decimal_places=2)

class VitaminGroupSerializer(serializers.Serializer):
    vitamin_a = serializers.DecimalField(max_digits=10, decimal_places=2)
    vitamin_c = serializers.DecimalField(max_digits=10, decimal_places=2)
    vitamin_d = serializers.DecimalField(max_digits=10, decimal_places=2)
    vitamin_e = serializers.DecimalField(max_digits=10, decimal_places=2)
    vitamin_k = serializers.DecimalField(max_digits=10, decimal_places=2)

class MineralGroupSerializer(serializers.Serializer):
    mineral_calcium = serializers.DecimalField(max_digits=10, decimal_places=2)
    mineral_iron = serializers.DecimalField(max_digits=10, decimal_places=2)
    mineral_sodium = serializers.DecimalField(max_digits=10, decimal_places=2)
    mineral_potassium = serializers.DecimalField(max_digits=10, decimal_places=2)
    mineral_zink = serializers.DecimalField(max_digits=10, decimal_places=2)

class FoodStatsResponseSerializer(serializers.Serializer):
    overall = NutrientGroupSerializer()
    vitamins = VitaminGroupSerializer()
    minerals = MineralGroupSerializer()