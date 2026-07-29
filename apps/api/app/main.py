from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import admin, analysis, auth, chat, departments, documents, knowledge, legal_cases, legal_review, reports, users

settings = get_settings()

app = FastAPI(
    title="TOPEC Legal AI API",
    description="TOPEC 사내 법률검토 AI 시스템 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.get("/api/health")
def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT, "ai_provider": settings.AI_PROVIDER}


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(departments.router)
app.include_router(documents.router)
app.include_router(analysis.router)
app.include_router(knowledge.router)
app.include_router(chat.router)
app.include_router(reports.router)
app.include_router(legal_review.router)
app.include_router(legal_cases.router)
app.include_router(admin.router)
