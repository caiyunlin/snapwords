"""Azure OCR service integration using Read API v3.2.

Implements the two-step asynchronous OCR flow:
1. POST image bytes to /vision/v3.2/read/analyze -> returns 202 with Operation-Location header.
2. Poll the Operation-Location until status == succeeded.
3. Parse readResults lines/words to return a flat list of words.

Environment variables required:
    AZURE_OCR_ENDPOINT : Base endpoint e.g. https://<name>.cognitiveservices.azure.com/
    AZURE_OCR_KEY      : Subscription key
Optional tuning env vars:
    AZURE_OCR_POLL_INTERVAL_MS (default 500)
    AZURE_OCR_MAX_POLL (default 20)
"""
from __future__ import annotations
import os
import asyncio
import httpx
from typing import List

AZURE_OCR_ENDPOINT = os.getenv("AZURE_OCR_ENDPOINT")
AZURE_OCR_KEY = os.getenv("AZURE_OCR_KEY")

POLL_INTERVAL_MS = int(os.getenv("AZURE_OCR_POLL_INTERVAL_MS", "500"))
MAX_POLL = int(os.getenv("AZURE_OCR_MAX_POLL", "20"))

READ_API_PATH = "/vision/v3.2/read/analyze"  # Adjust if using different API version.

class AzureOCRConfigError(RuntimeError):
    """Raised when OCR configuration is missing."""

class AzureOCROperationError(RuntimeError):
    """Raised when OCR operation fails or times out."""

async def extract_words_from_image(image_bytes: bytes) -> List[str]:
    """Run Azure Read OCR on the provided image bytes and return list of words."""
    missing = []
    if not AZURE_OCR_ENDPOINT:
        missing.append("AZURE_OCR_ENDPOINT")
    if not AZURE_OCR_KEY:
        missing.append("AZURE_OCR_KEY")
    if missing:
        raise AzureOCRConfigError(f"Missing environment variables: {', '.join(missing)}")

    analyze_url = f"{AZURE_OCR_ENDPOINT.rstrip('/')}{READ_API_PATH}"
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_OCR_KEY,
        "Content-Type": "application/octet-stream",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Step 1: submit image for analysis
        submit_resp = await client.post(analyze_url, headers=headers, content=image_bytes)
        if submit_resp.status_code >= 400:
            # Include truncated body for diagnostics.
            body = submit_resp.text[:300]
            raise AzureOCROperationError(f"Analyze request failed {submit_resp.status_code}: {body}")
        operation_location = submit_resp.headers.get("Operation-Location")
        if not operation_location:
            raise AzureOCROperationError("Missing Operation-Location header from analyze response")

        # Step 2: poll result
        interval = POLL_INTERVAL_MS / 1000.0
        for _ in range(MAX_POLL):
            poll_resp = await client.get(operation_location, headers={"Ocp-Apim-Subscription-Key": AZURE_OCR_KEY})
            if poll_resp.status_code >= 400:
                body = poll_resp.text[:300]
                raise AzureOCROperationError(f"Poll request failed {poll_resp.status_code}: {body}")
            result_json = poll_resp.json()
            status = result_json.get("status")
            if status == "succeeded":
                return _parse_read_results(result_json)
            if status == "failed":
                raise AzureOCROperationError("OCR analysis failed")
            await asyncio.sleep(interval)

    raise AzureOCROperationError("OCR operation timed out before completion")

def _parse_read_results(data: dict) -> List[str]:
    """Extract words from Azure Read API succeeded payload."""
    words: List[str] = []
    analyze = data.get("analyzeResult", {})
    read_results = analyze.get("readResults", [])
    for page in read_results:
        for line in page.get("lines", []):
            # Prefer explicit words array if present for more granular bounding boxes.
            line_words = line.get("words")
            if line_words:
                for w in line_words:
                    txt = w.get("text")
                    if txt:
                        words.append(txt)
            else:
                # Fallback: split line text
                line_text = line.get("text")
                if line_text:
                    for part in line_text.split():
                        words.append(part)
    return words
