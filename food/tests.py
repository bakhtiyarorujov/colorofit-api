"""Tests for the food app: recognition flow, stats aggregation, water logging."""
from datetime import date
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import WaterIntakeType
from .models import FoodItem, MealType, WaterIntake

User = get_user_model()

# A complete nutrition payload matching predict_food_with_gemini()'s output.
FAKE_NUTRITION = {
    "food_name": "plov", "estimated_grams": 300, "calories": 650, "protein": 20,
    "fat": 25, "saturated_fat": 8, "trans_fat": 0, "carbohydrates": 80, "fiber": 3,
    "sugar": 2, "cholesterol": 40, "sodium": 500, "calcium": 30, "iron": 3,
    "potassium": 400, "zinc": 2, "vitaminA": 100, "vitaminC": 5, "vitaminD": 0,
    "vitaminE": 1, "vitaminK": 10,
}


def fake_image():
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (8, 8), "red").save(buf, format="JPEG")
    buf.seek(0)
    buf.name = "food.jpg"
    return buf


class FoodRecognitionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(username="a@example.com", email="a@example.com")
        self.url = reverse("predict-food")

    def test_requires_authentication(self):
        resp = self.client.post(self.url, {"image": fake_image()}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("food.views.predict_food_with_gemini", return_value=FAKE_NUTRITION)
    def test_successful_scan_creates_food_item(self, _mock):
        self.client.force_authenticate(self.user)
        resp = self.client.post(self.url, {"image": fake_image()}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FoodItem.objects.filter(user=self.user).count(), 1)
        self.assertEqual(resp.data["food_name"], "plov")

    @patch("food.views.predict_food_with_gemini",
           return_value={**FAKE_NUTRITION, "food_name": ""})
    def test_no_food_detected_returns_400(self, _mock):
        self.client.force_authenticate(self.user)
        resp = self.client.post(self.url, {"image": fake_image()}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(FoodItem.objects.count(), 0)

    @patch("food.views.predict_food_with_gemini")
    def test_gemini_failure_does_not_leak_traceback(self, mock_predict):
        from food.views import GeminiAPIError
        mock_predict.side_effect = GeminiAPIError("boom: secret internal detail")
        self.client.force_authenticate(self.user)
        resp = self.client.post(self.url, {"image": fake_image()}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertNotIn("secret internal detail", str(resp.data))
        self.assertNotIn("details", resp.data)


class RangeStatsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(username="b@example.com", email="b@example.com")
        self.client.force_authenticate(self.user)
        self.url = reverse("range-food-stats")

    def test_missing_params_returns_400(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_date_returns_400_not_500(self):
        # Regression: parse_date raises ValueError, which used to bubble to a 500.
        resp = self.client.get(self.url, {"start_date": "not-a-date", "end_date": "2026-01-07"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_start_after_end_returns_400(self):
        resp = self.client.get(self.url, {"start_date": "2026-01-10", "end_date": "2026-01-01"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_range_aggregates_items(self):
        today = date.today().isoformat()
        FoodItem.objects.create(user=self.user, name="x", calories=100,
                                protein=10, carbohydrates=20, fats=5)
        FoodItem.objects.create(user=self.user, name="y", calories=200,
                                protein=20, carbohydrates=30, fats=8)
        resp = self.client.get(self.url, {"start_date": today, "end_date": today})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(float(resp.data["overall"]["calories"]), 300.0)


class WaterTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(username="c@example.com", email="c@example.com")
        self.client.force_authenticate(self.user)
        self.cup = WaterIntakeType.objects.create(name="Cup", amount_ml=250)

    def test_add_and_total(self):
        add = self.client.post(reverse("water-add"), {"intake_type": self.cup.id},
                               format="json")
        self.assertIn(add.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        self.assertEqual(WaterIntake.objects.filter(user=self.user).count(), 1)

        total = self.client.get(reverse("water-total"),
                                {"date": date.today().isoformat()})
        self.assertEqual(total.status_code, status.HTTP_200_OK)

    def test_water_intake_types_are_public(self):
        self.client.force_authenticate(None)
        resp = self.client.get(reverse("water-intake-types"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class MealTypeTests(APITestCase):
    def test_meal_types_require_auth(self):
        resp = self.client.get(reverse("meal-types"))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_meal_types_list_when_authenticated(self):
        user = User.objects.create(username="d@example.com", email="d@example.com")
        MealType.objects.create(name="Breakfast")
        self.client.force_authenticate(user)
        resp = self.client.get(reverse("meal-types"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
