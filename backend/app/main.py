from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, reports, settings as settings_api, tickets, wecom
from app.core.config import settings

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")
app.include_router(tickets.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(wecom.router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
