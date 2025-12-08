from django.urls import path
from .views import FoodRecognitionView, FoodItemByDateView, FoodItemUpdateView, FoodItemDeleteView \
    , WaterIntakeCreateView, WaterIntakeDeleteView, WaterIntakeDailyTotalView

urlpatterns = [
    path("predict-food/", FoodRecognitionView.as_view(), name="predict-food"),
    path("history/", FoodItemByDateView.as_view(), name="food-history"),
    path("update/<int:pk>/", FoodItemUpdateView.as_view(), name="update-food"),
    path("items/<int:pk>/delete/", FoodItemDeleteView.as_view(), name="food-item-delete"),
    path("water/add/", WaterIntakeCreateView.as_view(), name="water-add"),
    path("water/<int:pk>/delete/", WaterIntakeDeleteView.as_view(), name="water-delete"),
    path("water/total/", WaterIntakeDailyTotalView.as_view(), name="water-total"),
]