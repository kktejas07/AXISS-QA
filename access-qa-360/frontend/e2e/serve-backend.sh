#!/usr/bin/env bash
# Starts the API for the browser tests on a throwaway SQLite database. Nothing here is used in production.
set -euo pipefail
cd "$(dirname "$0")/../../backend"
export PYTHONPATH=. ENVIRONMENT=test SECRET_KEY=e2e-only-not-a-real-secret ANTHROPIC_API_KEY=e2e-placeholder
export DATABASE_URL=sqlite+aiosqlite:///./e2e.db SYNC_DATABASE_URL=sqlite:///./e2e.db REDIS_URL=redis://localhost:6379/0
# The chatbot test talks to a stand-in bot on this machine, which the scanner refuses unless told otherwise.
export ALLOW_PRIVATE_TARGETS=true
export APP_URL=http://localhost:5183 CORS_ORIGINS=http://localhost:5183 STORAGE_DIR=e2e-storage
rm -rf e2e.db e2e-storage
python - <<'PY'
import asyncio
import app.main  # noqa: F401  importing the app registers every table
from app.core.database import Base, engine

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(main())
PY
exec python -m uvicorn app.main:app --port 8010 --log-level warning
