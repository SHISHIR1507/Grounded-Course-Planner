"""
Main FastAPI application entrypoint.
Adopts eve-core patterns: create_app factory, startup event for validation,
/health endpoint, structured logging.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.routes.ask import router as ask_router
from app.routes.plan import router as plan_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.api_title,
        description=settings.api_description,
        version=settings.api_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Startup validation (eve-core pattern) ───────────────────────────────
    @app.on_event("startup")
    async def _startup() -> None:
        vs_path = Path(settings.vectorstore_path)
        if not vs_path.exists():
            print(
                f"WARNING: Vectorstore not found at '{vs_path.resolve()}'. "
                "Run 'python -m app.ingestion.ingest' before querying."
            )
        else:
            print(f"Vectorstore found at '{vs_path.resolve()}'")
        print(f"Starting {settings.api_title} v{settings.api_version} in {settings.env} mode")

    # ── Routes ──────────────────────────────────────────────────────────────
    app.include_router(ask_router)
    app.include_router(plan_router)

    # ── Health endpoint (eve-core pattern) ──────────────────────────────────
    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # ── Global exception handler ────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        return JSONResponse(
            status_code=500,
            content={"error": "Internal Server Error", "detail": str(exc)},
        )

    # ── Serve Frontend UI ───────────────────────────────────────────────────
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
