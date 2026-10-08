# 01 · FastAPI on Vercel

A single-file FastAPI app that deploys to Vercel with zero configuration: no `vercel.json`, no `api/` folder. Vercel detects FastAPI from `pyproject.toml`, finds `app` in `main.py`, and runs the whole app as one Vercel Function on Fluid compute. The endpoints cover path and query params, a Pydantic-validated JSON body, a lifespan hook, and a `StreamingResponse` to show that streaming works.

## Files

```
01-fastapi/
├── main.py          # the FastAPI app (Vercel auto-detects `app` here)
├── pyproject.toml   # deps: fastapi (runtime), uvicorn (dev group, local only)
├── uv.lock          # locked deps; Vercel installs from it with uv
└── .python-version  # selects Python 3.14 on Vercel (default would be 3.12)
```

## Run locally

```bash
uv sync
uv run uvicorn main:app --reload        # http://localhost:8000
# or, to run it the way Vercel does (no project link needed):
vercel dev --local                      # http://localhost:3000
```

## Deploy

- **Vercel project settings:** Framework Preset `FastAPI` (detected automatically), Root Directory `01-fastapi`. Leave the Build, Install and Output settings at their defaults.
- **Env vars:** none.
- **External resources:** none.
- **Python version:** `.python-version` (3.14) takes priority over `requires-python`. If you delete it, `>=3.12` resolves to Vercel's default, 3.12.
- **No `vercel.json`:** you'd only add one to change function settings such as `maxDuration`, keyed on the entrypoint: `{"functions": {"main.py": {"maxDuration": 60}}}`.

## Try it

Set `URL` to `http://localhost:8000` or to your deployment URL.

```bash
# Index: lists endpoints, Python version, region, instance uptime
curl $URL/

# Path + query params (try /items/abc to see the automatic 422)
curl "$URL/items/42?q=shoes&limit=3"

# Pydantic body validation (201 on success, 422 on invalid input)
curl -X POST $URL/items -H 'content-type: application/json' \
  -d '{"name": "Widget", "price": 9.99, "tags": ["demo"]}'
curl -X POST $URL/items -H 'content-type: application/json' \
  -d '{"name": "", "price": -1}'

# Streaming: -N turns off curl's buffering, so lines arrive every 0.5s
curl -N "$URL/stream?n=5"

# Interactive docs
open $URL/docs
```

Call `GET /` a few times on a deployment and watch `instance_uptime_s` climb. That shows Fluid compute reusing one warm instance, and the lifespan startup running once per instance rather than once per request.
