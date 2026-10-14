import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.config import config
from app.database import db
from app.scheduler import scheduler
from app.api.analytics_routes import router as analytics_router
from app.api.chat_routes import router as chat_router
from app.api.chartbot_routes import router as chartbot_router
from app.api.lead_routes import router as lead_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("trackingbot.main")

BASE_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: test database connection and start scheduler
    logger.info("Initializing TrackingBot Analytics Platform...")
    status = db.check_connection()
    if status.get("status") == "connected":
        logger.info(f"Database connected: {status.get('database')} on {status.get('host')}")
    else:
        logger.error(f"Database connection error: {status.get('error')}")

    # Start background scheduler for daily refresh
    scheduler.start()
    yield
    # Shutdown
    logger.info("Shutting down TrackingBot...")

app = FastAPI(
    title=config.APP_NAME,
    description="Dedicated Multi-Website Analytics & AI Chatbot Platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
static_path = BASE_DIR / "static"
templates_path = BASE_DIR / "templates"

app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
templates = Jinja2Templates(directory=str(templates_path))

# Include API routers
app.include_router(analytics_router)
app.include_router(chat_router)
app.include_router(chartbot_router)
app.include_router(lead_router)

# Page Routes
@app.get("/")
async def root():
    return RedirectResponse(url="/reports")

@app.get("/leads")
async def leads_page(request: Request):
    platform = request.query_params.get("platform", "startupflora")
    return templates.TemplateResponse(
        request=request,
        name="leads.html",
        context={"active_page": "leads", "platform": platform, "config": config}
    )

@app.get("/reports")
async def reports_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="reports.html",
        context={"active_page": "reports", "config": config}
    )

@app.get("/page-analytics")
async def page_analytics_page(request: Request):
    target_url = request.query_params.get("url", "")
    platform = request.query_params.get("platform", "living")
    days = int(request.query_params.get("days", 30))
    return templates.TemplateResponse(
        request=request,
        name="page_analytics.html",
        context={
            "active_page": "page-analytics",
            "target_url": target_url,
            "platform": platform,
            "days": days,
            "config": config
        }
    )

@app.get("/chat")
async def chat_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={"active_page": "chat", "config": config}
    )

@app.get("/settings")
async def settings_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={"active_page": "settings", "config": config}
    )
