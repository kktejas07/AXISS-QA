# Access QA 360

AI-native QA platform by AXISS Group. Generate Playwright tests from plain-English descriptions using Claude, run them automatically, and get AI-powered failure triage.

## Architecture

| Service   | Port  | Description                              |
|-----------|-------|------------------------------------------|
| api       | 8000  | FastAPI backend with JWT auth            |
| worker    | -     | Celery worker running Playwright tests   |
| frontend  | 5173  | React + TypeScript dashboard             |
| db        | 5432  | PostgreSQL 15 + pgvector                 |
| redis     | 6379  | Celery broker + result backend           |

## Quick Start

```bash
# 1. Copy and configure environment
cp backend/.env.example backend/.env
# Edit backend/.env — set ANTHROPIC_API_KEY

# 2. Start all services
docker compose up --build

# 3. Run database migrations
docker compose run --rm migrate

# 4. Open the app
open http://localhost:5173
```

## Usage

1. Register an account at the login page
2. Create a project with your application's base URL
3. Click "Generate Tests" and describe a feature in plain English
4. Claude Sonnet generates Playwright tests (~15 seconds)
5. Click "Run Now" to execute tests via the Celery worker
6. Failed tests get auto-triaged by Claude Haiku

## AI Cost

- Test generation: ~$0.024/suite (Claude Sonnet, ~8K tokens)
- Failure triage: ~$0.001/run (Claude Haiku, ~300 tokens)
- Calls are on-demand only, never on a timer

## Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2
- **AI**: Anthropic Claude (Sonnet for generation, Haiku for triage)
- **Runner**: Playwright (Python), headless Chromium
- **Queue**: Celery 5 + Redis 7
- **Database**: PostgreSQL 15 + pgvector
- **Frontend**: React 18, TypeScript, Vite 5, TailwindCSS
- **Infra**: Docker Compose (dev), AWS Fargate-ready
