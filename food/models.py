from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()
# Create your models here.
class MealType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class FoodItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='food_items')
    name = models.CharField(max_length=200)
    calories = models.DecimalField(max_digits=6, decimal_places=2)
    protein = models.DecimalField(max_digits=6, decimal_places=2)
    carbohydrates = models.DecimalField(max_digits=6, decimal_places=2)
    fats = models.DecimalField(max_digits=6, decimal_places=2)
    meal_type = models.ForeignKey(MealType, on_delete=models.CASCADE, related_name='food_items', null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class WaterIntakeType(models.Model):
    name = models.CharField(max_length=100)
    amount_ml = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.amount_ml} ml"
    
class WaterIntake(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='water_intakes')
    intake_type = models.ForeignKey(WaterIntakeType, on_delete=models.CASCADE, related_name='water_intakes')
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.intake_type.amount_ml} ml on {self.date}"