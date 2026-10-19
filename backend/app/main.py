import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.auth import router as auth_router
from app.api.conference_routes import router as conference_router
from app.api.template_routes import router as template_router
from app.api.submission_routes import router as submission_router
from app.api.issue_routes import router as issue_router
from app.api.notification_routes import router as notification_router
from app.api.revision_routes import router as revision_router
from app.api.collaboration_routes import router as collaboration_router
from app.api.review_routes import router as review_router
from app.api.intake_routes import router as intake_router
from app.api.google_auth_routes import router as google_auth_router
from app.api.invitation_routes import router as invitation_router
from app.config import BACKEND_DIR, get_settings
from app.storage.database import MigrationRequired
from app.security.middleware import BodyLimitMiddleware

logging.basicConfig(level=logging.INFO)

FRONTEND_DIR = BACKEND_DIR / "static" / "frontend"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version, debug=settings.debug)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    @app.exception_handler(HTTPException)
    async def api_error(request: Request, exc: HTTPException):
        response = JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)
        if exc.status_code == 401 and not request.headers.get("authorization"):
            # Expired cookies must not strand the standalone anonymous checker.
            from app.auth import SESSION_COOKIE, CSRF_COOKIE
            for name in (SESSION_COOKIE, CSRF_COOKIE):
                response.delete_cookie(name, path="/", secure=settings.cookie_secure,
                                       httponly=name == SESSION_COOKIE, samesite="lax")
        return response

    @app.exception_handler(MigrationRequired)
    async def migration_required(request: Request, exc: MigrationRequired):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.middleware("http")
    async def private_response_headers(request: Request, call_next):
        # Bound declared request size before multipart parsing. Chunked file bodies
        # are also bounded by the streaming reader; the reverse proxy caps bodies.
        length = request.headers.get("content-length")
        if length is not None:
            try:
                oversized = int(length) < 0 or int(length) > settings.max_batch_bytes + 1048576
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length"})
            if oversized:
                return JSONResponse(status_code=413, content={"detail": "Request exceeds the configured byte limit"})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Google Identity's browser widget needs the document origin. Private API
        # responses retain no-referrer, while SPA pages send only the origin cross-site.
        response.headers["Referrer-Policy"] = "no-referrer" if request.url.path.startswith("/api/") else "strict-origin-when-cross-origin"
        if not request.url.path.startswith("/api/"):
            response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "private, no-store"
        return response

    app.add_middleware(BodyLimitMiddleware, limit=settings.max_batch_bytes + 1048576)

    app.include_router(router)  # Core API routes (health, compare, etc.)
    app.include_router(auth_router)
    app.include_router(google_auth_router)
    app.include_router(conference_router)
    app.include_router(template_router)
    app.include_router(submission_router)
    app.include_router(issue_router)
    app.include_router(notification_router)
    app.include_router(revision_router)
    app.include_router(collaboration_router)
    app.include_router(review_router)
    app.include_router(intake_router)
    app.include_router(invitation_router)

    if FRONTEND_DIR.is_dir():
        assets_dir = FRONTEND_DIR / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa_fallback(path: str):
            if path.startswith("api/"):
                raise HTTPException(status_code=404, detail="API route not found")
            candidate = (FRONTEND_DIR / path).resolve()
            if not candidate.is_relative_to(FRONTEND_DIR.resolve()):
                raise HTTPException(status_code=404, detail="File not found")
            if path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIR / "index.html")

    return app


app = create_app()
