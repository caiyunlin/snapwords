import io
import wave

from app.services.azure_speech import choose_voice_for_text, normalize_wav_bytes


def _build_extended_fmt_wav() -> bytes:
    with io.BytesIO() as canonical_buffer:
        with wave.open(canonical_buffer, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(16000)
            writer.writeframes(b"\x00\x00" * 32)
        canonical = canonical_buffer.getvalue()

    fmt_chunk_size = int.from_bytes(canonical[16:20], "little")
    assert fmt_chunk_size == 16

    extended = bytearray()
    extended.extend(canonical[:16])
    extended.extend((18).to_bytes(4, "little"))
    extended.extend(canonical[20:36])
    extended.extend(b"\x00\x00")
    extended.extend(canonical[36:])
    riff_size = len(extended) - 8
    extended[4:8] = riff_size.to_bytes(4, "little")
    return bytes(extended)


def test_normalize_wav_bytes_rewrites_extended_fmt_chunk():
    normalized = normalize_wav_bytes(_build_extended_fmt_wav())

    assert normalized[:4] == b"RIFF"
    assert normalized[8:12] == b"WAVE"
    assert int.from_bytes(normalized[16:20], "little") == 16

    with io.BytesIO(normalized) as buffer:
        with wave.open(buffer, "rb") as reader:
            assert reader.getnchannels() == 1
            assert reader.getsampwidth() == 2
            assert reader.getframerate() == 16000
            assert reader.getnframes() == 32


def test_choose_voice_for_text_uses_chinese_voice_for_cjk():
    assert choose_voice_for_text("理想的；完美的") == "zh-CN-XiaoxiaoNeural"


def test_choose_voice_for_text_uses_default_voice_for_english():
    assert choose_voice_for_text("ideal") == "en-US-AriaNeural"


def test_choose_voice_for_text_respects_explicit_voice():
    assert choose_voice_for_text("理想的；完美的", "custom-voice") == "custom-voice"