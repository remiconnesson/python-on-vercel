"""A tiny FastAPI app that Vercel builds from Dockerfile.vercel and runs as a container."""

import os
import platform
import subprocess

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI(title="Containers on Vercel")


def image_os() -> str:
    # /etc/os-release comes from the base image in Dockerfile.vercel (Debian),
    # not from Vercel's managed Python runtime.
    try:
        return platform.freedesktop_os_release()["PRETTY_NAME"]
    except OSError:
        return "unknown (not running inside the container)"


@app.get("/")
def index():
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
        "endpoints": {
            "/": "this JSON",
            "/figlet?text=hi": "ASCII art from figlet, an apt package baked into the image",
            "/docs": "FastAPI's interactive docs",
        },
    }


@app.get("/figlet", response_class=PlainTextResponse)
def figlet(text: str = "Vercel"):
    # figlet is a system binary installed with apt-get in Dockerfile.vercel:
    # the kind of dependency a pip install can't give you.
    result = subprocess.run(["figlet", text[:40]], capture_output=True, text=True, check=True)
    return result.stdout
