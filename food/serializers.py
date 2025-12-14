from rest_framework import serializers
from .models import FoodItem, WaterIntake


class FoodRecognitionRequestSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)


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