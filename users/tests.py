"""Tests for the users app: TDEE/macro math, social auth, profile & feedback."""
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from jose.exceptions import JWTError

from .serializers import TargetDetailSerializer, is_profile_complete

User = get_user_model()


def make_user(**overrides):
    """An in-memory user with sensible onboarding defaults for math tests."""
    defaults = dict(
        username="u@example.com",
        email="u@example.com",
        gender="male",
        age=30,
        height=180,
        weight=80,
        aimed_weight=75,
        aimed_date=None,
        life_style="Moderately active",
    )
    defaults.update(overrides)
    return User(**defaults)


class TargetMathTests(APITestCase):
    """Locks down the calorie/macro engine — the core value of the app."""

    def test_tdee_male_moderately_active(self):
        # BMR = 10*80 + 6.25*180 - 5*30 + 5 = 1780; TDEE = 1780 * 1.55 = 2759
        data = TargetDetailSerializer(make_user()).data
        self.assertEqual(data["tdee"], 2759)

    def test_tdee_female_uses_minus_161_constant(self):
        # BMR = 10*70 + 6.25*165 - 5*28 - 161 = 1430.25; TDEE * 1.2 = 1716.3 -> 1716
        user = make_user(gender="female", weight=70, height=165, age=28,
                         life_style="Sedentary")
        self.assertEqual(TargetDetailSerializer(user).data["tdee"], 1716)

    def test_tdee_zero_when_metrics_missing(self):
        self.assertEqual(TargetDetailSerializer(make_user(weight=None)).data["tdee"], 0)

    def test_daily_deficit_capped_at_500_when_cutting(self):
        # 5 kg to lose, no target date -> ~550/day, capped at 500.
        self.assertEqual(TargetDetailSerializer(make_user()).data["daily_deficit"], 500)

    def test_daily_deficit_capped_at_minus_500_when_bulking(self):
        user = make_user(weight=60, aimed_weight=70)
        self.assertEqual(TargetDetailSerializer(user).data["daily_deficit"], -500)

    def test_daily_deficit_zero_when_weight_equals_target(self):
        user = make_user(weight=75, aimed_weight=75)
        self.assertEqual(TargetDetailSerializer(user).data["daily_deficit"], 0)

    def test_calorie_target_never_below_floor(self):
        # Tiny person, huge deficit request -> must clamp to the 1200 floor.
        user = make_user(weight=45, height=150, age=25, aimed_weight=40)
        self.assertGreaterEqual(TargetDetailSerializer(user).data["calorie_target"], 1200)

    def test_macros_are_consistent_with_calorie_target(self):
        data = TargetDetailSerializer(make_user()).data
        # protein 2.0 g/kg * 80 = 160; fat 30% of 2259 /9 = 75
        self.assertEqual(data["protein_target"], 160)
        self.assertEqual(data["fat_target"], 75)
        # carbs fill the remainder; sum of macro kcal ~= calorie target
        kcal = data["protein_target"] * 4 + data["fat_target"] * 9 + data["carbs_target"] * 4
        self.assertAlmostEqual(kcal, data["calorie_target"], delta=5)

    def test_micronutrient_targets_are_gender_specific(self):
        male = TargetDetailSerializer(make_user(gender="male")).data
        female = TargetDetailSerializer(make_user(gender="female")).data
        self.assertEqual(male["mineral_targets"]["mineral_iron"], 8)
        self.assertEqual(female["mineral_targets"]["mineral_iron"], 18)
        self.assertEqual(male["vitamin_targets"]["vitamin_c"], 90)
        self.assertEqual(female["vitamin_targets"]["vitamin_c"], 75)

    def test_days_left_honors_aimed_date(self):
        user = make_user(aimed_date=date.today() + timedelta(days=42))
        self.assertEqual(TargetDetailSerializer(user).data["days_left"], 42)


class ProfileCompleteTests(APITestCase):
    def test_complete_when_all_core_metrics_present(self):
        self.assertTrue(is_profile_complete(make_user()))

    def test_incomplete_when_a_metric_missing(self):
        self.assertFalse(is_profile_complete(make_user(life_style=None)))


class GoogleAuthTests(APITestCase):
    url = reverse("google-login")

    def test_missing_token_returns_400(self):
        resp = self.client.post(self.url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("users.views.id_token.verify_oauth2_token")
    def test_valid_token_creates_user_and_returns_jwt(self, mock_verify):
        mock_verify.return_value = {
            "email": "new@example.com",
            "given_name": "New",
            "family_name": "User",
        }
        resp = self.client.post(self.url, {"token": "fake"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data["tokens"])
        self.assertTrue(User.objects.filter(email="new@example.com").exists())
        self.assertIn("profile_complete", resp.data)

    @patch("users.views.id_token.verify_oauth2_token", side_effect=ValueError("bad token"))
    def test_invalid_token_returns_400(self, _mock):
        resp = self.client.post(self.url, {"token": "bad"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class AppleAuthTests(APITestCase):
    url = reverse("apple-login")

    @patch("users.views.verify_apple_identity_token")
    def test_valid_token_creates_user(self, mock_verify):
        mock_verify.return_value = {"email": "apple@example.com"}
        resp = self.client.post(self.url, {"token": "fake"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.filter(email="apple@example.com").exists())

    @patch("users.views.verify_apple_identity_token",
           side_effect=JWTError("signature verification failed"))
    def test_unverifiable_signature_is_rejected(self, _mock):
        # The whole point of the security fix: forged tokens must not pass.
        resp = self.client.post(self.url, {"token": "forged"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 0)

    @patch("users.views.verify_apple_identity_token", return_value={"email": ""})
    def test_missing_email_returns_400(self, _mock):
        resp = self.client.post(self.url, {"token": "fake"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class FeedbackTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(username="f@example.com", email="f@example.com")
        self.client.force_authenticate(self.user)

    def test_rating_out_of_range_is_rejected(self):
        resp = self.client.post(reverse("user-feedback"),
                                {"rating": 9, "message": "too high"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_feedback_is_saved_against_user(self):
        resp = self.client.post(reverse("user-feedback"),
                                {"rating": 5, "message": "great"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_feedback_requires_authentication(self):
        self.client.force_authenticate(None)
        resp = self.client.post(reverse("user-feedback"),
                                {"rating": 5, "message": "x"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfileTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(username="p@example.com", email="p@example.com",
                                        first_name="Ada", last_name="Lovelace")
        self.client.force_authenticate(self.user)

    def test_get_profile_returns_full_name(self):
        resp = self.client.get(reverse("user-profile"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["full_name"], "Ada Lovelace")

    def test_patch_updates_body_metrics(self):
        resp = self.client.patch(reverse("user-profile"), {"weight": 82, "height": 170},
                                 format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.weight, 82)
