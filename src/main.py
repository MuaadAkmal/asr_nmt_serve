"""Main FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api import auth, health, jobs
from src.config import get_settings
from src.db.session import init_db
from src.middleware.rate_limit import limiter

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    logger.info("Starting ASR-NMT Service...")

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

    logger.info("ASR-NMT Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down ASR-NMT Service...")


# Create FastAPI app
app = FastAPI(
    title="ASR-NMT Service",
    description="""
## Automatic Speech Recognition & Neural Machine Translation API

This service provides batch processing for:
- **ASR (Automatic Speech Recognition)**: Convert audio to text
- **NMT (Neural Machine Translation)**: Translate text between languages
- **ASR+NMT**: Combined transcription and translation

### Supported Languages
- English (en)
- Hindi (hi)
- Kannada (kn)
- Marathi (mr)
- Telugu (te)
- Malayalam (ml)
- Tamil (ta)

### Authentication
All API endpoints require authentication via API key.
Include your API key in the `Authorization` header:
```
Authorization: Bearer ask_your_api_key_here
```

### Rate Limiting
API requests are rate-limited per API key.
Default limits: 60 requests/minute, 500 requests/hour.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred",
        },
    )


# Include routers
app.include_router(health.router)
app.include_router(jobs.router)
app.include_router(auth.router)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with service info."""
    return {
        "service": "ASR-NMT Service",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
