from django.db import models
from django.contrib.auth.models import AbstractUser
# Create your models here.

class WaterIntakeUnit(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name

class WaterIntakeType(models.Model):
    name = models.CharField(max_length=100)
    amount_ml = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.name} ({self.amount_ml} ml)"

class LifeStyle(models.Model):
    name = models.CharField(max_length=100)
    activity_factor = models.DecimalField(max_digits=3, decimal_places=2)

GENDER_CHOICES = [('female', 'Female'), ('male', 'Male'), ('other', 'Other')] 
LifeStyle_CHOICES = [('Sedentary', 'Sedentary'), ('Lightly active', 'Lightly active'), ('Moderately active', 'Moderately active'), ('Active', 'Active'), ('Very active', 'Very active')]

class User(AbstractUser):
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True, choices=GENDER_CHOICES)
    height = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    aimed_weight = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    aimed_date = models.DateField(blank=True, null=True)
    aimed_water_intake = models.DecimalField(max_digits=3, decimal_places=2, default=2.0)  # in liters
    age = models.PositiveIntegerField(blank=True, null=True)
    life_style = models.CharField(max_length=20, choices=LifeStyle_CHOICES, blank=True, null=True)
    water_intake_goal_ml = models.PositiveIntegerField(default=2000)  # in milliliters
    water_intake_type_preference = models.ForeignKey(WaterIntakeType, on_delete=models.SET_NULL, blank=True, null=True)

    # Notification preferences (toggles synced from the Alerts page).
    alert_meal_reminders = models.BooleanField(default=True)
    alert_water_reminders = models.BooleanField(default=True)
    alert_weekly_summary = models.BooleanField(default=True)
    alert_goal_achievements = models.BooleanField(default=True)

    # True for anonymous "guest" accounts (no email yet). Cleared when the user
    # upgrades by signing in with Google/Apple.
    is_guest = models.BooleanField(default=False)

    def __str__(self):
        return self.username


class GuestScanUsage(models.Model):
    """Per-day AI food-scan counter for guest accounts, used to cap the (paid)
    Gemini/Spoonacular calls a guest can trigger before being asked to sign in."""

    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='guest_scan_usage')
    date = models.DateField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('user', 'date')

    def __str__(self):
        return f"{self.user_id} {self.date}: {self.count}"


class Feedback(models.Model):
    """User-submitted feedback (rating + free-form message)."""
    user = models.ForeignKey(
        'User', on_delete=models.CASCADE, related_name='feedback_entries',
        blank=True, null=True,
    )
    rating = models.PositiveSmallIntegerField(default=0)  # 0-5
    message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f"Feedback({self.rating}★) by {self.user_id}"