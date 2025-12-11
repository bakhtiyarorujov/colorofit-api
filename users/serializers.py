from rest_framework import serializers
from .models import User
from datetime import date


# Request Serializer
class GoogleTokenRequestSerializer(serializers.Serializer):
    token = serializers.CharField(help_text="Google ID token from client")

# Response Serializer
class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class GoogleLoginResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    tokens = serializers.DictField(child=serializers.CharField())


class AppleLoginSerializer(serializers.Serializer):
    token = serializers.CharField()
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)


class AppleLoginResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    tokens = serializers.DictField(child=serializers.CharField())


class UserAimDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'age',
            'gender',
            'height',
            'weight',
            'aimed_weight',
            'aimed_date',
            'life_style',
        )

class TargetDetailSerializer(serializers.ModelSerializer):
    tdee = serializers.SerializerMethodField()
    daily_deficit = serializers.SerializerMethodField()
    calorie_target = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'tdee',
            'daily_deficit',
            'calorie_target',
            'days_left'
        )

    def get_tdee(self, obj):
        # Safety Check: If any required field is missing, return 0
        if not all([obj.weight, obj.height, obj.age, obj.gender]):
            return 0

        activity_factors = {
            "Sedentary": 1.2,
            "Lightly active": 1.375,
            "Moderately active": 1.55,
            "Active": 1.725,
            "Very active": 1.9,
        }
        
        # Step 1: BMR
        s = 5 if obj.gender == "male" else -161
        try:
            bmr = 10 * float(obj.weight) + 6.25 * float(obj.height) - 5 * float(obj.age) + s
        except (ValueError, TypeError):
            return 0

        # Step 2: TDEE
        activity_factor = activity_factors.get(obj.life_style, 1.2)
        tdee = bmr * activity_factor
        return round(tdee)
    
    def get_daily_deficit(self, obj):
        # Safety Check
        if not all([obj.weight, obj.aimed_weight, obj.aimed_date]):
            return 0

        try:
            weight_loss_goal = float(obj.weight) - float(obj.aimed_weight)
            # Ensure days_left isn't negative or zero to prevent weird math
            days_left = max((obj.aimed_date - date.today()).days, 1)  
            
            total_deficit = weight_loss_goal * 7700
            daily_deficit = total_deficit / days_left
            return round(daily_deficit)
        except (ValueError, TypeError):
            return 0
    
    def get_calorie_target(self, obj):
        tdee = self.get_tdee(obj)
        daily_deficit = self.get_daily_deficit(obj)
        
        # If tdee is 0 (data missing), target cannot be calculated
        if tdee == 0:
            return 0
            
        calorie_target = tdee - daily_deficit
        
        # Prevent negative targets (if someone sets unrealistic goals)
        return max(round(calorie_target), 1200) # 1200 is a safe minimum floor
    
    def get_days_left(self, obj):
        if not obj.aimed_date:
            return 0
        return max((obj.aimed_date - date.today()).days, 0)


