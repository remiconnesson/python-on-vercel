# Django on Vercel

A trimmed `startproject` Django app that deploys to Vercel with **zero configuration**: no `vercel.json`, no `/api` folder, no WhiteNoise. Vercel finds `manage.py`, imports the settings to get `WSGI_APPLICATION`, and runs the whole Django app as one Vercel Function (Fluid compute). Because `STATIC_ROOT` is set, Vercel runs `collectstatic` during the build and serves the results from its CDN. That covers both this app's CSS and the Django admin's own CSS/JS. The app needs no database. Postgres is optional and only used for admin login.

## Files

```
02-django/
├── manage.py                 # Vercel detects Django here (it must mention DJANGO_SETTINGS_MODULE)
├── pyproject.toml            # deps + [tool.vercel.scripts] build hook (migrate only if DATABASE_URL is set)
├── uv.lock                   # Vercel installs from this with uv
├── .python-version           # 3.12 (Vercel's default; 3.13 and 3.14 also work)
└── mysite/                   # project package, also listed in INSTALLED_APPS
    ├── settings.py           # WSGI_APPLICATION, STATIC_ROOT, ALLOWED_HOSTS, optional DATABASE_URL
    ├── wsgi.py               # `application`, the object Vercel serves
    ├── urls.py               # /, /api/info, /admin/
    ├── views.py              # one template view, one JSON view
    ├── templates/mysite/index.html
    └── static/mysite/style.css
```

## Run locally

```bash
uv sync
DJANGO_DEBUG=1 uv run python manage.py runserver   # http://127.0.0.1:8000
```

`DEBUG` is off unless `DJANGO_DEBUG=1`. With `DEBUG` off, `runserver` does not serve static files. Use `runserver --insecure` in that case, or run `uv run vercel dev --local`, which serves them the way Vercel does.

To try the admin locally (SQLite), run `uv run python manage.py migrate && uv run python manage.py createsuperuser`.

## Deploy

Vercel project settings:

- **Framework Preset:** Django (auto-detected)
- **Root Directory:** `02-django`
- **Build / Install / Output commands:** leave them at the defaults. A Build Command set in the dashboard replaces the `[tool.vercel.scripts]` build hook.

Environment variables:

| Name | Required | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Recommended | Signing key. Without it, the settings fall back to a public dev key. Generate one with `uv run python -c 'from django.core.management.utils import get_random_secret_key as g; print(g())'` |
| `DJANGO_DEBUG` | No | Set to `1` to turn on debug pages. Don't do this in production. |
| `DATABASE_URL` | No | Postgres connection string. Only the admin login uses it. Vercel sets it when you add Neon (or another Postgres) from the Marketplace. |

No external resources are needed to deploy. `ALLOWED_HOSTS` is filled from Vercel system env vars (`VERCEL_URL`, `VERCEL_BRANCH_URL`, `VERCEL_PROJECT_PRODUCTION_URL`), so deployment URLs, branch aliases and the production domain all work, whatever domain the team uses.

### Optional: enable the admin with Postgres

1. Add Neon from the Vercel Marketplace (Storage tab) to the project. This sets `DATABASE_URL`.
2. Redeploy. The build hook runs `manage.py migrate` because `DATABASE_URL` is now set. Neon's Vercel integration gives each preview deployment its own branch, so previews never migrate production.
3. Create an admin user against that database:
   ```bash
   vercel env pull .env.local
   uv run --env-file .env.local python manage.py createsuperuser
   ```

Without `DATABASE_URL`, `/admin/login/` still renders (styled), but submitting it returns a 500. The fallback SQLite file can't be created because the deployment filesystem is read-only.

## Endpoints

```bash
URL=https://<your-deployment>.vercel.app   # or http://127.0.0.1:8000 locally

curl $URL/                              # HTML template view listing endpoints + runtime info
curl $URL/api/info                      # {"python": "3.12.x", "django": "6.1.x", "vercel_env": "production", "vercel_region": "iad1", "database": "sqlite3"}
curl -I $URL/static/mysite/style.css    # app CSS, served by the Vercel CDN
curl -I $URL/static/admin/css/base.css  # admin CSS from the Django package, also on the CDN
curl -I $URL/admin/                     # 302 to /admin/login/
```
