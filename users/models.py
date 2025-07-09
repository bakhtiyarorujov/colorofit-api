from django.db import models
from django.contrib.auth.models import AbstractUser
# Create your models here.


class LifeStyle(models.Model):
    name = models.CharField(max_length=100)

GENDER_CHOICES = [('female', 'Female'), ('male', 'Male'), ('other', 'Other')] 

class User(AbstractUser):
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True, choices=GENDER_CHOICES)
    height = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    aimed_weight = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    aimed_date = models.DateField(blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    life_style = models.ForeignKey(LifeStyle, on_delete=models.CASCADE, blank=True, null=True)
    
    def __str__(self):
        return self.username