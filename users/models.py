from django.db import models
from django.contrib.auth.models import AbstractUser
# Create your models here.


class WaterIntakeType(models.Model):
    name = models.CharField(max_length=100)
    amount_ml = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.amount_ml} ml"

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
    
    def __str__(self):
        return self.username