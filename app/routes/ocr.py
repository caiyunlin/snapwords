"""OCR upload endpoint definitions."""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from app.services.azure_ocr import analyze_image_text
from app.services.prompt_extractor import extract_items_from_ocr, get_prompt_templates, PromptExtractionConfigError, PromptExtractionError
from PIL import Image
import io

router = APIRouter(tags=["ocr"])


@router.get("/upload/prompt-templates")
async def get_upload_prompt_templates():
    return {"success": True, "data": {"templates": get_prompt_templates()}}

@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    prompt_template: str = Form("template_1"),
    prompt_text: str = Form(""),
):
    """Accept an image file, run OCR, return cleaned word list."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="上传的文件必须是图片")
    # Read file bytes.
    image_bytes = await file.read()
    # Validate dimensions (Azure requires 50x50 <= w,h <= 10000x10000)
    try:
        im = Image.open(io.BytesIO(image_bytes))
        w, h = im.size
        if w < 50 or h < 50:
            return JSONResponse(status_code=400, content={"success": False, "error": f"图片尺寸过小（{w}x{h}），最小支持 50x50。"})
        if w > 10000 or h > 10000:
            return JSONResponse(status_code=400, content={"success": False, "error": f"图片尺寸过大（{w}x{h}），最大支持 10000x10000。"})
    except Exception:
        return JSONResponse(status_code=400, content={"success": False, "error": "无效的图片文件"})
    # Extract OCR text via Azure service.
    try:
        ocr_result = await analyze_image_text(image_bytes)
    except Exception as e:  # Broad catch to wrap into consistent JSON shape.
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
    # Post-process OCR with built-in template or custom prompt.
    try:
        items = await extract_items_from_ocr(
            image_bytes=image_bytes,
            ocr_lines=ocr_result.lines,
            ocr_words=ocr_result.words,
            ocr_line_details=ocr_result.line_details,
            template_id=prompt_template,
            prompt_text=prompt_text,
        )
    except PromptExtractionConfigError as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e), "type": "prompt_config"})
    except PromptExtractionError as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e), "type": "prompt"})
    return {
        "success": True,
        "data": {
            "items": items,
            "words": items,
            "prompt_template": prompt_template,
            "prompt_text": prompt_text,
        },
    }
