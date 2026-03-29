"""Text utility helpers for SnapWords.

Provides functions to clean, normalize, and filter words extracted from OCR.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Iterable, List

from app.services.azure_ocr import OCRLine

WORD_REGEX = re.compile(r"^[A-Za-z]+$")
CHINESE_SEGMENT_REGEX = re.compile(r"[\u4e00-\u9fff][\u4e00-\u9fff0-9、，；：:（）()《》“”‘’·\-\s]*")
CHINESE_EDGE_TRIM_REGEX = re.compile(r"(^[^\u4e00-\u9fff]+|[^\u4e00-\u9fff]+$)")
SPACE_REGEX = re.compile(r"\s+")
ENTRY_HEADWORD_REGEX = re.compile(r"^\s*(?:\d{1,5}\s+)?\*?([A-Za-z][A-Za-z\-']*)\b(.*)$")
PART_OF_SPEECH_REGEX = re.compile(r"\b(?:adj|adv|n|v|vt|vi|prep|conj|pron|num|art|aux|int|phr)\.", re.IGNORECASE)
PHONETIC_REGEX = re.compile(r"/[^/]{0,80}/")
ONLY_POS_PREFIX_REGEX = re.compile(r"^\s*(?:[A-Za-z]+\.)\s*")
NOISE_LINE_REGEX = re.compile(r"^\s*(?:词组|辨析|派生|拓展|联想|用法|搭配)")


@dataclass
class VocabularyEntry:
    word: str
    meaning: str

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


def extract_chinese_explanations(lines: Iterable[str]) -> List[str]:
    """Extract deduplicated Chinese explanation segments from OCR lines."""
    seen = set()
    extracted: List[str] = []
    for line in lines:
        for segment in CHINESE_SEGMENT_REGEX.findall(line):
            normalized = _normalize_chinese_segment(segment)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            extracted.append(normalized)
    return extracted


def extract_vocabulary_entries(lines: Iterable[str], include_continuations: bool = True) -> List[VocabularyEntry]:
    """Parse dictionary-style OCR lines into word/meaning pairs.

    Expected format resembles numbered vocabulary lists where each entry starts
    with an index and a headword, followed by phonetics, part-of-speech labels,
    and Chinese meanings. Example sentences, phrase blocks, and analysis notes
    are ignored.
    """
    entries: List[VocabularyEntry] = []
    current_word = ""
    current_meanings: List[str] = []

    def flush_current() -> None:
        nonlocal current_word, current_meanings
        if not current_word:
            return
        merged = _merge_meanings(current_meanings)
        if merged:
            entries.append(VocabularyEntry(word=current_word, meaning=merged))
        current_word = ""
        current_meanings = []

    for raw_line in lines:
        line = SPACE_REGEX.sub(" ", raw_line.strip())
        if not line:
            continue
        headword = _extract_headword(line)
        if headword:
            flush_current()
            current_word = headword
            meaning = _extract_meaning_from_headword_line(line, headword)
            if meaning:
                current_meanings.append(meaning)
            continue
        if not current_word or NOISE_LINE_REGEX.match(line):
            continue
        if not include_continuations:
            continue
        continuation_meaning = _extract_meaning_from_continuation_line(line)
        if continuation_meaning:
            current_meanings.append(continuation_meaning)

    flush_current()
    return entries


def extract_entry_words(lines: Iterable[str]) -> List[str]:
    """Extract only the headwords from dictionary-style OCR lines."""
    entries = extract_vocabulary_entries(lines, include_continuations=False)
    return [entry.word for entry in entries]


def extract_entry_meanings(lines: Iterable[str]) -> List[str]:
    """Extract Chinese meanings aligned to headwords from dictionary-style OCR lines."""
    entries = extract_vocabulary_entries(lines, include_continuations=False)
    return [entry.meaning for entry in entries]


def extract_entry_words_from_positioned_lines(lines: Iterable[OCRLine]) -> List[str]:
    """Extract headwords using OCR line positions to ignore indented example sentences."""
    entries = extract_positioned_vocabulary_entries(lines)
    return [entry.word for entry in entries]


def extract_entry_meanings_from_positioned_lines(lines: Iterable[OCRLine]) -> List[str]:
    """Extract headword meanings using OCR line positions to align dictionary rows."""
    entries = extract_positioned_vocabulary_entries(lines)
    return [entry.meaning for entry in entries]


def extract_positioned_vocabulary_entries(lines: Iterable[OCRLine]) -> List[VocabularyEntry]:
    """Parse dictionary-style rows using OCR layout positions."""
    row_groups = _group_ocr_lines_by_row(lines)
    if not row_groups:
        return []
    candidate_lefts = [row[0].left for row in row_groups if _extract_row_headword(row)]
    if not candidate_lefts:
        return []
    min_left = min(candidate_lefts)
    page_right = max((line.right for row in row_groups for line in row), default=min_left)
    left_tolerance = max(40.0, (page_right - min_left) * 0.1)
    entries: List[VocabularyEntry] = []
    seen_words = set()
    for row in row_groups:
        first_line = row[0]
        if first_line.left > min_left + left_tolerance:
            continue
        headword = _extract_row_headword(row)
        if not headword or headword in seen_words:
            continue
        row_text = " ".join(line.text.strip() for line in sorted(row, key=lambda item: item.left) if line.text.strip())
        meaning = _extract_meaning_from_headword_line(row_text, headword)
        if not meaning:
            continue
        seen_words.add(headword)
        entries.append(VocabularyEntry(word=headword, meaning=meaning))
    return entries


def _normalize_chinese_segment(segment: str) -> str:
    stripped = CHINESE_EDGE_TRIM_REGEX.sub("", segment.strip())
    stripped = SPACE_REGEX.sub(" ", stripped)
    stripped = stripped.replace("(", "").replace(")", "").replace("（", "").replace("）", "")
    return stripped.strip(" ，、；：:()（）《》“”‘’·-")


def _extract_headword(line: str) -> str:
    match = ENTRY_HEADWORD_REGEX.match(line)
    if not match:
        return ""
    word, remainder = match.groups()
    if not remainder:
        return ""
    if "/" not in remainder and not PART_OF_SPEECH_REGEX.search(remainder):
        return ""
    return word.lower()


def _extract_headword_candidate(line: str) -> str:
    match = ENTRY_HEADWORD_REGEX.match(line)
    if not match:
        return ""
    word = match.group(1).lower()
    if len(word) <= 1:
        return ""
    return word


def _extract_row_headword(row: List[OCRLine]) -> str:
    """Find a headword from the left side of a positioned OCR row.

    Azure OCR may split the entry number and the actual word into separate
    line fragments. This helper progressively joins the first few leftmost
    fragments so rows like `1917` + `ideal` still resolve to `ideal`.
    """
    left_sorted = sorted(row, key=lambda item: item.left)
    prefix_parts: List[str] = []
    for index, fragment in enumerate(left_sorted[:4]):
        text = fragment.text.strip()
        if not text:
            continue
        direct = _extract_headword_candidate(text)
        if direct and (index == 0 or not _looks_like_sentence(text)):
            return direct
        prefix_parts.append(text)
        combined = " ".join(prefix_parts)
        combined_candidate = _extract_headword_candidate(combined)
        if combined_candidate and not _looks_like_sentence(combined):
            return combined_candidate
    return ""


def _extract_meaning_from_headword_line(line: str, word: str) -> str:
    stripped = SPACE_REGEX.sub(" ", line)
    stripped = re.sub(r"^\s*\d{1,5}\s+", "", stripped)
    stripped = re.sub(r"^\*?" + re.escape(word) + r"\b", "", stripped, flags=re.IGNORECASE)
    stripped = PHONETIC_REGEX.sub(" ", stripped)
    stripped = PART_OF_SPEECH_REGEX.sub(" ", stripped)
    stripped = SPACE_REGEX.sub(" ", stripped)
    return _normalize_chinese_definition(stripped)


def _extract_meaning_from_continuation_line(line: str) -> str:
    if not ONLY_POS_PREFIX_REGEX.match(line):
        return ""
    if not PART_OF_SPEECH_REGEX.search(line):
        return ""
    stripped = PHONETIC_REGEX.sub(" ", line)
    stripped = PART_OF_SPEECH_REGEX.sub(" ", stripped)
    stripped = SPACE_REGEX.sub(" ", stripped)
    return _normalize_chinese_definition(stripped)


def _normalize_chinese_definition(text: str) -> str:
    chinese_segments = []
    for segment in CHINESE_SEGMENT_REGEX.findall(text):
        normalized = _normalize_chinese_segment(segment)
        if normalized:
            chinese_segments.append(normalized)
    return _merge_meanings(chinese_segments)


def _merge_meanings(items: Iterable[str]) -> str:
    merged: List[str] = []
    seen = set()
    for item in items:
        normalized = SPACE_REGEX.sub(" ", item.strip())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(normalized)
    return "；".join(merged)


def _group_ocr_lines_by_row(lines: Iterable[OCRLine]) -> List[List[OCRLine]]:
    ordered = sorted(lines, key=lambda item: (((item.top + item.bottom) / 2.0), item.left))
    if not ordered:
        return []
    heights = [max(line.bottom - line.top, 1.0) for line in ordered]
    avg_height = sum(heights) / len(heights)
    row_tolerance = max(12.0, avg_height * 0.65)
    rows: List[List[OCRLine]] = []
    row_centers: List[float] = []
    for line in ordered:
        center = (line.top + line.bottom) / 2.0
        if not rows:
            rows.append([line])
            row_centers.append(center)
            continue
        if abs(center - row_centers[-1]) <= row_tolerance:
            rows[-1].append(line)
            row_centers[-1] = sum((item.top + item.bottom) / 2.0 for item in rows[-1]) / len(rows[-1])
        else:
            rows.append([line])
            row_centers.append(center)
    for row in rows:
        row.sort(key=lambda item: item.left)
    return rows


def _looks_like_sentence(text: str) -> bool:
    tokens = [token for token in SPACE_REGEX.split(text.strip()) if token]
    if len(tokens) >= 3:
        return True
    if text.endswith((".", "?", "!")):
        return True
    return False
