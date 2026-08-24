"""
Pre-warms the recipe-search cache for every fixed category chip (see
RECIPE_CATEGORIES in food.views), in every translated language (az, ru).

Browsing by category is the app's most common recipe-search path, and on a
cache miss it pays a live Spoonacular call plus a Gemini translation round
trip — a few seconds each, and worse if several land on the server at once
(PythonAnywhere's free/Beginner tier runs a single worker, so concurrent
requests queue up behind each other instead of running in parallel). This
command does that expensive work once, up front, using the *exact* same
cache keys SpoonacularRecipeSearchView builds — so real user requests hit
a warm cache instead.

Run manually after a deploy:

    python manage.py warm_recipe_cache

Or, better, set it up as a PythonAnywhere scheduled task (Tasks tab) to run
roughly once a day — comfortably inside the 3-day cache TTL — so the cache
never goes fully cold.
"""
import requests as rq
from django.core.cache import cache
from django.core.management.base import BaseCommand

from food.views import (
    RECIPE_CATEGORIES,
    RECIPE_TRANSLATE_LANGS,
    SPOONACULAR_API_KEY,
    _translate_search_results,
)

# Must match SpoonacularRecipeSearchView.MAX_PAGE_SIZE / the mobile app's
# default page size — a different number here would warm a cache key real
# requests never look up.
PAGE_SIZE = 20

# Matches the cache TTL in SpoonacularRecipeSearchView (search + translate).
CACHE_TTL_SECONDS = 60 * 60 * 24 * 3


class Command(BaseCommand):
    help = "Pre-warms the recipe-search + translation cache for every category chip."

    def handle(self, *args, **options):
        for category in RECIPE_CATEGORIES:
            meal_type = category["type"] or ""
            # Must exactly match the cache_key format built in
            # SpoonacularRecipeSearchView.get() — query/cuisine/diet are
            # always empty for plain category browsing, sort defaults to
            # 'popularity'.
            cache_key = f"spoon_search:|{PAGE_SIZE}|0|{meal_type}|||popularity"

            data = cache.get(cache_key)
            if data is None:
                params = {
                    "number": PAGE_SIZE,
                    "offset": 0,
                    "addRecipeNutrition": "true",
                    "apiKey": SPOONACULAR_API_KEY,
                    "sort": "popularity",
                }
                if meal_type:
                    params["type"] = meal_type

                try:
                    resp = rq.get(
                        "https://api.spoonacular.com/recipes/complexSearch",
                        params=params,
                        timeout=15,
                    )
                except rq.RequestException as e:
                    self.stderr.write(
                        self.style.ERROR(f"[{category['key']}] Spoonacular request failed: {e}")
                    )
                    continue

                if resp.status_code != 200:
                    self.stderr.write(self.style.ERROR(
                        f"[{category['key']}] Spoonacular error {resp.status_code}: "
                        f"{resp.text[:200]}"
                    ))
                    continue

                data = resp.json()
                data["offset"] = 0
                data["number"] = PAGE_SIZE
                data["hasMore"] = PAGE_SIZE < data.get("totalResults", 0)
                cache.set(cache_key, data, CACHE_TTL_SECONDS)
                self.stdout.write(f"[{category['key']}] base results cached.")
            else:
                self.stdout.write(f"[{category['key']}] base results already warm.")

            for lang_code, lang_name in RECIPE_TRANSLATE_LANGS.items():
                tr_key = f"{cache_key}|tr:{lang_code}"
                if cache.get(tr_key) is not None:
                    self.stdout.write(f"[{category['key']}] {lang_code} already warm.")
                    continue
                translated = _translate_search_results(data, lang_name)
                cache.set(tr_key, translated, CACHE_TTL_SECONDS)
                self.stdout.write(
                    self.style.SUCCESS(f"[{category['key']}] {lang_code} translated + cached.")
                )

        self.stdout.write(self.style.SUCCESS("Done."))
