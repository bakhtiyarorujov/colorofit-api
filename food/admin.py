from django.contrib import admin
from .models import MealType, FoodItem, WaterIntakeType, WaterIntake
# Register your models here.

@admin.register(MealType)
class MealTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    list_display_links = ('name',)
    search_fields = ('name',)

@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'calories', 'protein', 'carbohydrates', 'fats', 'meal_type')
    list_display_links = ('name',)
    search_fields = ('name',)
    list_filter = ('meal_type',)

@admin.register(WaterIntakeType)
class WaterIntakeTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    list_display_links = ('name',)
    search_fields = ('name',)

@admin.register(WaterIntake)
class WaterIntakeAdmin(admin.ModelAdmin):
    list_display = ('user', 'intake_type', 'date')
    list_display_links = ('user',)
    search_fields = ('user__username',)
    list_filter = ('intake_type', 'date')