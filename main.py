from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.limiter import limiter
from app.routers.auth import router as auth_router
from app.routers.opportunities import router as opportunities_router
from app.routers.pipeline import router as pipeline_router
from app.routers.projects import router as projects_router
from app.routers.prd import router as prd_router
from app.routers.signals import router as signals_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


app = FastAPI(title="SpecForge API", version="0.1.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(signals_router)
app.include_router(pipeline_router)
app.include_router(opportunities_router)
app.include_router(prd_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "env": get_settings().APP_ENV}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
