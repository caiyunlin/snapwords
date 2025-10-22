# SnapWords.AI

SnapWords.AI lets you snap a photo of English text and quickly hear and study the extracted words.

## Quick Test
https://snapwords.bravemushroom-502e9645.southeastasia.azurecontainerapps.io/  

![](app/static/qr.png)

## Features
* Upload an image and extract words (Azure OCR Read API implementation).
* Clean, deduplicate and normalize words.
* Convert text to speech using Azure Speech Service.
* Minimal web UI served by FastAPI static files.

## Project Structure
```
app/
	main.py            # FastAPI app entrypoint
	routes/
		ocr.py           # /upload endpoint
		speech.py        # /speak endpoint
	services/
		azure_ocr.py     # Azure OCR integration (placeholder logic)
		azure_speech.py  # Azure Speech synthesis integration
		text_utils.py    # Word cleaning helpers
	static/            # Frontend assets (index.html, script.js, style.css)
tests/
	test_text_utils.py # Basic unit test
requirements.txt
Dockerfile
```

## Environment Variables
Set (e.g. in a `.env` file for local development):
```
AZURE_OCR_ENDPOINT=https://<your-resource>.cognitiveservices.azure.com/
AZURE_OCR_KEY=<your-key>
AZURE_SPEECH_KEY=<your-speech-key>
AZURE_SPEECH_REGION=<speech-region>
# Optional explicit speech endpoint override (if provided by Azure):
AZURE_SPEECH_ENDPOINT=https://eastus2.tts.speech.microsoft.com
# Optional tuning (defaults shown)
AZURE_OCR_POLL_INTERVAL_MS=500
AZURE_OCR_MAX_POLL=20
```

## Local Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
# Use a custom port (e.g. 8080):
# uvicorn app.main:app --reload --port 8080
```
Navigate to: http://localhost:8000

## API
### POST /upload
Multipart form field `file` (image). Returns JSON:
```json
{"success": true, "data": {"words": ["apple", "banana"]}}
```

### POST /speak
JSON body: `{ "text": "Hello world" }` streams audio response.

## Tests
```powershell
pytest -q
```
(Install pytest if adding more tests.)

## Docker
```powershell
docker build -t snapwords .
docker run -p 8000:8000 --env-file .env snapwords
```

## OCR Implementation
The backend uses Azure Read API v3.2 asynchronous flow:
1. POST image bytes to `/vision/v3.2/read/analyze`.
2. Poll `Operation-Location` until `status == succeeded`.
3. Parse `analyzeResult.readResults.lines.words` collecting text values.

Tuning: adjust poll interval and attempts via env vars.

Image constraints (Azure Vision):
* Min dimensions: 50 x 50 px
* Max dimensions: 10000 x 10000 px
* Oversized or undersized images are rejected before calling Azure.

## Notes
* Improve error handling, logging, and authentication for production.
* Add caching or pagination if word lists grow large.
* Rotate any keys that were accidentally committed; `.env` is now in `.gitignore`.

## License
TBD

