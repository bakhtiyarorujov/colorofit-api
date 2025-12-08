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
        activity_factors = {
            "Sedentary": 1.2,
            "Lightly active": 1.375,
            "Moderately active": 1.55,
            "Active": 1.725,
            "Very active": 1.9,
        }
        # Step 1: BMR
        s = 5 if obj.gender == "male" else -161
        bmr = 10 * float(obj.weight) + 6.25 * float(obj.height) - 5 * float(obj.age) + s

        # Step 2: TDEE
        activity_factor = activity_factors.get(obj.life_style, 1.2)
        tdee = bmr * activity_factor
        return round(tdee)
    
    def get_daily_deficit(self, obj):
        # Step 3: Calorie deficit and target
        weight_loss_goal = float(obj.weight) - float(obj.aimed_weight)
        days_left = max((obj.aimed_date - date.today()).days, 1)  # avoid division by zero
        total_deficit = weight_loss_goal * 7700
        daily_deficit = total_deficit / days_left
        return round(daily_deficit)
    
    def get_calorie_target(self, obj):
        tdee = self.get_tdee(obj)
        daily_deficit = self.get_daily_deficit(obj)
        calorie_target = tdee - daily_deficit
        return round(calorie_target)
    
    def get_days_left(self, obj):
        days_left = max((obj.aimed_date - date.today()).days, 1)
        return days_left


