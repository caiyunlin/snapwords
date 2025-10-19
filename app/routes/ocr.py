"""OCR upload endpoint definitions."""
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from app.services.azure_ocr import extract_words_from_image
from app.services.text_utils import clean_and_filter_words
from PIL import Image
import io

router = APIRouter(tags=["ocr"])

@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """Accept an image file, run OCR, return cleaned word list."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    # Read file bytes.
    image_bytes = await file.read()
    # Validate dimensions (Azure requires 50x50 <= w,h <= 10000x10000)
    try:
        im = Image.open(io.BytesIO(image_bytes))
        w, h = im.size
        if w < 50 or h < 50:
            return JSONResponse(status_code=400, content={"success": False, "error": f"Image too small ({w}x{h}). Minimum is 50x50."})
        if w > 10000 or h > 10000:
            return JSONResponse(status_code=400, content={"success": False, "error": f"Image too large ({w}x{h}). Maximum is 10000x10000."})
    except Exception:
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid image file"})
    # Extract words via OCR service.
    try:
        raw_words = await extract_words_from_image(image_bytes)
    except Exception as e:  # Broad catch to wrap into consistent JSON shape.
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
    # Clean and filter.
    cleaned = clean_and_filter_words(raw_words)
    return {"success": True, "data": {"words": cleaned}}
