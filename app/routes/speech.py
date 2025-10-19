"""Speech synthesis endpoint definitions."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from app.services.azure_speech import synthesize_speech, DEFAULT_VOICE, AzureSpeechConfigError, AzureSpeechSynthesisError

router = APIRouter(tags=["speech"])

class SpeakRequest(BaseModel):
    text: str
    voice: str | None = None  # Optional voice name.

@router.get("/speech/default-voice")
async def get_default_voice():
    return {"success": True, "data": {"default_voice": DEFAULT_VOICE}}

@router.post("/speak")
async def speak(req: SpeakRequest):
    """Accept text and return synthesized speech audio stream."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    try:
        audio_bytes, content_type = await synthesize_speech(req.text, voice=req.voice)
    except AzureSpeechConfigError as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e), "type": "config"})
    except AzureSpeechSynthesisError as e:
        return JSONResponse(status_code=502, content={"success": False, "error": str(e), "type": "synthesis"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e), "type": "unknown"})
    return StreamingResponse(iter([audio_bytes]), media_type=content_type, headers={"X-Audio-Format": content_type})
