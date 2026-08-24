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

Or, better, set it up as a PythonAnywhere scheduled task (Tasks tab).

IMPORTANT — Spoonacular's real free-plan budget is tiny (50 points/day, per
their own dashboard), and this command alone can burn through a large chunk
of it (10 categories x a costly `addRecipeNutrition` search each). Two
safeguards keep that in check even if the PythonAnywhere task is still set
to run daily:

1. WARM_LOCK: this command no-ops if it already ran within WARM_LOCK_TTL_SECONDS
   (set just under the search cache's own TTL), so it only actually spends
   quota roughly once per that window, not every day.
2. It shares food.views' SPOONACULAR_DAILY_BUDGET guard with the live search
   /detail views, so a warm run and real user traffic on the same day draw
   from one combined daily ceiling instead of each getting their own.
"""
import time

import requests as rq
from django.core.cache import cache
from django.core.management.base import BaseCommand

from food.views import (
    RECIPE_CATEGORIES,
    RECIPE_TRANSLATE_LANGS,
    SEARCH_CACHE_TTL,
    SPOONACULAR_API_KEY,
    SPOONACULAR_DAILY_BUDGET,
    _spoonacular_budget_exceeded,
    _spoonacular_exhaust_budget_for_today,
    _spoonacular_note_request,
    _translate_search_results,
)

# Must match SpoonacularRecipeSearchView.MAX_PAGE_SIZE / the mobile app's
# default page size — a different number here would warm a cache key real
# requests never look up.
PAGE_SIZE = 20

# Skip the whole run if the last one was within this window. Kept a bit
# under SEARCH_CACHE_TTL (7 days) so a run lands shortly before the cache
# would actually go cold, instead of re-spending the budget every single
# day the PythonAnywhere task happens to fire.
WARM_LOCK_KEY = "warm_recipe_cache:last_run"
WARM_LOCK_TTL_SECONDS = 60 * 60 * 24 * 6  # 6 days


class Command(BaseCommand):
    help = "Pre-warms the recipe-search + translation cache for every category chip."

    def handle(self, *args, **options):
        if cache.get(WARM_LOCK_KEY):
            self.stdout.write(
                "Skipping — already warmed within the last "
                f"{WARM_LOCK_TTL_SECONDS // 86400} days. Spoonacular's free-plan "
                "budget is tiny; re-warming every time this task fires would "
                "waste most of it on categories nobody may open today. Delete "
                f"the '{WARM_LOCK_KEY}' cache key (or wait it out) to force a run."
            )
            return

        for category in RECIPE_CATEGORIES:
            if _spoonacular_budget_exceeded():
                self.stdout.write(self.style.WARNING(
                    f"Today's Spoonacular budget ({SPOONACULAR_DAILY_BUDGET} requests) "
                    f"is spent — stopping before [{category['key']}]. Remaining "
                    "categories will warm on a later run or lazily from real traffic."
                ))
                break

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

                _spoonacular_note_request()

                if resp.status_code != 200:
                    self.stderr.write(self.style.ERROR(
                        f"[{category['key']}] Spoonacular error {resp.status_code}: "
                        f"{resp.text[:200]}"
                    ))
                    if resp.status_code == 402:
                        # The real plan quota is gone — stop the whole run
                        # instead of burning through the rest of the
                        # categories on requests that will all fail the
                        # same way.
                        _spoonacular_exhaust_budget_for_today()
                        self.stdout.write(self.style.WARNING(
                            "Spoonacular reports the daily quota is exhausted — stopping run."
                        ))
                        break
                    continue

                data = resp.json()
                data["offset"] = 0
                data["number"] = PAGE_SIZE
                data["hasMore"] = PAGE_SIZE < data.get("totalResults", 0)
                cache.set(cache_key, data, SEARCH_CACHE_TTL)
                self.stdout.write(f"[{category['key']}] base results cached.")
            else:
                self.stdout.write(f"[{category['key']}] base results already warm.")

            for lang_code, lang_name in RECIPE_TRANSLATE_LANGS.items():
                tr_key = f"{cache_key}|tr:{lang_code}"
                if cache.get(tr_key) is not None:
                    self.stdout.write(f"[{category['key']}] {lang_code} already warm.")
                    continue
                translated, ok = _translate_search_results(data, lang_name)
                # Only cache a translation that actually succeeded. This
                # loop fires ~20 Gemini calls back-to-back (10 categories x
                # 2 languages); if one gets rate-limited or times out and we
                # cache its fail-open (still-English) result anyway, that
                # category+language is then stuck showing English for the
                # full cache TTL, regardless of what language the user
                # picks in the app — which is exactly what was happening.
                if ok:
                    cache.set(tr_key, translated, SEARCH_CACHE_TTL)
                    self.stdout.write(
                        self.style.SUCCESS(f"[{category['key']}] {lang_code} translated + cached.")
                    )
                else:
                    self.stderr.write(self.style.WARNING(
                        f"[{category['key']}] {lang_code} translation failed — "
                        "not caching, will retry on a later run or a live request."
                    ))
                # A short pause between Gemini calls so a burst of ~20 in a
                # row doesn't trip a per-minute rate limit itself. (Gemini
                # calls don't touch the Spoonacular budget above.)
                time.sleep(1)

        cache.set(WARM_LOCK_KEY, True, WARM_LOCK_TTL_SECONDS)
        self.stdout.write(self.style.SUCCESS("Done."))
