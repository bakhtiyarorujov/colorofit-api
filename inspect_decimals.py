"""Inspect raw SQLite values for FoodItem decimal fields."""
import sqlite3, decimal, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "colorofit.settings")
import django; django.setup()
from django.conf import settings

FIELDS = ["calories","protein","carbohydrates","fats","trans_fat","saturated_fat",
          "vitamin_a","vitamin_c","vitamin_d","vitamin_e","vitamin_k",
          "mineral_calcium","mineral_iron","mineral_sodium","mineral_potassium","mineral_zink"]

conn = sqlite3.connect(settings.DATABASES["default"]["NAME"])
cur = conn.cursor()
cur.execute(f"SELECT id, {', '.join(FIELDS)} FROM food_fooditem")
fixed = 0
for row in cur.fetchall():
    rid = row[0]
    updates = {}
    for i, field in enumerate(FIELDS, start=1):
        raw = row[i]
        print(f"row {rid} {field} = {raw!r} (type={type(raw).__name__})")
        # Try Django's exact path
        try:
            if raw is None:
                continue
            decimal.Decimal(raw)
        except Exception as e:
            print(f"  >>> BAD: {e}")
            updates[field] = "0.00"
    if updates:
        fixed += 1
        set_clause = ", ".join(f"{f} = ?" for f in updates)
        vals = list(updates.values()) + [rid]
        cur.execute(f"UPDATE food_fooditem SET {set_clause} WHERE id = ?", vals)
        print(f"  FIXED row {rid}: {list(updates.keys())}")

conn.commit()
conn.close()
print(f"\nFixed {fixed} rows.")
