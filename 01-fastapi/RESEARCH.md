# Research: FastAPI on Vercel (as of 2026-10-08)

## What's available

**Official docs**
- [Deploy a FastAPI app on Vercel](https://vercel.com/docs/frameworks/backend/fastapi): the main reference. Covers entrypoint names, `tool.vercel.entrypoint`, `[tool.vercel.scripts] build`, `public/`, CDN promotion of `app.mount()`/`app.frontend()`, lifespan (500 ms shutdown budget), `maxDuration` keyed on the entrypoint file, and the 500 MB / 5 GB bundle limits. Updated 2026-08-27.
- [Python runtime](https://vercel.com/docs/functions/runtimes/python): ASGI/WSGI support, entrypoint rules (`app` or `application`), dependency files (`pyproject.toml` ± `uv.lock`, `requirements.txt`, `Pipfile`), streaming, bytecode precompilation, `excludeFiles`, and the note that relative paths resolve from the project root.
- [Set the Python version](https://vercel.com/docs/functions/runtimes/python/python-version): 3.12 (default), 3.13, 3.14. Set it with `requires-python`, `.python-version` or `Pipfile.lock`.
- [Fluid compute](https://vercel.com/docs/fluid-compute): on by default for projects created since 2025-04-23. Python supports optimized (in-function) concurrency.
- [Max duration](https://vercel.com/docs/functions/configuring-functions/duration) and [Functions limits](https://vercel.com/docs/functions/limitations): 300 s default; max 300 s on Hobby and 800 s on Pro/Enterprise, with a 1800 s beta. Request and response bodies are capped at 4.5 MB. Memory is 2 GB / 1 vCPU by default.
- [System env vars](https://vercel.com/docs/environment-variables/system-environment-variables): `VERCEL_REGION` and similar are available at runtime. The [Vercel Python SDK](https://vercel.com/docs/functions/functions-api-reference/vercel-sdk-python) (`vercel` on PyPI, 0.11.6) exposes them through `get_env()`.

**KB guides**
- [How to ship a FastAPI app on Vercel](https://vercel.com/kb/guide/ship-a-fastapi-app-on-vercel): end-to-end walkthrough covering streaming, FastAPI middleware vs Vercel Routing Middleware, lifespan, `public/`, and Python version.
- [Build with a FastAPI starter template](https://vercel.com/kb/guide/build-with-a-fastapi-starter-template): compares four templates (minimal, AI chatbot, OpenAI Agents + Sandbox, full-stack with Next.js).
- [Do Vercel Functions support WebSockets?](https://vercel.com/kb/guide/do-vercel-serverless-functions-support-websocket-connections): yes, as a public beta. Python support landed on 2026-07-23, and FastAPI `@app.websocket()` works without config.

**Changelog (newest first)**
- 2026-09-10 [FastAPI frontends and static files served from the CDN](https://vercel.com/changelog/fastapi-frontends-and-static-files-served-from-the-cdn): `StaticFiles` mounts and `app.frontend()` are promoted to the CDN at build time. `[tool.vercel.fastapi.static]` takes `cdn` and `exclude`.
- 2026-02-02 [Python 3.13 and 3.14 are now available](https://vercel.com/changelog/python-3-13-and-3-14-are-now-available): says the default "will switch to Python 3.14 in the coming months". The docs still list 3.12 as the default.
- 2025-12-09 [FastAPI lifespan events supported](https://vercel.com/changelog/fastapi-lifespan-events-are-now-supported-on-vercel).
- 2025-10-03 [uv is the default for Python builds](https://vercel.com/changelog/python-package-manager-uv-is-now-available-for-builds-with-zero): reads `uv.lock` and `pyproject.toml` with zero config.
- 2025-09-25 [Zero-configuration FastAPI backends](https://vercel.com/changelog/zero-config-fastapi-backends): no `vercel.json` or `/api` folder needed.
- 2025-01-14 [Python in-function concurrency](https://vercel.com/changelog/python-support-added-to-in-function-concurrency-beta) and 2025-01-06 [Python streaming on by default](https://vercel.com/changelog/python-vercel-functions-now-have-streaming-enabled-by-default) (`VERCEL_FORCE_PYTHON_STREAMING` is no longer needed).

**Templates and examples**
- [FastAPI Boilerplate template](https://vercel.com/templates/python/fastapi-python-boilerplate) uses [vercel/examples `python/fastapi`](https://github.com/vercel/examples/tree/main/python/fastapi) as its source: a single `main.py`, `.python-version` = 3.14, `fastapi>=0.135.3`, and `public/favicon.ico`.
- [vercel/vercel `examples/fastapi`](https://github.com/vercel/vercel/tree/main/examples/fastapi) is what `vc init fastapi` clones: the "bigger applications" layout (`app/main.py`, routers, settings), pinned to `==3.12.*`.
- Other FastAPI templates: [OpenAI Agents SDK + Sandbox + FastAPI](https://vercel.com/templates/other/openai-agents-sdk-with-vercel-sandbox-fastapi) and [Full-stack FastAPI + Next.js](https://vercel.com/templates/other/full-stack-fastapi-template-with-next-js).
- vercel-labs repos, found with `gh search`: [nextjs-fastapi-multiplayer-cursors](https://github.com/vercel-labs/nextjs-fastapi-multiplayer-cursors), [ocr-fastapi-nextjs-docker](https://github.com/vercel-labs/ocr-fastapi-nextjs-docker), [full-stack-service-previews](https://github.com/vercel-labs/full-stack-service-previews), [openai-agents-fastapi-starter](https://github.com/vercel-labs/openai-agents-fastapi-starter). They combine FastAPI with Next.js through Vercel Services.
- A community walkthrough turned up in search results: [zenn.dev article on Vercel + FastAPI](https://zenn.dev/testkun08080/articles/vercel-fastapi-591926e41c4a69) (Japanese).

**Builder source (ground truth for edge cases)**
- [`packages/python/src/entrypoint.ts`](https://github.com/vercel/vercel/blob/main/packages/python/src/entrypoint.ts): candidate filenames, and candidate dirs `''`, `src`, `app`, `api`.
- [`packages/python/src/version.ts`](https://github.com/vercel/vercel/blob/main/packages/python/src/version.ts) and [`python-analysis/.../package.ts`](https://github.com/vercel/vercel/blob/main/packages/python-analysis/src/manifest/package.ts): how the Python version is resolved.
- [`packages/python/src/uv.ts`](https://github.com/vercel/vercel/blob/main/packages/python/src/uv.ts): the install runs `uv sync --active --no-dev ... --no-editable`.
- [`packages/frameworks/src/frameworks.ts`](https://github.com/vercel/vercel/blob/main/packages/frameworks/src/frameworks.ts): the FastAPI preset (detectors, routes).
- [`python/vercel-runtime/.../vc_init.py`](https://github.com/vercel/vercel/blob/main/python/vercel-runtime/src/vercel_runtime/vc_init.py): the runtime shim. It vendors uvicorn and runs the ASGI lifespan once at instance start.

**PyPI versions on 2026-10-08:** [fastapi](https://pypi.org/project/fastapi/) 0.143.0 (released today; this demo locks 0.142.2, see Gotchas), [uvicorn](https://pypi.org/project/uvicorn/) 0.54.0, [pydantic](https://pypi.org/project/pydantic/) 2.13.5, [starlette](https://pypi.org/project/starlette/) 1.7.0.

## How it works on Vercel

1. **Detection.** The FastAPI preset matches when the string `fastapi` appears in `requirements.txt`, `pyproject.toml` or `Pipfile`. It is a plain substring match.
2. **Entrypoint.** The builder looks for a top-level `app` (or `application`) in `{app,index,server,main,wsgi,asgi}.py`, at the root or under `src/`, `app/` or `api/`. The docs list only `src/` and `app/`, but the builder source also checks `api/`. You can override the lookup with `[tool.vercel] entrypoint = "pkg.module:app"`. The legacy `[project.scripts] app = "..."` still works.
3. **Install.** uv runs `uv sync --no-dev` from `pyproject.toml` and `uv.lock`. Dev dependency groups are skipped. Source files are precompiled to `.pyc` when the bundle has room.
4. **Python version.** `.python-version` wins over `requires-python`. A range like `>=3.12` resolves to 3.12, because the builder lists the default version first. Anything unset or unsupported falls back to 3.12.
5. **Runtime.** The whole app becomes one Vercel Function on Fluid compute. Routes are `filesystem` (`public/`) first, then `/(.*)` goes to the function. Vercel's runtime brings its own ASGI server, so uvicorn isn't needed in production. Lifespan startup runs once per instance, and shutdown gets about 500 ms after SIGTERM.
6. **Streaming.** On by default. `StreamingResponse` chunks are flushed as they are yielded, and the stream counts toward `maxDuration` (300 s default).
7. **Static files.** Anything in `public/` is served from the CDN at `/`, without invoking the function. `StaticFiles` mounts and `app.frontend()` are promoted to the CDN at build time, unless middleware or `Depends()` guards cover them.
8. **Function config.** Use `vercel.json` with a `functions` entry keyed on the entrypoint file, e.g. `"main.py": {"maxDuration": 60}`. Without one, defaults apply.

## Gotchas

- The variable name matters. It must be a module-level `app` (or `application`). For anything else, set `tool.vercel.entrypoint`.
- Pin the Python version explicitly. The default is expected to move from 3.12 to 3.14, and `>=3.12` alone gives 3.12, not the newest version.
- Keep `uv.lock` in sync with `pyproject.toml`. The builder can run `uv sync` with `--locked`/`--frozen`, so a stale lock can fail the build.
- Don't put uvicorn or `fastapi[standard]` in runtime deps unless you need them. They only grow the bundle (500 MB limit, no tree-shaking).
- Don't `app.mount()` the `public/` dir. Also, CDN-served files bypass FastAPI middleware and `Depends()`.
- Plain `uvicorn` doesn't serve `public/` locally. `vercel dev --local` does, and needs no project link.
- Fluid compute runs concurrent requests in one process. Treat module globals as shared state, never per-request state.
- Request and response bodies are capped at 4.5 MB. For long streams over HTTP/1.1, send heartbeats, because idle connections may be closed.
- Logs printed during lifespan shutdown don't appear in the dashboard.
- Relative `open()` paths resolve from the project root (the Root Directory), not from the file's directory.
- On this machine, uv has `exclude-newer = "2 days"` set in `~/.config/uv/uv.toml`. fastapi 0.143.0 (released 2026-10-08) was therefore not installable, and the lock uses 0.142.2.

## Approach chosen for this demo

- **One file, `main.py`, at the project root.** It's the most common FastAPI convention and is auto-detected, so there's no `vercel.json`, no `api/` folder and no `tool.vercel.entrypoint`. It matches the official Boilerplate template.
- **Endpoints:** `GET /` (JSON listing the endpoints plus Python version, `VERCEL_REGION` and instance uptime), `GET /items/{id}?q=&limit=`, `POST /items` with a Pydantic model, and `GET /stream` (`StreamingResponse`, a line every 0.5 s). `/docs` comes free.
- **A tiny lifespan hook** records instance start time. It demonstrates lifespan support, and shows Fluid compute reusing instances through `instance_uptime_s`.
- **`.python-version` = 3.14** together with `requires-python = ">=3.12"`. This shows explicit version selection on Vercel, overriding the 3.12 default, and keeps local and deployed Python the same.
- **uvicorn sits in the `dev` dependency group**, so it's available for local runs. Vercel skips it, which keeps the function to fastapi's dependencies.
- **Left out on purpose:** `public/` assets, `app.frontend()`, and `vercel.json` function config. They're documented above and fit better in follow-up demos.
