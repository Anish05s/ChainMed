import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import settings

# ── Routers ──────────────────────────────────────────────────────────────────
from auth.router import router as auth_router
from manufacturer.router import router as manufacturer_router
from supplier.router import router as supplier_router
from consumer.router import router as consumer_router
from verification_ai.router import router as verification_ai_router
from approval_logs.router import router as approval_logs_router
from shared.router import router as shared_router
from notification_service.router import router as notifications_router
from crisis_ai.router import router as crisis_router

# ── Services ─────────────────────────────────────────────────────────────────
from blockchain_service.service import init_blockchain_service
from notification_service.service import init_redis
from inventory_ai.monitor import start_scheduler
from news_monitor.stub import start_news_monitor
from database import SessionLocal

logger = logging.getLogger(__name__)

# ── Scheduler reference (kept alive for app lifetime) ────────────────────────
_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan — runs startup then yields, then runs shutdown."""
    global _scheduler

    # ── Addition 5 — CORS production safety guard ─────────────────────────────
    # Prevents wildcard CORS from accidentally being deployed to production.
    # Set ENVIRONMENT=production and ALLOWED_ORIGINS=<your-frontend-url> in .env
    if settings.ENVIRONMENT == "production" and settings.ALLOWED_ORIGINS == "*":
        raise RuntimeError(
            "CRITICAL SECURITY GUARD: ALLOWED_ORIGINS must not be '*' in production. "
            "Set it to your exact frontend domain in Railway environment variables, e.g. "
            "ALLOWED_ORIGINS=https://chainmed-mauve.vercel.app"
        )
    # ─────────────────────────────────────────────────────────────────────────

    # 1. Blockchain service (mock or real Sepolia)
    init_blockchain_service(
        rpc_url=settings.ETHEREUM_RPC_URL,
        private_key=settings.ETHEREUM_PRIVATE_KEY,
        contract_address=settings.CONTRACT_ADDRESS,
    )

    # 2. Redis (graceful fallback if unavailable)
    init_redis(settings.REDIS_URL)

    # 3. Inventory AI scheduler
    _scheduler = start_scheduler(SessionLocal)

    # 4. News monitor (Phase 3 stub)
    start_news_monitor(settings.NEWS_API_KEY)

    logger.info("ChainMed API started — environment: %s", settings.ENVIRONMENT)

    yield  # ← application runs here

    # Shutdown
    if _scheduler:
        _scheduler.shutdown(wait=False)
        logger.info("Inventory AI scheduler stopped.")


app = FastAPI(
    title="ChainMed API",
    version="2.0.0",
    description=(
        "AI + Blockchain pharmaceutical supply chain verification and "
        "crisis intelligence platform."
    ),
    lifespan=lifespan,
)

# ── Rate Limiter ──────────────────────────────────────────────────────────────
# Uses Redis if available; falls back to in-memory so app never crashes on boot.
try:
    limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)
except Exception:
    limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Static files (QR codes, etc.) ────────────────────────────────────────────
_static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(os.path.join(_static_dir, "qr"), exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# ── CORS ─────────────────────────────────────────────────────────────────────
# Set ALLOWED_ORIGINS in .env to your deployed frontend URL before going live.
# Example: ALLOWED_ORIGINS=https://chainmed.example.com
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list(),
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

from admin.router import router as admin_router

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(manufacturer_router)
app.include_router(supplier_router)
app.include_router(consumer_router)
app.include_router(verification_ai_router)
app.include_router(approval_logs_router)
app.include_router(shared_router)
app.include_router(notifications_router)
app.include_router(crisis_router)
app.include_router(admin_router)


@app.get("/health")
def health_check():
    from blockchain_service.service import get_blockchain_service
    bc = get_blockchain_service()
    return {
        "status": "ok",
        "project": "ChainMed",
        "version": "2.0.0",
        "environment": settings.ENVIRONMENT,
        "blockchain_mode": "mock" if bc.is_mock else "sepolia",
    }