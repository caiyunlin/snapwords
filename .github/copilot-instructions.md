# 🤖 GitHub Copilot Instructions for SnapWords.AI

## 🧩 Project Overview

**SnapWords.AI** is a lightweight web application for learning English words through camera capture and AI assistance.  
Users can take a photo of a textbook page or upload an image, then the app will:
1. Extract words using **Azure AI Foundry Vision OCR**.
2. Clean and filter valid English words.
3. Use **Azure Speech Service (TTS)** to read them aloud.

The project backend runs in **Python (FastAPI)** and will be **containerized with Docker**.

---

## 🧠 Copilot Development Goals

When generating or suggesting code, Copilot should:

- Use **Python 3.10+**.
- Prefer **FastAPI** for backend web framework.
- Expose RESTful endpoints for:
  - `/upload` → accepts image file, returns extracted words.
  - `/speak` → accepts text, returns a generated audio stream (MP3 or WAV).
- Integrate with **Azure AI Foundry APIs** (OCR, GPT/Text, Speech).
- Be structured and production-ready with logging and error handling.
- Generate Dockerfile and requirements.txt compatible with Azure deployment.

---

## ⚙️ Tech Stack

| Component | Technology |
|------------|-------------|
| Backend | FastAPI |
| OCR | Azure AI Foundry Vision API |
| Text Processing | Azure AI Foundry Text Analytics or GPT Model |
| Speech Synthesis | Azure Speech Service |
| Container | Docker (Python base image) |
| Frontend | Minimal HTML + JavaScript (served by FastAPI static) |

---

## 📦 Expected Project Structure

Copilot should help maintain this folder layout:

snapwords/
│
├── app/
│ ├── main.py # FastAPI entrypoint
│ ├── routes/
│ │ ├── ocr.py # /upload endpoint
│ │ ├── speech.py # /speak endpoint
│ ├── services/
│ │ ├── azure_ocr.py # Functions for calling Azure Vision OCR
│ │ ├── azure_speech.py # Functions for calling Azure Speech
│ │ └── text_utils.py # Cleaning and filtering extracted words
│ ├── static/
│ │ ├── index.html # Simple web UI
│ │ ├── script.js # Frontend logic
│ │ └── style.css
│ └── init.py
│
├── Dockerfile
├── requirements.txt
├── README.md
└── .github/copilot-instructions.md


---

## 🚀 Copilot Behavior Guidelines

When completing code, Copilot should:

- Prefer clean, readable, production-quality code.
- Use `async` endpoints and `aiohttp` or `httpx` for async API calls.
- Return JSON responses with consistent schema:
  ```json
  {
    "success": true,
    "data": { "words": ["apple", "banana"] }
  }

- Handle errors gracefully with proper logging.
- Avoid exposing API keys directly; use environment variables or os.getenv().


## Environment Variables

Copilot should assume the following environment variables exist:

AZURE_OCR_ENDPOINT=
AZURE_OCR_KEY=
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=

Use python-dotenv to load them in local development.

## 🐳 Docker Configuration

Copilot should produce a minimal but functional Docker setup:

### Dockerfile

```
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### requirements.txt
```
fastapi
uvicorn
httpx
python-dotenv
pydantic
azure-cognitiveservices-speech
```

### 🧭 Author: Calvin Cai
Powered by Azure AI Foundry + GitHub Copilot


