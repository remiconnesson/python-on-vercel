"""Trimmed `django-admin startproject` settings. Anything not listed uses Django's default."""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Set DJANGO_SECRET_KEY in the Vercel project. The fallback is only for local dev.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-local-dev-only")
DEBUG = os.environ.get("DJANGO_DEBUG") == "1"

# Vercel system env vars hold this deployment's hostnames: its unique URL, its
# branch alias, and the project's production domain (which may be a custom domain).
ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".vercel.app"]
for var in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
    if host := os.environ.get(var):
        ALLOWED_HOSTS.append(host)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "mysite",  # the project package doubles as the app, so its templates/ and static/ are found
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "mysite.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Vercel reads this to find the function entrypoint (ASGI_APPLICATION wins if both are set).
WSGI_APPLICATION = "mysite.wsgi.application"

# The database is optional: no public page queries it, only the admin login does.
# Locally this falls back to SQLite. On Vercel the filesystem is read-only, so attach
# Postgres (e.g. Neon from the Marketplace) and Vercel sets DATABASE_URL for you.
DATABASES = {
    "default": dj_database_url.config(default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

# When STATIC_ROOT is set, Vercel runs `collectstatic` during the build and serves
# the files from its CDN at STATIC_URL. That includes the admin's CSS/JS, which
# Django ships inside the installed package. No WhiteNoise needed.
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
