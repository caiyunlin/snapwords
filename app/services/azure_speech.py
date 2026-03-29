"""Azure Speech synthesis integration.

Provides a simple async wrapper around the Azure Cognitive Services Speech SDK.
Returns WAV bytes by default for reliable browser decoding.
"""
from __future__ import annotations
import os
import asyncio
import io
import re
import wave
from typing import Tuple
import azure.cognitiveservices.speech as speechsdk

AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")
AZURE_SPEECH_ENDPOINT = os.getenv("AZURE_SPEECH_ENDPOINT")  # Optional endpoint override
DEFAULT_VOICE = os.getenv("AZURE_SPEECH_VOICE", "en-US-AriaNeural")
DEFAULT_CHINESE_VOICE = os.getenv("AZURE_SPEECH_VOICE_ZH", "zh-CN-XiaoxiaoNeural")

class AzureSpeechConfigError(RuntimeError):
    """Raised when Speech configuration is missing."""

class AzureSpeechSynthesisError(RuntimeError):
    """Raised when synthesis fails with cancellation details."""


_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def choose_voice_for_text(text: str, voice: str | None = None) -> str:
    """Pick a voice that matches the script used in the text.

    Pure Chinese study content fails with the default English voice because the
    Azure SDK can return an empty audio payload while still reporting success.
    """
    if voice:
        return voice
    if _CJK_RE.search(text):
        return DEFAULT_CHINESE_VOICE
    return DEFAULT_VOICE


def normalize_wav_bytes(audio_bytes: bytes) -> bytes:
    """Rewrite WAV bytes with a standard PCM RIFF header for browser compatibility.

    Azure Speech can return WAV files with an extended fmt chunk that some
    browsers reject in Web Audio's decodeAudioData(). Rewriting the container
    keeps the same PCM frames while producing a simpler header.
    """
    try:
        with io.BytesIO(audio_bytes) as source:
            with wave.open(source, "rb") as reader:
                channels = reader.getnchannels()
                sample_width = reader.getsampwidth()
                frame_rate = reader.getframerate()
                frame_count = reader.getnframes()
                frames = reader.readframes(frame_count)

        with io.BytesIO() as target:
            with wave.open(target, "wb") as writer:
                writer.setnchannels(channels)
                writer.setsampwidth(sample_width)
                writer.setframerate(frame_rate)
                writer.writeframes(frames)
            return target.getvalue()
    except (wave.Error, EOFError):
        return audio_bytes

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

    speech_config.speech_synthesis_voice_name = choose_voice_for_text(text, voice)
    # Request WAV output for more reliable decoding in browsers/Web Audio.
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
    )

    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)  # None => capture in result.audio_data
    result = synthesizer.speak_text_async(text).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        # result.audio_data already contains the entire binary payload in requested format.
        audio_bytes: bytes = result.audio_data  # type: ignore
        if not audio_bytes:
            active_voice = choose_voice_for_text(text, voice)
            raise AzureSpeechSynthesisError(
                f"Speech synthesis returned empty audio for voice '{active_voice}'"
            )
        return normalize_wav_bytes(audio_bytes), "audio/wav"
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation = result.cancellation_details
        msg = f"Speech synthesis canceled: {cancellation.reason}. Error details: {getattr(cancellation, 'error_details', '')}"
        raise AzureSpeechSynthesisError(msg)
    else:
        snippet = text[:50] + ("..." if len(text) > 50 else "")
        raise AzureSpeechSynthesisError(f"Unexpected synthesis result: {result.reason}; text snippet='{snippet}'")
