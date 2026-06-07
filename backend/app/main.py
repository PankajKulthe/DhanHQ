from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import verify_app_session_token
from app.database.session import Base, engine
from app import models  # noqa: F401


def _requires_app_access(path: str) -> bool:
    if path in {"/health", "/favicon.ico"}:
        return False
    if path.startswith("/api/v1/auth/app/"):
        return False
    if path.startswith("/api/v1/"):
        return True
    return path in {"/docs", "/redoc", "/openapi.json"}


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def app_access_guard(request, call_next):
        if settings.app_access_password and _requires_app_access(request.url.path):
            token = request.cookies.get(settings.app_session_cookie)
            if not verify_app_session_token(token):
                return JSONResponse(status_code=401, content={"detail": "App password required"})
        return await call_next(request)

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "environment": settings.environment}

    return app


app = create_app()
