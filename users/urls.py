# urls.py
from django.urls import path
from .views import GoogleLoginAPIView, AppleLoginAPIView, UserAimDetailUpdateView, TargetDetailView, FoodRecognitionView

urlpatterns = [
    path('auth/google/', GoogleLoginAPIView.as_view(), name='google-login'),
    path('auth/apple/', AppleLoginAPIView.as_view(), name='apple-login'),
    path('user-details/update/', UserAimDetailUpdateView.as_view(), name='user-aim-detail-update'),
    path('target-details/', TargetDetailView.as_view(), name='target-detail-view'),
]
