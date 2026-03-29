"""Layout-aware helpers for dictionary-style OCR pages."""
from __future__ import annotations

import io
from statistics import mean
from typing import Iterable, List

from PIL import Image

from app.services.azure_ocr import OCRLine


def filter_lines_on_gray_bands(image_bytes: bytes, lines: Iterable[OCRLine]) -> List[OCRLine]:
    """Return OCR lines that appear on gray dictionary entry bands.

    Many vocabulary books place the headword/phonetic/meaning row on a light gray
    strip, while example sentences remain on a white background. This helper
    samples full-width horizontal bands to keep only the gray-strip rows.
    """
    line_list = [line for line in lines if line.text.strip()]
    if not line_list:
        return []

    with Image.open(io.BytesIO(image_bytes)) as image:
        grayscale = image.convert("L")
        width, height = grayscale.size
        rows = _group_lines_by_row(line_list)
        if not rows:
            return []

        gray_rows: List[List[OCRLine]] = []
        for row in rows:
            if _row_has_gray_background(grayscale, row, width, height):
                gray_rows.append(row)

    selected = [line for row in gray_rows for line in row]
    if len(selected) >= max(3, len(line_list) // 8):
        return selected
    return []


def _group_lines_by_row(lines: List[OCRLine]) -> List[List[OCRLine]]:
    ordered = sorted(lines, key=lambda item: (((item.top + item.bottom) / 2.0), item.left))
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


def _row_has_gray_background(image: Image.Image, row: List[OCRLine], width: int, height: int) -> bool:
    top = max(0, int(min(line.top for line in row) - 2))
    bottom = min(height, int(max(line.bottom for line in row) + 2))
    row_height = max(bottom - top, 1)
    left = max(0, int(width * 0.05))
    right = min(width, int(width * 0.95))
    band_mean = _band_mean(image, left, top, right, bottom)
    if band_mean <= 0:
        return False

    gap = max(row_height, int(row_height * 0.8))
    above_top = max(0, top - gap - row_height)
    above_bottom = max(0, top - gap)
    below_top = min(height, bottom + gap)
    below_bottom = min(height, bottom + gap + row_height)

    surroundings = []
    if above_bottom > above_top:
        surroundings.append(_band_mean(image, left, above_top, right, above_bottom))
    if below_bottom > below_top:
        surroundings.append(_band_mean(image, left, below_top, right, below_bottom))
    if not surroundings:
        return False

    surrounding_mean = mean(surroundings)
    darkness_delta = surrounding_mean - band_mean
    return darkness_delta >= 7.5 and band_mean <= 242


def _band_mean(image: Image.Image, left: int, top: int, right: int, bottom: int) -> float:
    if right <= left or bottom <= top:
        return 0.0
    crop = image.crop((left, top, right, bottom))
    histogram = crop.histogram()
    total_pixels = sum(histogram)
    if total_pixels == 0:
        return 0.0
    weighted = sum(index * count for index, count in enumerate(histogram))
    return weighted / total_pixels