"""Delete all existing WaterIntake records (test data cleanup)."""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "colorofit.settings")
django.setup()

from food.models import WaterIntake

count = WaterIntake.objects.count()
print(f"Deleting {count} water intake records...")
WaterIntake.objects.all().delete()
print(f"Done. Remaining: {WaterIntake.objects.count()}")
