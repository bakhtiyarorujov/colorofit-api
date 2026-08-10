"""AI explanation layer over the deterministic calorie/macro engine.

ALL numbers come from the formula: `TargetDetailSerializer` computes the daily
calorie target (Mifflin-St Jeor + activity + capped goal deficit) and the
protein/fat/carb split. This module does NOT change any of those numbers — it
only asks Claude to write a short, personalised explanation and a few practical
tips, in the user's language, about the plan the formula already produced.

Everything degrades gracefully: if no API key is configured or the call fails,
we return a `null` summary and empty tips, so the endpoint never breaks because
of the AI layer.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

# Fast, low-cost model for this high-frequency endpoint; overridable per-deploy
# via NUTRITION_AI_MODEL (e.g. "claude-sonnet-5" or "claude-opus-5").
ANTHROPIC_MODEL = os.environ.get("NUTRITION_AI_MODEL", "claude-haiku-4-5")

_LANG_NAMES = {"az": "Azerbaijani", "en": "English", "ru": "Russian"}

# The AI returns text only — never numbers. The macros are the formula's.
_ADVICE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "tips": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "tips"],
    "additionalProperties": False,
}


def _client():
    """Lazily build the Anthropic client. Returns None when unavailable so the
    caller can fall back instead of raising."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic SDK not installed; skipping AI nutrition layer")
        return None
    return anthropic.Anthropic(api_key=api_key)


def _goal(user):
    if user.weight and user.aimed_weight:
        delta = float(user.weight) - float(user.aimed_weight)
        if delta > 0:
            return "lose weight"
        if delta < 0:
            return "gain weight"
    return "maintain weight"


def _prompt(user, targets, language_name):
    """All numbers are the formula's — the model only explains them."""
    return (
        "You are a nutrition assistant for a calorie-tracking app.\n"
        "The daily targets below were computed by a validated formula "
        "(Mifflin-St Jeor + activity factor + a capped goal deficit). They are "
        "final — do NOT recompute or change any number, and do not output "
        "numbers of your own.\n\n"
        "Write a short, encouraging `summary` (2-3 sentences) explaining what "
        "these targets mean for THIS person and their goal, plus 2-4 concrete, "
        "practical `tips` for hitting them.\n"
        f"Write everything in {language_name}.\n\n"
        "USER:\n"
        f"- gender: {user.gender}\n"
        f"- age: {user.age}\n"
        f"- height_cm: {user.height}\n"
        f"- weight_kg: {user.weight}\n"
        f"- aimed_weight_kg: {user.aimed_weight}\n"
        f"- activity: {user.life_style}\n"
        f"- goal: {_goal(user)}\n\n"
        "DAILY TARGETS (final, formula-computed):\n"
        f"- calories: {targets.get('calorie_target')}\n"
        f"- protein_g: {targets.get('protein_target')}\n"
        f"- fat_g: {targets.get('fat_target')}\n"
        f"- carbs_g: {targets.get('carbs_target')}\n"
    )


def build_nutrition_advice(user, targets, language="en"):
    """Return an AI-written explanation of the formula's plan.

    Always returns a dict with `summary` (str or None), `tips` (list), and
    `ai_generated` (bool). It never contains or affects any calorie/macro
    number — those live in `targets`, straight from the formula. Degrades to a
    null summary whenever the AI layer is unavailable.
    """
    fallback = {"summary": None, "tips": [], "ai_generated": False}

    if int(targets.get("calorie_target") or 0) <= 0:
        return fallback

    client = _client()
    if client is None:
        return fallback

    language_name = _LANG_NAMES.get((language or "en").lower(), "English")

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            # Note: no `effort` here — Haiku 4.5 (the default model) rejects it.
            output_config={
                "format": {"type": "json_schema", "schema": _ADVICE_SCHEMA},
            },
            messages=[{"role": "user", "content": _prompt(user, targets, language_name)}],
        )
    except Exception:
        logger.exception("nutrition AI call failed; returning null summary")
        return fallback

    if response.stop_reason == "refusal":
        logger.warning("nutrition AI refused; returning null summary")
        return fallback

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        return fallback

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        logger.exception("nutrition AI returned unparseable output; null summary")
        return fallback

    return {
        "summary": data.get("summary"),
        "tips": data.get("tips") or [],
        "ai_generated": True,
    }
