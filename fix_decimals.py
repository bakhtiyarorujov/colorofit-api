"""
Bütün FoodItem sətirlərini gəzir və etibarsız Decimal dəyərləri (NaN, boş, qeyri-numerik)
0.00 ilə əvəz edir. PythonAnywhere Bash konsolunda işlət:
    cd ~/colorofit-api && source .venv/bin/activate && python fix_decimals.py
"""
import os
import sys
import django
import sqlite3
import decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "colorofit.settings")
django.setup()

from django.conf import settings

DECIMAL_FIELDS = [
    "calories", "protein", "carbohydrates", "fats",
    "trans_fat", "saturated_fat",
    "vitamin_a", "vitamin_c", "vitamin_d", "vitamin_e", "vitamin_k",
    "mineral_calcium", "mineral_iron", "mineral_sodium",
    "mineral_potassium", "mineral_zink",
]

db_path = settings.DATABASES["default"]["NAME"]
print(f"DB: {db_path}")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

fixed_rows = 0
fixed_cells = 0
cur.execute(f"SELECT id, {', '.join(DECIMAL_FIELDS)} FROM food_fooditem")
rows = cur.fetchall()
print(f"Total rows: {len(rows)}")

for row in rows:
    updates = {}
    for field in DECIMAL_FIELDS:
        raw = row[field]
        if raw is None:
            continue
        try:
            d = decimal.Decimal(str(raw))
            if d.is_nan() or d.is_infinite():
                updates[field] = "0.00"
        except (decimal.InvalidOperation, TypeError, ValueError):
            updates[field] = "0.00"

    if updates:
        fixed_rows += 1
        fixed_cells += len(updates)
        set_clause = ", ".join(f"{f} = ?" for f in updates)
        values = list(updates.values()) + [row["id"]]
        cur.execute(f"UPDATE food_fooditem SET {set_clause} WHERE id = ?", values)
        print(f"  Row {row['id']} fixed fields: {list(updates.keys())}")

conn.commit()
conn.close()
print(f"\nDone. Fixed {fixed_cells} cells across {fixed_rows} rows.")
