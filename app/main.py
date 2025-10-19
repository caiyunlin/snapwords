"""FastAPI application entrypoint for SnapWords.

This app exposes two primary endpoints:
- POST /upload : Accepts an image file and returns extracted words.
- POST /speak  : Accepts text and returns synthesized speech audio.

Environment variables expected:
- AZURE_OCR_ENDPOINT
- AZURE_OCR_KEY
- AZURE_SPEECH_KEY
- AZURE_SPEECH_REGION

Run locally:
    uvicorn app.main:app --reload
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

######################################################################
# Environment loading
# Load .env from project root if present so services see env variables.
######################################################################
# Determine project root (two levels up: app/ -> repo root)
_root_env = Path(__file__).resolve().parent.parent / ".env"
if _root_env.exists():
    load_dotenv(dotenv_path=_root_env)  # load silently

from app.routes.ocr import router as ocr_router  # noqa: E402 (after dotenv load)
from app.routes.speech import router as speech_router  # noqa: E402

app = FastAPI(title="SnapWords.AI", version="0.1.0")

# Allow all origins for development; restrict in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers.
app.include_router(ocr_router, prefix="")
app.include_router(speech_router, prefix="")

# Serve static files for simple frontend.
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")

@app.get("/health", tags=["system"])
async def health() -> dict:
    """Health check endpoint."""
    return {"success": True, "data": {"status": "ok"}}

@app.get("/config", tags=["system"])
async def config() -> dict:
    """Return non-secret configuration diagnostics to help debugging environment loading.

    Does NOT return actual keys, only whether they are set.
    """
    def _flag(name: str) -> bool:
        return bool(os.getenv(name))
    return {
        "success": True,
        "data": {
            "env_loaded": _root_env.exists(),
            "AZURE_OCR_ENDPOINT": _flag("AZURE_OCR_ENDPOINT"),
            "AZURE_OCR_KEY": _flag("AZURE_OCR_KEY"),
            "AZURE_SPEECH_KEY": _flag("AZURE_SPEECH_KEY"),
            "AZURE_SPEECH_REGION": _flag("AZURE_SPEECH_REGION"),
            "AZURE_SPEECH_ENDPOINT": _flag("AZURE_SPEECH_ENDPOINT"),
        }
    }
