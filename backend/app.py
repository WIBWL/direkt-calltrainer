"""FastAPI app: REST endpoints for setup data, WebSocket route for the live Session, static frontend."""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.session_ws import router as session_ws_router
from backend.languages import LANGUAGES
from backend.personas import PERSONAS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("calltrainer")

app = FastAPI(title="CallTrainer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session_ws_router)

FRONTEND_DIST_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")


@app.get("/health")
def health() -> dict[str, str]:
    """Plain health check."""
    return {"status": "ok"}


@app.get("/api/personas")
def list_personas() -> list[dict[str, str]]:
    """List Personas available for Session setup."""
    return [
        {"id": p.id, "name": p.name, "training_goal": p.training_goal}
        for p in PERSONAS.values()
    ]


@app.get("/api/languages")
def list_languages() -> list[dict[str, str]]:
    """List Languages available for Session setup."""
    return [{"id": id_, "name": name} for id_, name in LANGUAGES.items()]


app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True, check_dir=False), name="frontend")
