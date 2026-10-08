"""FastAPI on Vercel with zero configuration.

Vercel finds the `app` object in main.py (other recognized names: app.py,
index.py, server.py, asgi.py, wsgi.py, optionally under src/, app/ or api/)
and deploys the whole app as one Vercel Function running on Fluid compute.
"""

import asyncio
import os
import platform
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup runs once per function instance (on a cold start). Fluid compute
    # reuses an instance for many requests, so this state is shared by them.
    app.state.started_at = time.time()
    yield
    # Shutdown: Vercel allows ~500 ms after SIGTERM for cleanup here.


app = FastAPI(title="FastAPI on Vercel", lifespan=lifespan)


@app.get("/")
def index():
    return {
        "message": "FastAPI running on Vercel",
        "python": platform.python_version(),
        "region": os.environ.get("VERCEL_REGION", "local"),
        "instance_uptime_s": round(time.time() - app.state.started_at, 1),
        "endpoints": {
            "GET /items/{item_id}?q=&limit=": "path + query parameters",
            "POST /items": "JSON body validated by Pydantic",
            "GET /stream?n=5": "StreamingResponse, one line every 0.5s",
            "GET /docs": "interactive OpenAPI docs (Swagger UI)",
        },
    }


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None, limit: int = 10):
    # item_id comes from the path, q and limit from the query string.
    # FastAPI converts and validates them from the type hints (try item_id=abc).
    return {"item_id": item_id, "q": q, "limit": limit}


class Item(BaseModel):
    name: str = Field(min_length=1)
    price: float = Field(gt=0)
    tags: list[str] = []


@app.post("/items", status_code=201)
def create_item(item: Item):
    # The JSON body is parsed into `Item`; invalid input gets an automatic 422.
    return {"created": item, "price_with_tax": round(item.price * 1.2, 2)}


@app.get("/stream")
async def stream(n: Annotated[int, Query(ge=1, le=20)] = 5):
    # Python functions on Vercel stream by default: each chunk is sent as soon
    # as it is yielded instead of buffering the whole response.
    async def lines():
        start = time.perf_counter()
        for i in range(1, n + 1):
            yield f"chunk {i}/{n} at t+{time.perf_counter() - start:.1f}s\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(lines(), media_type="text/plain")
