import os
import platform

import django
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render


def runtime_info():
    return {
        "python": platform.python_version(),
        "django": django.get_version(),
        # System env vars Vercel sets on deployments; absent when running locally.
        "vercel_env": os.environ.get("VERCEL_ENV", "local"),
        "vercel_region": os.environ.get("VERCEL_REGION"),
        "database": settings.DATABASES["default"]["ENGINE"].rsplit(".", 1)[-1],
    }


def index(request):
    """HTML rendered from a template. Its stylesheet is linked with {% static %}."""
    return render(request, "mysite/index.html", {"info": runtime_info()})


def api_info(request):
    """Plain JSON."""
    return JsonResponse(runtime_info())
