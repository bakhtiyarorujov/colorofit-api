"""Replace garbage water intake types with sensible defaults."""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "colorofit.settings")
django.setup()

from users.models import WaterIntakeType

defaults = [
    ("Glass", 250),
    ("Bottle", 500),
    ("Cup", 200),
]

print("BEFORE:")
for t in WaterIntakeType.objects.all():
    print(f"  id={t.id} name={t.name!r} amount_ml={t.amount_ml}")

# Update existing or create
existing = list(WaterIntakeType.objects.order_by('id'))
for i, (name, ml) in enumerate(defaults):
    if i < len(existing):
        t = existing[i]
        t.name = name
        t.amount_ml = ml
        t.save()
        print(f"Updated id={t.id} -> {name} ({ml}ml)")
    else:
        t = WaterIntakeType.objects.create(name=name, amount_ml=ml)
        print(f"Created id={t.id} -> {name} ({ml}ml)")

# Delete any extras
for t in existing[len(defaults):]:
    print(f"Deleting id={t.id} name={t.name}")
    t.delete()

print("\nAFTER:")
for t in WaterIntakeType.objects.all():
    print(f"  id={t.id} name={t.name!r} amount_ml={t.amount_ml}")
