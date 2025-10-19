"""Azure Speech synthesis integration.

Provides a simple async wrapper around the Azure Cognitive Services Speech SDK.
Returns MP3 bytes by default for efficient transfer.
"""
from __future__ import annotations
import os
import asyncio
from typing import Tuple
import azure.cognitiveservices.speech as speechsdk

AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")
AZURE_SPEECH_ENDPOINT = os.getenv("AZURE_SPEECH_ENDPOINT")  # Optional endpoint override
DEFAULT_VOICE = os.getenv("AZURE_SPEECH_VOICE", "en-US-AriaNeural")

class AzureSpeechConfigError(RuntimeError):
    """Raised when Speech configuration is missing."""

class AzureSpeechSynthesisError(RuntimeError):
    """Raised when synthesis fails with cancellation details."""

async def synthesize_speech(text: str, voice: str | None = None) -> Tuple[bytes, str]:
    """Synthesize speech and return (audio_bytes, content_type).

    Args:
        text: Input text to speak.
        voice: Optional Azure voice name; falls back to DEFAULT_VOICE.
    Returns:
        Tuple of (audio bytes, MIME content type).
    Raises:
        AzureSpeechConfigError: Missing env configuration.
        AzureSpeechSynthesisError: Cancellation or failure in synthesis.
    """
    if not AZURE_SPEECH_KEY or (not AZURE_SPEECH_REGION and not AZURE_SPEECH_ENDPOINT):
        raise AzureSpeechConfigError("Missing Azure Speech configuration environment variables (AZURE_SPEECH_KEY + REGION or ENDPOINT)")

    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Text is empty after stripping whitespace")

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _synthesize_blocking, cleaned, voice)

def _synthesize_blocking(text: str, voice: str | None) -> Tuple[bytes, str]:
    # Configure speech.
    if AZURE_SPEECH_ENDPOINT:
        speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, endpoint=AZURE_SPEECH_ENDPOINT)
    else:
        speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)

    speech_config.speech_synthesis_voice_name = voice or DEFAULT_VOICE
    # Request MP3 output (smaller than raw PCM). Adjust as needed.
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
    )

    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)  # None => capture in result.audio_data
    result = synthesizer.speak_text_async(text).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        # result.audio_data already contains the entire binary payload in requested format.
        audio_bytes: bytes = result.audio_data  # type: ignore
        return audio_bytes, "audio/mpeg"
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation = result.cancellation_details
        msg = f"Speech synthesis canceled: {cancellation.reason}. Error details: {getattr(cancellation, 'error_details', '')}"
        raise AzureSpeechSynthesisError(msg)
    else:
            snippet = text[:50] + ("..." if len(text) > 50 else "")
            raise AzureSpeechSynthesisError(f"Unexpected synthesis result: {result.reason}; text snippet='{snippet}'")
