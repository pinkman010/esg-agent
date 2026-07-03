from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import audit, exports, reports, review, runs
from src.config.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="esg-agent")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(reports.router)
    app.include_router(runs.router)
    app.include_router(review.router)
    app.include_router(exports.router)
    app.include_router(audit.router)

    return app


app = create_app()