from django.urls import path
from .views import FoodRecognitionView, FoodItemByDateView, FoodItemUpdateView, FoodItemDeleteView \
    , WaterIntakeCreateView, WaterIntakeDeleteView, WaterIntakeDailyTotalView, AddRecipeView \
    , DailyStatsView, WeeklyFoodStatsView, RangeFoodStatsView, WaterIntakeTypeListView, SetWaterIntakePreferenceView \
    , MealTypeListView

urlpatterns = [
    path("predict-food/", FoodRecognitionView.as_view(), name="predict-food"),
    path("add-recipe/", AddRecipeView.as_view(), name="add-recipe"),
    path("history/", FoodItemByDateView.as_view(), name="food-history"),
    path("meal-types/", MealTypeListView.as_view(), name="meal-types"),
    path("update/<int:pk>/", FoodItemUpdateView.as_view(), name="update-food"),
    path("items/<int:pk>/delete/", FoodItemDeleteView.as_view(), name="food-item-delete"),
    path("water/add/", WaterIntakeCreateView.as_view(), name="water-add"),
    path("water/<int:pk>/delete/", WaterIntakeDeleteView.as_view(), name="water-delete"),
    path("water/total/", WaterIntakeDailyTotalView.as_view(), name="water-total"),
    path("daily-stats/", DailyStatsView.as_view(), name="daily-stats"),
    path("weekly-food-stats/", WeeklyFoodStatsView.as_view(), name="weekly-food-stats"),
    path("range-food-stats/", RangeFoodStatsView.as_view(), name="range-food-stats"),
    path("water-intake-types/", WaterIntakeTypeListView.as_view(), name="water-intake-types"),
    path("set-water-intake-preference/", SetWaterIntakePreferenceView.as_view(), name="set-water-intake-preference"),
]