# Research: Django on Vercel (October 2026)

## What's available

**Official Vercel docs and changelog**

- [Deploy a Django app on Vercel](https://vercel.com/docs/frameworks/full-stack/django) (the old URL [/docs/frameworks/backend/django](https://vercel.com/docs/frameworks/backend/django) points here). The primary reference: `manage.py` detection, WSGI/ASGI resolution, `tool.vercel.entrypoint`, the `[tool.vercel.scripts] build` hook, automatic `collectstatic` → CDN, WhiteNoise/django-storages notes, a `DATABASE_URL` snippet, Django Channels WebSockets, and `functions` config keyed by `myproject/wsgi.py`.
- [Changelog: Zero-configuration Django support](https://vercel.com/changelog/zero-configuration-django-support) (April 9, 2026). Django is detected with no `vercel.json` and no `/api` folder, runs on Fluid compute with Active CPU pricing, and its static files are served by the CDN.
- [Python runtime](https://vercel.com/docs/functions/runtimes/python). Entrypoint rules: Django's `application` name and `manage.py` in the root or an immediate subdirectory. Also covers dependencies from `pyproject.toml`/`uv.lock`, "no automatic tree-shaking", `excludeFiles`, and precompiled bytecode.
- [Python version](https://vercel.com/docs/functions/runtimes/python/python-version) and [Python 3.13 and 3.14 are now available](https://vercel.com/changelog/python-3-13-and-3-14-are-now-available) (Feb 2, 2026). The versions are 3.12 (default), 3.13 and 3.14. The changelog says the default will move to 3.14.
- [Functions limits](https://vercel.com/docs/functions/limitations): 500 MB Python bundle (5 GB with Large Functions beta), 300 s default duration, 4.5 MB request/response body, 2 GB / 1 vCPU default memory.
- [System environment variables](https://vercel.com/docs/environment-variables/system-environment-variables): `VERCEL_ENV`, `VERCEL_REGION`, `VERCEL_URL`, and `VERCEL_PROJECT_PRODUCTION_URL` ("set even in preview deployments").

**Official templates and examples**

- [vercel/vercel `examples/django`](https://github.com/vercel/vercel/tree/main/examples/django) is what `vc init django` clones. It has a single `app` package that is both project and app, `DATABASES = {}`, `STATIC_ROOT = 'staticfiles'`, and `DEBUG = True`.
- [vercel/examples `python/django`](https://github.com/vercel/examples/tree/main/python/django) is the [Django Hello World template](https://vercel.com/templates/backend/django-hello-world) (demo: django-template.vercel.app). It is a full startproject (admin included) with `DJANGO_SECRET_KEY` and `DJANGO_DEBUG` env vars and `ALLOWED_HOSTS = ["127.0.0.1", "localhost", ".vercel.app"]`. It keeps SQLite, so admin login can't work once deployed.
- [vercel/examples `python/django-notes`](https://github.com/vercel/examples/tree/main/python/django-notes) is the [Django Notes template](https://vercel.com/templates/python/django-notes). It uses SQLite locally and Postgres when `DATABASE_URL` is set (stdlib `urllib.parse`, `psycopg[binary]`). Migrations run on each deploy via `[tool.vercel.scripts] build = 'if [ -n "$DATABASE_URL" ]; then python manage.py migrate --noinput; fi'`, and the README recommends Neon branching for previews.
- [vercel/examples `python/django-rest-framework`](https://github.com/vercel/examples/tree/main/python/django-rest-framework) is a minimal DRF API (`/api/time/`).

**Builder source (how it actually works)**

- [`packages/python/src/django.ts`](https://github.com/vercel/vercel/blob/main/packages/python/src/django.ts) implements collectstatic. It writes a temporary settings shim that sets `STATIC_ROOT` to `.vercel/output/static/<STATIC_URL>`, runs `manage.py collectstatic --noinput`, and copies `staticfiles.json` into the function for manifest storages. It skips collectstatic when there is no `STATIC_ROOT` and no `WHITENOISE_USE_FINDERS`, and with django-storages it runs collectstatic with your real settings.
- [`packages/python/templates/vc_django_settings.py`](https://github.com/vercel/vercel/blob/main/packages/python/templates/vc_django_settings.py) handles settings discovery. It runs `manage.py` with a patched `execute_from_command_line`, imports `DJANGO_SETTINGS_MODULE`, and dumps all uppercase settings as JSON.
- [`packages/python/src/entrypoint.ts`](https://github.com/vercel/vercel/blob/main/packages/python/src/entrypoint.ts) and [`index.ts`](https://github.com/vercel/vercel/blob/main/packages/python/src/index.ts) hold the detection logic. A `manage.py` containing the string `DJANGO_SETTINGS_MODULE` must sit in the root or an immediate subdirectory. ASGI_APPLICATION takes priority over WSGI_APPLICATION, and the function bundle excludes `**/public/**`, `.venv`, and `__pycache__`.
- [`packages/frameworks/src/frameworks.ts`](https://github.com/vercel/vercel/blob/main/packages/frameworks/src/frameworks.ts) defines the Django preset. The detectors are `django` in requirements.txt, pyproject.toml, or Pipfile, or a `manage.py` containing `DJANGO_SETTINGS_MODULE`. The build and dev commands default to none.
- [`packages/python/CHANGELOG.md`](https://github.com/vercel/vercel/blob/main/packages/python/CHANGELOG.md) records the Django work: entrypoint detection (#15167), loading settings dynamically (#15367), collectstatic → CDN (#15391), manifest storage fixes (#15709), and keeping app `static/` dirs in the bundle (#15705).
- [`python/vercel-runtime/.../vc_init.py`](https://github.com/vercel/vercel/blob/main/python/vercel-runtime/src/vercel_runtime/vc_init.py) builds the WSGI environ. It sets `wsgi.url_scheme` from `x-forwarded-proto`, so Django sees HTTPS without `SECURE_PROXY_SSL_HEADER`.

**Upstream and ecosystem**

- [Django 6.1 release notes](https://docs.djangoproject.com/en/6.1/releases/6.1/) (Aug 2026): Python 3.12–3.14, PostgreSQL 15+, SQLite 3.37+.
- [Django deployment checklist](https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/) covers `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `STATIC_ROOT`, and `check --deploy`.
- [WhiteNoise Django guide](https://whitenoise.readthedocs.io/en/latest/django.html) (v6.12.0). On Vercel it only matters for `vercel dev`, because production static files come from the CDN.
- [dj-database-url](https://github.com/jazzband/dj-database-url) parses `DATABASE_URL` and passes query params (e.g. Neon's `sslmode=require`, `channel_binding=require`) through to `OPTIONS`.
- Neon: [Vercel-managed integration](https://neon.com/docs/guides/neon-managed-vercel-integration) and [preview branching](https://neon.com/docs/guides/vercel-previews-integration). The integration injects `DATABASE_URL` (pooled) and `DATABASE_URL_UNPOOLED` and creates a branch per preview deployment.
- Latest PyPI versions (via [Django](https://pypi.org/pypi/django/json), [dj-database-url](https://pypi.org/pypi/dj-database-url/json), [psycopg](https://pypi.org/pypi/psycopg/json), and [whitenoise](https://pypi.org/pypi/whitenoise/json) JSON): Django 6.1.2 (Oct 6, 2026), dj-database-url 3.1.2, psycopg 3.3.6, whitenoise 6.12.0.
- Legacy community guides such as [dev.to/petrjoe (Oct 2024)](https://dev.to/petrjoe/how-to-deploying-django-on-vercel-43ek) use the pre-zero-config approach: `vercel.json` `builds`/`routes`, `@vercel/python`, a `build_files.sh` that runs collectstatic, and an `app = application` alias. **This approach is obsolete now.** Similar guides appear in search results (e.g. [codewitgabi](https://dev.to/codewitgabi/hosting-your-django-project-on-vercel-a-quick-and-easy-deployment-3217), [ksharma20](https://dev.to/ksharma20/how-to-deploy-a-django-web-app-on-vercel-for-free-4fhe)).

## How it works on Vercel

1. **Detection.** The Django preset is picked when `manage.py` contains `DJANGO_SETTINGS_MODULE`, or `django` appears in your dependency file. `manage.py` may be in the root or one level down.
2. **Install.** uv installs from `pyproject.toml` + `uv.lock` (or `requirements.txt`/Pipfile). The Python version comes from `.python-version` or `requires-python` and defaults to 3.12.
3. **Settings discovery (at build time).** The builder runs `manage.py` with `execute_from_command_line` stubbed out, imports the settings module, and reads `WSGI_APPLICATION` / `ASGI_APPLICATION` (ASGI wins), `STATIC_URL`, `STATIC_ROOT`, `STORAGES`, `INSTALLED_APPS`, and so on. `mysite.wsgi.application` becomes entrypoint `mysite/wsgi.py`, variable `application`.
4. **Static files.** If `STATIC_ROOT` is set, `collectstatic` runs with `STATIC_ROOT` redirected to `.vercel/output/static/static/`. Every finder is included, so the admin's assets inside site-packages are collected too. The files are served by the CDN at `STATIC_URL` before any request reaches Django (`handle: filesystem` route).
5. **Build hook.** `[tool.vercel.scripts] build` in `pyproject.toml` runs after install. A dashboard or `vercel.json` Build Command overrides it.
6. **Runtime.** The whole Django app is one Vercel Function on Fluid compute, so instances are reused across requests. The filesystem is read-only (the builder sets `PYTHONDONTWRITEBYTECODE=1`) apart from ephemeral `/tmp`. Limits: 300 s default duration (Pro up to 800 s), 4.5 MB body, 500 MB bundle.

## Gotchas

- **Settings run at build time.** Anything the settings module needs at import (env vars, imports) must also be available during the build, and the settings must not touch the network or database at import.
- **No `STATIC_ROOT` means no collectstatic.** Vercel then logs "No collectstatic strategy configured" and the admin comes up unstyled. Don't run `collectstatic` in your own build script, because Vercel already does it.
- **SQLite doesn't work once deployed.** The deployment filesystem is read-only and `/tmp` is per-instance and ephemeral. The official Hello World template keeps SQLite, so its admin login would fail. Use Postgres from the Marketplace (`DATABASE_URL`). The `urllib.parse` snippet in the docs drops query params such as `sslmode`. It still works with Neon (libpq's default `sslmode=prefer` negotiates TLS), but dj-database-url keeps them.
- **Migrations have no release phase.** Run them in the `[tool.vercel.scripts] build` hook (guarded by `DATABASE_URL`) or from your machine after `vercel env pull`. If migrations run on every build, preview deployments need an isolated database, such as Neon branches.
- **`ALLOWED_HOSTS` matters once `DEBUG=False`.** `.vercel.app` covers default production and preview URLs, but not custom domains or teams with a custom preview suffix. The system env vars `VERCEL_URL`, `VERCEL_BRANCH_URL` and `VERCEL_PROJECT_PRODUCTION_URL` hold the actual hostnames.
- **HTTPS is already detected.** The runtime maps `x-forwarded-proto` to `wsgi.url_scheme`, so CSRF Origin checks pass. `check --deploy` still warns about HSTS, SSL redirect, and secure cookies (W004/W008/W012/W016) until you set those explicitly.
- **Static cache headers.** `vercel dev` served `/static/*` with `cache-control: public, max-age=0, must-revalidate`, and the deployed CDN likely does the same. For long-lived caching, use `ManifestStaticFilesStorage` (hashed names; Vercel copies `staticfiles.json` into the function) and add headers.
- **Bundle contents.** There is no tree-shaking: everything except `.venv`, `__pycache__`, `**/public/**`, and `.git` ships in the function. Don't keep templates under a `public/` directory.
- **Uploads and media.** Bodies are capped at 4.5 MB and there's no persistent disk. Use django-storages, Vercel Blob, or S3 for `MEDIA`.
- **Connections on Fluid compute.** With the default `CONN_MAX_AGE=0`, each request opens a new connection. If you raise it while using Neon's pooled (PgBouncer) URL, also set `DISABLE_SERVER_SIDE_CURSORS = True`.
- **Local tooling.** `vercel dev` needs CLI ≥ 50.38.0. `vercel dev --local` works without linking a project. `vercel build` requires project settings (`vercel pull`).
- **Naming.** Don't name the project package `django`, because it would shadow the library.

## Approach chosen for this demo

- **Zero config:** no `vercel.json`, no WhiteNoise, no `/api`. The demo relies on `manage.py` detection, `WSGI_APPLICATION`, and `STATIC_ROOT`, which are the three things Vercel reads.
- **A single package `mysite`** acts as both project and app (as in the `vc init django` example). That gives the fewest files while still using `APP_DIRS` templates and app `static/`.
- **Admin is included** because unstyled admin pages are the classic Django-on-serverless failure. Here its CSS/JS (from site-packages) is collected and CDN-served with zero config. Sessions and auth use the stock DB-backed defaults. No public page and not even `/admin/login/` touches the database, so it **deploys without provisioning anything**.
- **Postgres is optional** through `dj_database_url.config(default=sqlite)`, plus the django-notes-style guarded `migrate` build hook. This makes the database story real (admin login) without making it a deployment requirement. `psycopg[binary]` is a regular dependency because Vercel installs only default dependencies.
- **Secure defaults, matching the official templates:** `DEBUG` is off unless `DJANGO_DEBUG=1`, the secret comes from `DJANGO_SECRET_KEY`, and `ALLOWED_HOSTS` is `.vercel.app` plus the hostnames from `VERCEL_URL`, `VERCEL_BRANCH_URL` and `VERCEL_PROJECT_PRODUCTION_URL`.
- **Python 3.12** (`.python-version`) matches Vercel's default. Django is locked at 6.1.1 because the local uv config enforces `exclude-newer = "2 days"` and 6.1.2 is only 2 days old. Re-lock later to pick it up.
