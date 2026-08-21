# urls.py
from django.urls import path
from .views import (
    GoogleLoginAPIView, AppleLoginAPIView, GuestLoginView, UserAimDetailUpdateView,
    TargetDetailView, NutritionAdviceView, UserProfileView, AlertPreferenceView,
    FeedbackCreateView, DeleteAccountView,
)

urlpatterns = [
    path('auth/google/', GoogleLoginAPIView.as_view(), name='google-login'),
    path('auth/apple/', AppleLoginAPIView.as_view(), name='apple-login'),
    path('auth/guest/', GuestLoginView.as_view(), name='guest-login'),
    path('delete-account/', DeleteAccountView.as_view(), name='delete-account'),
    path('user-details/update/', UserAimDetailUpdateView.as_view(), name='user-aim-detail-update'),
    path('target-details/', TargetDetailView.as_view(), name='target-detail-view'),
    path('nutrition-advice/', NutritionAdviceView.as_view(), name='nutrition-advice'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('alerts/', AlertPreferenceView.as_view(), name='user-alerts'),
    path('feedback/', FeedbackCreateView.as_view(), name='user-feedback'),
]
