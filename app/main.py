from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import bcrypt

# Monkeypatch bcrypt for passlib compatibility (bcrypt 4.0.0+ removed __about__)
try:
    bcrypt.__about__
except AttributeError:
    bcrypt.__about__ = type('about', (object,), {'__version__': bcrypt.__version__})

from contextlib import asynccontextmanager
from app.api import router
from app.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="Helixa API", lifespan=lifespan, description="Unified microservice for generating AI Agent DNAs and manifestations.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "helixa"}
