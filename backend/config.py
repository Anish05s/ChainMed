from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://postgres:postgres123@localhost:5432/chainmed"
    REDIS_URL: str = "redis://localhost:6379"

    # ── App ───────────────────────────────────────────────────────────────────
    # IMPORTANT: override SECRET_KEY in production .env — never use the default
    SECRET_KEY: str = "chainmed-secret-key-change-in-production"
    ENVIRONMENT: str = "development"
    PUBLIC_APP_URL: str = "http://localhost:5173"
    API_BASE_URL: str = "http://localhost:8000"

    # CORS: comma-separated list of allowed origins for production
    # Example: "https://chainmed.example.com,https://app.chainmed.io"
    ALLOWED_ORIGINS: str = "*"

    # ── Blockchain (Ethereum Sepolia) ─────────────────────────────────────────
    # Leave empty → blockchain service runs in MOCK MODE (safe for demos)
    ETHEREUM_RPC_URL: str = ""
    ETHEREUM_PRIVATE_KEY: str = ""
    CONTRACT_ADDRESS: str = ""

    # ── External APIs ─────────────────────────────────────────────────────────
    OPENWEATHER_API_KEY: str = ""
    SENDGRID_API_KEY: str = ""
    MAPBOX_TOKEN: str = ""
    GEMINI_API_KEY: str = ""

    # ── Admin Passwords ───────────────────────────────────────────────────────
    ADMIN_MASTER_PASSWORD: str = "AdminMaster2026!"
    ADMIN_MANAGER_PASSWORD: str = "AdminManager2026!"
    ADMIN_DEV_PASSWORD: str = "AdminDev2026!"

    class Config:
        env_file = ".env"

    def allowed_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into a list for CORS middleware."""
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        return [o.strip().rstrip("/") for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
