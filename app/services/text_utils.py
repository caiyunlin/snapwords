"""Text utility helpers for SnapWords.

Provides functions to clean, normalize, and filter words extracted from OCR.
"""
from __future__ import annotations
import re
from typing import Iterable, List

WORD_REGEX = re.compile(r"^[A-Za-z]+$")

def clean_and_filter_words(words: Iterable[str]) -> List[str]:
    """Normalize words (lowercase) and filter out non-alphabetic entries and duplicates."""
    seen = set()
    cleaned: List[str] = []
    for w in words:
        w_norm = w.strip().lower()
        if not w_norm or len(w_norm) == 1:  # Skip empty and single letters.
            continue
        if not WORD_REGEX.match(w_norm):
            continue
        if w_norm in seen:
            continue
        seen.add(w_norm)
        cleaned.append(w_norm)
    return cleaned
