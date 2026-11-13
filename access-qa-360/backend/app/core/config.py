from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str
    SYNC_DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ANTHROPIC_API_KEY: str
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = "wiseflow-screenshots"
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    # Comma-separated emails that are made super admin when they register or sign in.
    SUPER_ADMIN_EMAILS: str = ""
    # Where uploaded builds and generated reports are kept. Mount a volume here in production.
    STORAGE_DIR: str = "storage"
    MAX_UPLOAD_MB: int = 300
    # Address of the web app, used in links inside emails and reset links.
    APP_URL: str = "http://localhost:5173"
    # Outgoing email. Leave SMTP_HOST empty to send no email; reset and invite links are then shared by hand.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    PASSWORD_RESET_MINUTES: int = 60
    # ---- Sign in with Google or Microsoft. Leave a provider's client id empty to switch it off. ----
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    # Your Microsoft Entra tenant id. Required for Microsoft sign-in: only accounts in this tenant may sign in.
    MICROSOFT_TENANT_ID: str = ""
    # Public address of this API, used as the address providers send people back to.
    # Empty means APP_URL + "/api/v1", which is right when the web app proxies /api (the production setup).
    SSO_REDIRECT_BASE: str = ""
    # ---- Plans and billing. The amounts are placeholders: change them before charging anyone. ----
    # Team plan, per seat per month: whole US dollars (Stripe) and whole rupees (Razorpay).
    TEAM_PRICE_USD: int = 29
    TEAM_PRICE_INR: int = 2400
    # Scans a free Individual account may start each month. 0 means no limit. Applies to new sign-ups.
    FREE_SCANS_PER_MONTH: int = 10
    # Where "Contact sales" on the pricing page sends people.
    SALES_EMAIL: str = ""
    # Leave a provider's keys empty to switch that provider off.
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    # Largest amount of source code, once unpacked, that one code scan will read.
    CODE_SCAN_MAX_MB: int = 500

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
