# ColorOfit API — Deployment & Configuration

Django REST API backing the CaloriLens mobile app. Hosted on PythonAnywhere
(`colorofit.pythonanywhere.com`). Requires **Python 3.10+** (Django 5.2).

## Local development

```bash
python3.13 -m venv .venv313
.venv313/bin/pip install -r requirements.txt
cp .env.example .env          # then fill in the values (see below)
.venv313/bin/python manage.py migrate
.venv313/bin/python manage.py runserver
```

For local dev set `DJANGO_DEBUG=True` in `.env`.

## Environment variables

All secrets and environment-specific config are read from the environment
(loaded from `.env` via `python-dotenv`). Nothing sensitive lives in the code.
See `.env.example` for the full list. Key ones:

| Variable | Purpose |
|----------|---------|
| `DJANGO_SECRET_KEY` | **Required in prod.** Generate a fresh 50+ char key. |
| `DJANGO_DEBUG` | `False` in prod (default), `True` for local dev. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts. |
| `GOOGLE_OAUTH_CLIENT_ID` | Google Sign-In audience (matches mobile client). |
| `APPLE_CLIENT_IDS` | Comma-separated Apple audiences (iOS bundle id). |
| `GEMINI_API_KEY` / `SPOONACULAR_API_KEY` | External API keys. |
| `DB_ENGINE` + `DB_*` | Set to use MySQL instead of SQLite (see below). |

Generate a secret key:

```bash
.venv313/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Running tests

```bash
.venv313/bin/python manage.py test
```

35 tests cover the TDEE/macro engine, Google/Apple auth (incl. forged-token
rejection), food recognition, stats aggregation, water logging, and permissions.

## Production go-live checklist

- [ ] **Rotate the leaked API keys.** `GEMINI_API_KEY`, `SPOONACULAR_API_KEY`,
      and the old `CLARIFAI_PAT` were committed to git history in the past.
      Revoke/regenerate them in each provider console before launch.
- [ ] Set `DJANGO_SECRET_KEY` to a fresh value on the server (never reuse the
      dev fallback — `manage.py check --deploy` warns about it).
- [ ] Set all env vars in the PythonAnywhere `.env` (or the WSGI file).
- [ ] Keep `DJANGO_DEBUG` unset/`False`.
- [ ] Run `python manage.py check --deploy` — should be clean apart from any
      remaining drf-spectacular schema doc notes.
- [ ] **Database:** the repo historically committed `db.sqlite3`. Before
      changing DB tracking, confirm what the live site actually uses. For a
      real launch, move to PythonAnywhere MySQL by setting `DB_ENGINE` +
      `DB_*`, then `manage.py migrate`. Do **not** remove the committed
      `db.sqlite3` from git and redeploy without first securing production data.
- [ ] `python manage.py collectstatic` and confirm the PythonAnywhere static
      (`/static/`) and media (`/media/`) mappings are configured.
- [ ] Reload the web app.

## Security notes

- Apple Sign-In tokens are verified against Apple's public JWKS
  (signature + issuer + audience). Forged/unsigned tokens are rejected.
- The AI (`/food/predict-food/`) and recipe endpoints are rate-limited
  (`food_scan`, `recipe_search` scopes) to protect paid API quota.
- Error responses no longer include stack traces; full tracebacks go to the
  server log only.
