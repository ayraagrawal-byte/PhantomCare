from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.analysis import router as analysis_router
from api.cases import router as cases_router
from api.config import settings
from api.investigations import router as investigations_router
from api.schemas import HealthResponse

app = FastAPI(
    title="PhantomCare API",
    description="Evidence-backed hospice registration and building-fit investigation API.",
    version="0.1.0",
)

dashboard_origins = [settings.dashboard_origin]
dashboard_url = urlsplit(settings.dashboard_origin)
loopback_alias = {"localhost": "127.0.0.1", "127.0.0.1": "localhost"}.get(dashboard_url.hostname)
if loopback_alias and settings.environment == "development":
    port = f":{dashboard_url.port}" if dashboard_url.port is not None else ""
    dashboard_origins.append(f"{dashboard_url.scheme}://{loopback_alias}{port}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=dashboard_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(analysis_router)
app.include_router(cases_router)
app.include_router(investigations_router)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", environment=settings.environment)
