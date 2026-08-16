from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from research_agent.api import router
from research_agent.catalog import seed_catalog
from research_agent.config import get_settings
from research_agent.db import SessionLocal, create_schema


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_schema()
    with SessionLocal() as session:
        seed_catalog(session, get_settings().source_catalog_path)
    yield


app = FastAPI(
    title="ContResAI",
    version="0.1.0",
    description="Guarded browser research with an independently confirmed knowledge graph.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.include_router(router)
