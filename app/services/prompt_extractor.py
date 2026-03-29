"""Prompt-based OCR post-processing helpers."""
from __future__ import annotations

import json
import os
from typing import List

import httpx

from app.services.azure_ocr import OCRLine
from app.services.text_utils import clean_and_filter_words, extract_chinese_explanations, extract_entry_meanings, extract_entry_meanings_from_positioned_lines, extract_entry_words, extract_entry_words_from_positioned_lines

PROMPT_TEMPLATE_1 = "请按词典词条提取英文单词词头，只保留词条行中的主单词。忽略序号、音标、词性、中文释义、白底区域中的英文例句、词组、辨析和其他无关内容。输出去重后的结果，每行一个。"
PROMPT_TEMPLATE_2 = "请按词典词条提取中文释义，只保留词条行中的中文释义，如果同一词条的中文释义有多个，可以一起跟上。忽略序号、音标、词性、白底区域中的英文例句、词组、辨析和其他无关内容。输出去重后的结果，每行一个。"

PROMPT_TEMPLATES = {
    "template_1": PROMPT_TEMPLATE_1,
    "template_2": PROMPT_TEMPLATE_2,
    "custom": "",
}


class PromptExtractionError(RuntimeError):
    """Raised when OCR prompt extraction fails."""


class PromptExtractionConfigError(PromptExtractionError):
    """Raised when prompt extraction requires model config that is missing."""


def get_prompt_templates() -> dict[str, str]:
    """Return built-in prompt templates exposed to the UI."""
    return PROMPT_TEMPLATES.copy()


def resolve_prompt(template_id: str | None, prompt_text: str | None) -> tuple[str, str]:
    """Resolve selected template and the effective prompt text."""
    normalized_template = (template_id or "template_1").strip()
    if normalized_template not in PROMPT_TEMPLATES:
        normalized_template = "custom"
    effective_prompt = (prompt_text or "").strip()
    if not effective_prompt and normalized_template in ("template_1", "template_2"):
        effective_prompt = PROMPT_TEMPLATES[normalized_template]
    return normalized_template, effective_prompt


async def extract_items_from_ocr(
    *,
    image_bytes: bytes | None,
    ocr_lines: List[str],
    ocr_words: List[str],
    ocr_line_details: List[OCRLine] | None,
    template_id: str | None,
    prompt_text: str | None,
) -> List[str]:
    """Extract target content from OCR result using built-in templates or a model-backed custom prompt."""
    normalized_template, effective_prompt = resolve_prompt(template_id, prompt_text)
    if normalized_template == "template_1" and _is_builtin_prompt(normalized_template, prompt_text):
        entry_words = extract_entry_words_from_positioned_lines(ocr_line_details or []) or extract_entry_words(ocr_lines)
        return entry_words or clean_and_filter_words(ocr_words)
    if normalized_template == "template_2" and _is_builtin_prompt(normalized_template, prompt_text):
        entry_meanings = extract_entry_meanings_from_positioned_lines(ocr_line_details or []) or extract_entry_meanings(ocr_lines)
        return entry_meanings or extract_chinese_explanations(ocr_lines)
    if normalized_template == "custom" and not effective_prompt:
        raise PromptExtractionError("请输入自定义提示词后再上传提取")
    if not _is_model_configured():
        if normalized_template == "template_1":
            entry_words = extract_entry_words_from_positioned_lines(ocr_line_details or []) or extract_entry_words(ocr_lines)
            return entry_words or clean_and_filter_words(ocr_words)
        if normalized_template == "template_2":
            entry_meanings = extract_entry_meanings_from_positioned_lines(ocr_line_details or []) or extract_entry_meanings(ocr_lines)
            return entry_meanings or extract_chinese_explanations(ocr_lines)
        raise PromptExtractionConfigError(
            "当前未配置自定义提示词所需的模型服务。请先配置 AZURE_OPENAI_ENDPOINT、AZURE_OPENAI_KEY 和 AZURE_OPENAI_DEPLOYMENT。"
        )
    return await _extract_items_with_model(ocr_lines, effective_prompt)


def _is_builtin_prompt(template_id: str, prompt_text: str | None) -> bool:
    expected = PROMPT_TEMPLATES.get(template_id, "")
    actual = (prompt_text or "").strip()
    return not actual or actual == expected


def _is_model_configured() -> bool:
    return all(
        [
            os.getenv("AZURE_OPENAI_ENDPOINT"),
            os.getenv("AZURE_OPENAI_KEY"),
            os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        ]
    )


async def _extract_items_with_model(ocr_lines: List[str], prompt_text: str) -> List[str]:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    api_key = os.getenv("AZURE_OPENAI_KEY", "")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一个 OCR 提取助手。你必须严格按照用户提示词处理 OCR 文本，"
                    "并仅返回 JSON，格式为 {\"items\": [\"内容1\", \"内容2\"]}。"
                    "不要输出解释、Markdown 或额外字段。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户提示词：\n{prompt_text}\n\n"
                    "以下是 OCR 识别出的原始文本，请仅根据上面的提示词提取内容：\n"
                    + "\n".join(ocr_lines)
                ),
            },
        ],
        "temperature": 0.1,
        "max_tokens": 800,
        "response_format": {"type": "json_object"},
    }
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)
    if response.status_code >= 400:
        body = response.text[:300]
        raise PromptExtractionError(f"提示词提取请求失败 {response.status_code}: {body}")
    content = (
        response.json()
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    items = _parse_model_items(content)
    if not items:
        raise PromptExtractionError("提示词提取未返回有效内容")
    return items


def _parse_model_items(content: str) -> List[str]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise PromptExtractionError("模型返回的结果不是有效 JSON") from exc
    raw_items = data.get("items")
    if not isinstance(raw_items, list):
        raise PromptExtractionError("模型返回结果缺少 items 数组")
    normalized: List[str] = []
    seen = set()
    for item in raw_items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized