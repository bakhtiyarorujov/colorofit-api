from django.urls import path
from .views import FoodRecognitionView

urlspatterns = [
    path("predict-food/", FoodRecognitionView.as_view(), name="predict-food"),
]