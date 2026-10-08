import os
import platform

import django
from django.conf import settings
from django.http import JsonResponse
from django.http.request import split_domain_port, validate_host
from django.shortcuts import render

# The system env vars that settings.py appends to ALLOWED_HOSTS.
VERCEL_HOST_VARS = ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL")


def runtime_info():
    return {
        "python": platform.python_version(),
        "django": django.get_version(),
        # System env vars Vercel sets on deployments; absent when running locally.
        "vercel_env": os.environ.get("VERCEL_ENV", "local"),
        "vercel_region": os.environ.get("VERCEL_REGION"),
        "database": settings.DATABASES["default"]["ENGINE"].rsplit(".", 1)[-1],
    }


def allowed_hosts_check(request):
    """Each ALLOWED_HOSTS entry, where it came from, and whether it accepts this request's Host."""
    host = request.get_host()  # raises DisallowedHost (a 400) when no entry matches
    domain, _port = split_domain_port(host)
    from_var = {os.environ[var]: var for var in VERCEL_HOST_VARS if os.environ.get(var)}
    return {
        "host": host,
        "entries": [
            {"entry": entry, "source": from_var.get(entry, "settings.py"), "matches": validate_host(domain, [entry])}
            for entry in settings.ALLOWED_HOSTS
        ],
        "unset": [var for var in VERCEL_HOST_VARS if not os.environ.get(var)],
    }


def index(request):
    """The explainer page, rendered from a template. Its stylesheet is linked with {% static %}."""
    return render(request, "mysite/index.html", {"info": runtime_info(), "hosts": allowed_hosts_check(request)})


def api_info(request):
    """Plain JSON."""
    return JsonResponse(runtime_info())
