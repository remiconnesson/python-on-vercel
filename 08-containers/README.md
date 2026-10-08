# 08 · Containers on Vercel (Python)

A FastAPI app that Vercel deploys **from a Dockerfile**. Vercel finds `Dockerfile.vercel`, builds the image (linux/amd64), pushes it to Vercel Container Registry (VCR), and runs it as a Vercel Function on Fluid compute, with the same scaling, logs and Active CPU pricing as any other function. The image installs a system package (`figlet`) with `apt-get`, which the native Python runtime can't give you. That's the main reason to use a container.

**Product:** [Container Images for Vercel Functions](https://vercel.com/docs/functions/container-images). The docs list it as **Beta, available on all plans** (announced 2026-06-30).

## Files

```
08-containers/
├── Dockerfile.vercel   # what Vercel builds: python:3.14-slim + uv + apt figlet, uvicorn on $PORT (default 80)
├── main.py             # FastAPI app: GET / (environment info) and GET /figlet (shells out to the apt binary)
├── pyproject.toml      # uv project: fastapi + uvicorn
├── uv.lock             # pinned dependency versions; the image installs exactly these (uv sync --frozen)
└── vercel.json         # pins the "Container" framework preset (see below)
```

## Run locally

With Docker (this is what Vercel runs):

```bash
docker build -f Dockerfile.vercel -t containers-on-vercel .
docker run --rm -p 8080:80 containers-on-vercel        # container listens on 80, like on Vercel
curl localhost:8080/
```

Without Docker (quick iteration; `/figlet` only works if `figlet` is on your PATH):

```bash
uv run uvicorn main:app --reload
```

`vercel dev` can also build and run the container locally (needs the Docker daemon).

## Deploy

- **Root Directory:** `08-containers`
- **Framework Preset:** `Container`. `vercel.json` sets it, so the dashboard value doesn't matter. Install, Build and Output settings: leave empty (the preset sets them to "None").
- **Env vars:** none needed. Optional: set `PORT` if you change the port the server listens on. Vercel sends traffic to port `80` unless `PORT` is set in project settings.
- **Access:** nothing to enable. Container Images and VCR are available on all plans. The image is about 200 MB uncompressed, under the 250 MB standard function limit, so it doesn't need Large Functions.

### Why `vercel.json`?

The image is built only when the project's framework preset is `container` (Vercel's `@vercel/container` builder). When you import this folder from Git in the dashboard, Vercel detects the preset on its own: `Dockerfile.vercel` is checked before every other framework, so `pyproject.toml` doesn't win. A project created through the API or CLI can end up with the preset set to "Other", though, and then Vercel would never build the Dockerfile. The one-line `"framework": "container"` rules that out.

## Try it

```bash
URL=https://<your-deployment>.vercel.app

curl $URL/                        # JSON: image OS (Debian), Python version, arch (x86_64 on Vercel), port
curl "$URL/figlet?text=Vercel"    # ASCII art rendered by the apt-installed figlet binary
curl -I $URL/docs                 # FastAPI's interactive docs
```
