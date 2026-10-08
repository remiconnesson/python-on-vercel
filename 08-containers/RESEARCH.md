# Research: Containers on Vercel (as of 2026-10-08)

Short version: since **2026-06-30**, Vercel deploys any HTTP server from a `Dockerfile.vercel` as a Vercel Function (OCI image on Fluid compute). The images live in the new **Vercel Container Registry (VCR)**. The same registry also feeds **custom images for Vercel Sandbox**. The docs label Container Images and Services as **Beta, all plans**.

## What's available

**Container Images for Vercel Functions (the main product)**
- [Changelog: Bring your Dockerfile to Vercel Functions](https://vercel.com/changelog/bring-your-dockerfile-to-vercel-functions): announcement (2026-06-30). Add a `Dockerfile.vercel` (or `Containerfile.vercel`) that starts an HTTP server on `$PORT`. Vercel builds the image on every commit, pushes it to VCR and runs it on Fluid compute.
- [Docs: Container Images](https://vercel.com/docs/functions/container-images): the reference page. Shows the "Beta, available on all plans" banner, root-level `Dockerfile.vercel` detection with an automatic catch-all rewrite, port 80 by default (override via the `PORT` project env var), scale-in after 5 min (prod) or 30 s (preview), SIGTERM with a 30 s grace period, and no Secure Compute or Static IPs yet.
- [Blog: Run any Dockerfile on Vercel](https://vercel.com/blog/dockerfile-on-vercel): explains how it works. Images are stored as optimized, compressed boot images with streaming decompression for fast cold starts. Lists FastAPI among supported stacks.
- [KB: Running Docker on Vercel](https://vercel.com/kb/guide/docker): overview of the whole Docker workflow (Functions, VCR, Sandbox, `vercel dev`).
- [KB: Does Vercel support Docker deployments?](https://vercel.com/kb/guide/does-vercel-support-docker-deployments): FAQ. Stateless, scale to zero, Active CPU pricing, standard function limits.
- [KB: Deploy Python apps on Vercel using Docker](https://vercel.com/kb/guide/vercel-docker-python-apps): the official **Python** guide (FastAPI + Tesseract OCR in `Dockerfile.vercel`, run as a Service next to Next.js). Says "Large Functions… supports… container images up to 5 GB".
- [KB: Deploy a Node.js Fastify app with Docker](https://vercel.com/kb/guide/deploy-nodejs-on-vercel-with-docker) and [KB: Deploy Go apps using Docker](https://vercel.com/kb/guide/deploy-go-using-docker-vercel): bind to `0.0.0.0`, read `PORT` (falling back to 80), non-root users can't bind port 80, set `PORT` for prebuilt images that listen elsewhere.
- [KB: Docker on Vercel vs Render](https://vercel.com/kb/guide/docker-on-vercel-vs-render): HTTP only (no background workers), no volumes, and images can't be pulled straight from Docker Hub, GHCR or ECR. You build from a Dockerfile or push to VCR.
- [Vercel: 7 ways to use Docker containers on Vercel](https://vercel.com/i/7-ways-to-use-docker-containers-on-vercel): the map of options. Dockerfile deploys, polyglot backends, Services, VCR push/pull, custom Sandbox images, Docker inside Sandbox, `vercel dev` parity.
- [Template: Container Images Demo](https://vercel.com/templates/container-images/container-images-demo) / [source (vercel/examples)](https://github.com/vercel/examples/tree/main/container-images/demo): nine Dockerfile services (Rust, Go, nginx/WASM, Chromium, ffmpeg, Doom, Laravel) behind one `vercel.json` `services` config. There's no Python example.

**Services (multi-container / polyglot in one project)**
- [Docs: Services](https://vercel.com/docs/services): **Beta, all plans**. `vercel.json` `services` with `root`, `entrypoint` (a Dockerfile path) or `"runtime": "container"`, plus top-level `rewrites` to `{ "service": ... }`. You don't need it for a single root `Dockerfile.vercel`.

**Vercel Container Registry (VCR)**
- [Changelog: Introducing VCR](https://vercel.com/changelog/introducing-vcr-vercel-container-registry): OCI registry at `vcr.vercel.com/<team>/<project>/<repo>:<tag>`. Works with `docker push/pull`. Backs both Functions and Sandbox.
- [Docs: VCR limits and pricing](https://vercel.com/docs/container-registry/limits-and-pricing): $0.10/GB storage, 2 GB per compressed layer, 15 GB per image, gzip or zstd layers only. Plan limits on repositories, images and tags.
- [Docs: `vercel vcr` CLI](https://vercel.com/docs/cli/vcr): `vercel vcr login docker`, `vercel vcr build docker . repo:tag --push`, image ls/inspect/rm.

**Vercel Sandbox with custom images (the alternative)**
- [Docs: Sandbox images](https://vercel.com/docs/sandbox/concepts/images): Firecracker microVMs boot from Vercel Managed Images (`vercel/sandbox/python:3.14`, `universal`, …) or your own VCR image. The image must be `linux/amd64`, and Sandbox does **not** run `ENTRYPOINT`/`CMD`, so you start processes with run-command calls.
- [Changelog: Vercel Sandbox now supports Custom Images](https://vercel.com/changelog/vercel-sandbox-now-support-custom-images): custom images launched in public beta on 2026-06-30.
- [PyPI: `vercel`](https://pypi.org/project/vercel/): the official Python SDK (latest 0.11.6). I checked the installed 0.11.4 source: `vercel.sandbox.create_sandbox(image=..., ...)` is an async context manager that stops and destroys the sandbox on exit. Credentials come from `VERCEL_OIDC_TOKEN` (project and team read from the token), or else from `VERCEL_TOKEN` + `VERCEL_PROJECT_ID` + `VERCEL_TEAM_ID` (`vercel/oidc/credentials.py`).

**Source code (ground truth for detection and build)**
- [vercel/vercel `packages/frameworks/src/frameworks.ts`](https://github.com/vercel/vercel/blob/main/packages/frameworks/src/frameworks.ts): the **`Container`** framework preset (slug `container`) is first in the list, detected by `Dockerfile.vercel` / `Containerfile.vercel`, and uses the `@vercel/container` builder. Being first means it beats Next.js, FastAPI and the rest whenever both are present.
- [vercel/vercel `packages/container`](https://github.com/vercel/vercel/tree/main/packages/container): the builder (v7.0.1). It builds `TARGET_PLATFORM = 'linux/amd64'` with buildah on Vercel (docker locally). The build context is the directory that holds the Dockerfile. The project's build env is passed as `--build-arg`s (only for declared `ARG`s). It pushes to VCR as `<owner>/<project>/dockerfile:<git-sha-12>` and emits a catch-all route to the container function.

**Third-party write-ups (secondary)**
- [flaviocopes: Run a Dockerfile on Vercel](https://flaviocopes.com/run-dockerfile-on-vercel/): hands-on walkthrough. No preset tweaks needed, `npx vercel` deploys it, `PORT` defaults to 80.
- [buildwithmatija: Vercel Dockerfile support](https://www.buildwithmatija.com/blog/vercel-dockerfile-backend-hosting): practical limits discussion (300 s default duration, 500 MB `/tmp`, stateless).
- [Cloud Native Now: Vercel now lets you deploy any Dockerfile](https://cloudnativenow.com/features/vercel-now-lets-you-deploy-any-dockerfile-straight-to-production/): news coverage.

## How it works on Vercel

1. **Detection.** A `Dockerfile.vercel` at the project root selects the `Container` framework preset, which sets install, build and output to "None". You can force it with `"framework": "container"` in `vercel.json` (a valid value in the vercel.json schema).
2. **Build.** `@vercel/container` builds the image for `linux/amd64` with the Root Directory as the build context, authenticates to VCR with the build's OIDC token, and pushes it.
3. **Run.** The deployment contains one function (`runtime: "container"`), and every path is rewritten to it. The original request path reaches your server. Vercel proxies HTTP to the container on **port 80**, or on the port in the `PORT` project env var. Your server must bind `0.0.0.0`.
4. **Scale.** Fluid compute autoscaling. Instances scale in after 5 min idle (prod) or 30 s (preview), with SIGTERM and a 30 s grace period. Fully stateless: no volumes.
5. **Limits and pricing.** Same as Vercel Functions: memory up to 2 GB on Hobby and 4 GB on Pro/Enterprise; duration 300 s default, 800 s max on Pro/Enterprise; 4.5 MB request/response bodies; Active CPU plus provisioned-memory billing. The standard function size limit is 250 MB uncompressed, and Large Functions (beta, on by default for new projects, `VERCEL_SUPPORT_LARGE_FUNCTIONS=1` for existing ones) goes up to 5 GB. VCR storage costs $0.10/GB.
6. **Local dev.** `vercel dev` builds and runs the image with your local Docker daemon. Plain `docker build` and `docker run` also work.

## Gotchas

- **Port 80 is the default, not 3000 or 8000.** Use `--port ${PORT:-80}`. The Python KB guide bakes `ENV PORT=8000` into its image, but the docs say Vercel's router reads `PORT` from **project settings**. Falling back to 80 works either way.
- **Bind `0.0.0.0`**, not `127.0.0.1` (the usual cause of 502s in the KB guides).
- **Non-root users can't bind port 80.** If the image switches `USER`, set `PORT` (for example 8080) in the project env vars.
- **Use `exec` in a shell-form CMD** so the server is PID 1 and receives SIGTERM on scale-in.
- **The image is built for amd64.** On Apple Silicon, `docker build` locally gives you arm64. Use `--platform linux/amd64` to reproduce Vercel's build exactly.
- **No Secure Compute or Static IPs** for container images yet.
- **HTTP only.** No background workers, and cron must hit an HTTP route. No persistent disk.
- **The framework preset matters.** If a project ends up with preset "Other", the Dockerfile is ignored (`detect-builders.ts` only uses `@vercel/container` via the preset).
- **uv.lock with `exclude-newer`.** If the machine that ran `uv lock` has a global `exclude-newer` in its uv config, uv writes it into `uv.lock` `[options]`. A clean `uv sync --locked` (inside Docker, CI, …) then refuses with "lockfile needs to be updated". This demo uses `uv sync --frozen`, which installs exactly the lockfile's pins.

## Approach chosen for this demo

**A Dockerfile container deploy (Container Images for Vercel Functions), not Sandbox.** It's the most direct, officially supported way to run a container with Python on Vercel. It's a single file Vercel detects on its own, and it's available on all plans (Beta).

- One root `Dockerfile.vercel` (no Services) keeps it minimal. Services only matter when several apps share one project.
- FastAPI + uvicorn managed by uv (`pyproject.toml` + `uv.lock`, installed with `uv sync --frozen`), on `python:3.14-slim`.
- One `apt-get install figlet` plus a `/figlet` endpoint shows *why* you'd pick a container over the zero-config Python runtime: system binaries.
- `vercel.json` only pins `"framework": "container"`, so pyproject.toml/main.py can never make a project built through the API or CLI fall back to the native Python builder.
- **Sandbox is the alternative** for running *untrusted or arbitrary* code or images on demand (agents, code execution). It uses the same VCR images, through `vercel.sandbox.create_sandbox(image=...)` in the `vercel` Python package. It isn't a way to *host* a web server from a Dockerfile, so I left it out of this demo.
