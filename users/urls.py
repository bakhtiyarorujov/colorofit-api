# urls.py
from django.urls import path
from .views import GoogleLoginAPIView

urlpatterns = [
    path('auth/google/', GoogleLoginAPIView.as_view(), name='google-login'),
]
