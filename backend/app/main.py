import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.db.init_db import init_database
from app.services.cache_service import cache_service
from app.services.watchdog_service import watchdog_loop
from app.api.v1.api_router import api_v1_router
from app.api.websocket import router as websocket_router

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("coldstorage.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    logger.info("Starting Cold Storage Backend Application...")
    await init_database()
    await cache_service.init_redis()
    app.state.watchdog = asyncio.create_task(watchdog_loop())
    yield
    app.state.watchdog.cancel()
    try:
        await app.state.watchdog
    except asyncio.CancelledError:
        pass
    logger.info("Shutting down Cold Storage Backend Application...")
    await cache_service.close()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Decentralized IoT-Enabled Solar Cold Storage Monitoring, Psychrometric Physics, AI Spoilage Guardian & Farmer Cellular Alert Platform for North Eastern Region (NER)",
    lifespan=lifespan
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(api_v1_router, prefix=settings.API_V1_STR)
app.include_router(websocket_router)

@app.get("/doc", include_in_schema=False)
async def doc_redirect():
    """Redirect /doc to /docs."""
    return RedirectResponse(url="/docs")

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint providing service information and links to documentation."""
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "docs": "/docs",
        "health": "/health",
        "version": settings.VERSION
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """System health check endpoint."""
    return {
        "status": "HEALTHY",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

