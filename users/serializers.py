from rest_framework import serializers
from .models import User, Feedback
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


class UserProfileSerializer(serializers.ModelSerializer):
    """Full profile read/update. Read returns all relevant fields; write
    accepts a subset (name, bio, profile_picture, body metrics)."""
    full_name = serializers.SerializerMethodField()
    profile_picture = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'username',
            'first_name',
            'last_name',
            'full_name',
            'profile_picture',
            'bio',
            'gender',
            'age',
            'height',
            'weight',
            'aimed_weight',
            'aimed_date',
            'life_style',
            'water_intake_goal_ml',
        )
        read_only_fields = ('id', 'email', 'username', 'full_name')

    def get_full_name(self, obj):
        name = f"{obj.first_name or ''} {obj.last_name or ''}".strip()
        return name or (obj.username or '').split('@')[0]


class AlertPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'alert_meal_reminders',
            'alert_water_reminders',
            'alert_weekly_summary',
            'alert_goal_achievements',
        )


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ('id', 'rating', 'message', 'created_at')
        read_only_fields = ('id', 'created_at')

    def validate_rating(self, value):
        if value < 0 or value > 5:
            raise serializers.ValidationError('rating must be 0..5')
        return value

class TargetDetailSerializer(serializers.ModelSerializer):
    tdee = serializers.SerializerMethodField()
    daily_deficit = serializers.SerializerMethodField()
    calorie_target = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()
    protein_target = serializers.SerializerMethodField()
    carbs_target = serializers.SerializerMethodField()
    fat_target = serializers.SerializerMethodField()
    vitamin_targets = serializers.SerializerMethodField()
    mineral_targets = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'tdee',
            'daily_deficit',
            'calorie_target',
            'days_left',
            'protein_target',
            'carbs_target',
            'fat_target',
            'vitamin_targets',
            'mineral_targets',
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
        # Need at least current weight and target weight to compute anything.
        if not obj.weight or not obj.aimed_weight:
            return 0

        try:
            # weight_delta > 0 means cutting (lose weight),
            # weight_delta < 0 means bulking (gain weight).
            weight_delta = float(obj.weight) - float(obj.aimed_weight)
            if weight_delta == 0:
                return 0

            # If user picked a target date, honor it. Otherwise pace at a
            # healthy 0.5 kg/week (~1 lb/week) — standard fitness app default.
            if obj.aimed_date:
                days_left = max((obj.aimed_date - date.today()).days, 1)
            else:
                days_left = max(int(abs(weight_delta) / 0.5 * 7), 7)

            total_deficit = weight_delta * 7700
            daily_deficit = total_deficit / days_left

            # Cap at ±750 kcal/day to keep recommendations medically safe
            # (avoids crash diets or extreme bulks when the user picks an
            # aggressive target date).
            return round(max(min(daily_deficit, 750), -750))
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
        if obj.aimed_date:
            return max((obj.aimed_date - date.today()).days, 0)
        # Fallback: estimate days from weight delta at 0.5 kg/week.
        if obj.weight and obj.aimed_weight:
            try:
                delta = abs(float(obj.weight) - float(obj.aimed_weight))
                if delta == 0:
                    return 0
                return max(int(delta / 0.5 * 7), 7)
            except (ValueError, TypeError):
                pass
        return 0

    # --- Macronutrient targets (grams/day) ---
    # Strategy:
    #   Protein: 1.8 g per kg of body weight (fitness app standard, 1.6-2.2 range)
    #   Fat:     30% of total calories, divided by 9 kcal/g
    #   Carbs:   remaining calories, divided by 4 kcal/g
    # Falls back to a 30/40/30 percentage split if weight is missing.

    def get_protein_target(self, obj):
        calories = self.get_calorie_target(obj)
        if calories <= 0:
            return 0
        # Protein scales with activity level (ACSM / ISSN guidelines):
        # - Sedentary:          1.2 g/kg
        # - Lightly active:     1.6 g/kg
        # - Moderately active:  2.0 g/kg
        # - Active:             2.2 g/kg
        # - Very active:        2.4 g/kg
        protein_per_kg = {
            "Sedentary": 1.2,
            "Lightly active": 1.6,
            "Moderately active": 2.0,
            "Active": 2.2,
            "Very active": 2.4,
        }.get(obj.life_style, 1.6)
        if obj.weight:
            try:
                return round(float(obj.weight) * protein_per_kg)
            except (ValueError, TypeError):
                pass
        # fallback when weight is missing: 30% of calories
        return round(calories * 0.30 / 4)

    def get_fat_target(self, obj):
        calories = self.get_calorie_target(obj)
        if calories <= 0:
            return 0
        # 30% of calories from fat, 9 kcal/g
        return round(calories * 0.30 / 9)

    def get_carbs_target(self, obj):
        calories = self.get_calorie_target(obj)
        if calories <= 0:
            return 0
        protein_kcal = self.get_protein_target(obj) * 4
        fat_kcal = self.get_fat_target(obj) * 9
        remaining = calories - protein_kcal - fat_kcal
        return max(round(remaining / 4), 0)

    # --- Micronutrient targets (RDA, gender-based where applicable) ---
    def get_vitamin_targets(self, obj):
        is_male = obj.gender == 'male'
        return {
            'vitamin_a': 900 if is_male else 700,   # µg RAE
            'vitamin_c': 90 if is_male else 75,     # mg
            'vitamin_d': 15,                        # µg
            'vitamin_e': 15,                        # mg
            'vitamin_k': 120 if is_male else 90,    # µg
        }

    def get_mineral_targets(self, obj):
        is_male = obj.gender == 'male'
        return {
            'mineral_calcium': 1000,                # mg
            'mineral_iron': 8 if is_male else 18,   # mg
            'mineral_sodium': 2300,                 # mg (upper limit)
            'mineral_potassium': 3400 if is_male else 2600,  # mg
            'mineral_zink': 11 if is_male else 8,   # mg
        }


