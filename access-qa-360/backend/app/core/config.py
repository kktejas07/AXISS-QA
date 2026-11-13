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
    # Largest amount of source code, once unpacked, that one code scan will read.
    CODE_SCAN_MAX_MB: int = 500

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
