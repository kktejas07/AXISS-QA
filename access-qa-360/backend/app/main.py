from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import auth, projects, suites, runs, webhooks, scans, vulnerabilities, gaps, test_cases, reports

app = FastAPI(
    title="Access QA 360 API",
    description="AI-native QA platform by AXISS Group",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(suites.router, prefix="/api/v1")
app.include_router(runs.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(scans.router, prefix="/api/v1")
app.include_router(vulnerabilities.router, prefix="/api/v1")
app.include_router(gaps.router, prefix="/api/v1")
app.include_router(test_cases.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "access-qa-360"}
