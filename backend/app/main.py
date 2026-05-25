from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, datasets, health, jobs, models, payments
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="OpenReef API", version="0.1.0", lifespan=lifespan)

# Parse allowed origins from config (comma-separated)
_cors_origins = [o.strip() for o in settings.frontend_url.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router)
app.include_router(datasets.router)
app.include_router(jobs.router)
app.include_router(models.router)
app.include_router(payments.router)
app.include_router(health.router)
