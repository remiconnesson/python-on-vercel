"""A tiny FastAPI app that Vercel builds from Dockerfile.vercel and runs as a container."""

import os
import platform
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

app = FastAPI(title="Containers on Vercel")
INDEX_HTML = (Path(__file__).parent / "index.html").read_text()

# Set once per process. Each container instance runs a single uvicorn process,
# so these identify the instance; Fluid compute reuses it for many requests.
INSTANCE_ID = uuid.uuid4().hex[:8]
STARTED_AT = time.time()

# figlet is a system binary installed with apt-get in Dockerfile.vercel.
FIGLET = shutil.which("figlet")


def figlet_package() -> str | None:
    # The Debian package version shows figlet came from apt, not from pip.
    try:
        out = subprocess.run(
            ["dpkg-query", "-W", "-f=${Version}", "figlet"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


FIGLET_PACKAGE = figlet_package()


def image_os() -> str:
    # /etc/os-release comes from the base image in Dockerfile.vercel (Debian),
    # not from Vercel's managed Python runtime.
    try:
        return platform.freedesktop_os_release()["PRETTY_NAME"]
    except OSError:
        return "unknown (not running inside the container)"


@app.get("/")
def index(request: Request):
    # Browsers get the visual explainer (index.html); curl and scripts get JSON.
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(INDEX_HTML)
    return {
        "message": "Hello from a Docker container running on Vercel Functions",
        "how": (
            "Vercel detected Dockerfile.vercel, built the image, pushed it to "
            "Vercel Container Registry, and serves it on Fluid compute."
        ),
        "image_os": image_os(),
        "python": platform.python_version(),
        "arch": platform.machine(),
        # Vercel sends traffic to port 80 unless PORT is set in project settings.
        "port": os.environ.get("PORT", "80 (default)"),
        "vercel_env": os.environ.get("VERCEL_ENV"),
        # 1 inside the container: the CMD execs uvicorn, so it is the first process.
        "pid": os.getpid(),
        "instance_id": INSTANCE_ID,
        "instance_started_at": datetime.fromtimestamp(STARTED_AT, timezone.utc).isoformat(timespec="seconds"),
        "instance_uptime_s": round(time.time() - STARTED_AT, 1),
        "figlet": FIGLET,
        "figlet_package": FIGLET_PACKAGE,
        "endpoints": {
            "/": "this JSON (browsers get the explainer page)",
            "/figlet?text=hi": "ASCII art from figlet, an apt package baked into the image",
            "/docs": "FastAPI's interactive docs",
        },
    }


@app.get("/figlet", response_class=PlainTextResponse)
def figlet(text: str = "Vercel"):
    # figlet is a system binary installed with apt-get in Dockerfile.vercel:
    # the kind of dependency a pip install can't give you.
    if FIGLET is None:
        return PlainTextResponse(
            "figlet is not installed here. It is part of the container image: "
            "deploy this folder or run Dockerfile.vercel with Docker.\n",
            status_code=503,
        )
    # "--" ends figlet's options, so text that starts with "-" is printed, not parsed.
    result = subprocess.run([FIGLET, "--", text[:40]], capture_output=True, text=True, check=True)
    return result.stdout
