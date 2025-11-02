"""Application factory for Orders service."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates

from .config import get_settings
from .events import get_event_publisher
from . import repository, schemas
from .routes import get_session, router as orders_router
from .telemetry import setup_telemetry

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def create_app() -> FastAPI:
    settings = get_settings()
    event_publisher = get_event_publisher(settings.event_broker_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # pragma: no cover - env specific
        await event_publisher.start()
        try:
            yield
        finally:
            await event_publisher.stop()

    app = FastAPI(title="eFab Orders Service", version="0.1.0", lifespan=lifespan)
    telemetry = setup_telemetry(settings.service_name)
    app.state.telemetry = telemetry
    app.state.event_publisher = event_publisher

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):  # pragma: no cover - simple header
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Embedder-Policy", "require-corp")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        return response

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name}

    @app.get("/health/ready")
    async def ready() -> dict[str, str]:
        # TODO: add DB + broker health checks
        return {"status": "ok"}

    app.include_router(orders_router)
    @app.get("/")
    async def root() -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name}

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request, session=Depends(get_session)):
        metrics = repository.get_dashboard_metrics(session)
        return templates.TemplateResponse(
            "dashboard_overview.html",
            {
                "request": request,
                "metrics": metrics,
                "nav": "overview",
            },
        )

    @app.get("/dashboard/orders", response_class=HTMLResponse)
    async def dashboard_orders(
        request: Request,
        session=Depends(get_session),
        state: str | None = None,
        limit: int = 25,
    ):
        orders = repository.list_orders_summary(session, state=state, limit=limit)
        metrics = repository.get_dashboard_metrics(session)
        return templates.TemplateResponse(
            "dashboard_orders.html",
            {
                "request": request,
                "orders": orders,
                "selected_state": state or "",
                "states": [s.value for s in schemas.OrderState],
                "metrics": metrics,
                "nav": "orders",
            },
        )

    @app.get("/dashboard/audit", response_class=HTMLResponse)
    async def dashboard_audit(
        request: Request,
        session=Depends(get_session),
        limit: int = 25,
    ):
        audit_events = repository.list_audit_events(session, limit=limit)
        metrics = repository.get_dashboard_metrics(session)
        return templates.TemplateResponse(
            "dashboard_audit.html",
            {
                "request": request,
                "events": audit_events,
                "metrics": metrics,
                "nav": "audit",
            },
        )

    @app.get("/dashboard/api/metrics")
    async def dashboard_metrics_api(session=Depends(get_session)):
        return repository.get_dashboard_metrics(session)

    @app.get("/dashboard/performance", response_class=HTMLResponse)
    async def dashboard_performance(request: Request, session=Depends(get_session)):
        metrics = repository.get_dashboard_metrics(session)
        return templates.TemplateResponse(
            "dashboard_performance.html",
            {
                "request": request,
                "metrics": metrics,
                "nav": "performance",
            },
        )

    @app.get("/dashboard/executive", response_class=HTMLResponse)
    async def dashboard_executive(request: Request, session=Depends(get_session)):
        metrics = repository.get_dashboard_metrics(session)
        return templates.TemplateResponse(
            "dashboard_executive.html",
            {
                "request": request,
                "metrics": metrics,
                "nav": "executive",
            },
        )

    @app.get("/robots.txt", response_class=PlainTextResponse)
    async def robots() -> str:
        return "User-agent: *\nDisallow:\n"

    @app.get("/sitemap.xml", response_class=Response)
    async def sitemap() -> Response:
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>',
            media_type="application/xml",
        )
    return app


app = create_app()
