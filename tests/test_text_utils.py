import asyncio

from app.services.azure_ocr import OCRLine
from app.services.prompt_extractor import PromptExtractionConfigError, extract_items_from_ocr, resolve_prompt
from app.services.text_utils import clean_and_filter_words, extract_chinese_explanations, extract_entry_meanings, extract_entry_meanings_from_positioned_lines, extract_entry_words, extract_entry_words_from_positioned_lines

def test_clean_and_filter_words_basic():
    words = ["Apple", "banana", "BANANA", "car", "A", "123", "peel!"]
    assert clean_and_filter_words(words) == ["apple", "banana", "car"]


def test_extract_chinese_explanations_basic():
    lines = [
        "abandon 放弃；抛弃",
        "ability 能力；才能",
        "This is an example line.",
    ]
    assert extract_chinese_explanations(lines) == ["放弃；抛弃", "能力；才能"]


def test_extract_entry_words_ignores_example_sentences():
    lines = [
        "1917 ideal /ai'dial/ adj. 理想的；完美的",
        "n. 理想；努力目标",
        "This dictionary is ideal - it's exactly what I need.",
        "1918 identical /ai'dentikal/ adj. 同一的；（完全）相同的",
        "Our opinions are identical.",
    ]
    assert extract_entry_words(lines) == ["ideal", "identical"]


def test_extract_entry_words_from_positioned_lines_ignores_indented_examples():
    lines = [
        OCRLine(text="1917 ideal", left=20, top=10, right=120, bottom=28),
        OCRLine(text="/ai'dial/ adj. 理想的；完美的", left=150, top=10, right=420, bottom=28),
        OCRLine(text="This dictionary is ideal", left=90, top=36, right=360, bottom=52),
        OCRLine(text="1918 identical", left=20, top=70, right=150, bottom=88),
        OCRLine(text="/ai'dentikal/ adj. 同一的；完全相同的", left=150, top=70, right=450, bottom=88),
        OCRLine(text="Our opinions are identical.", left=96, top=96, right=380, bottom=114),
    ]
    assert extract_entry_words_from_positioned_lines(lines) == ["ideal", "identical"]


def test_extract_entry_words_from_positioned_lines_handles_split_number_and_word():
    lines = [
        OCRLine(text="1917", left=20, top=10, right=50, bottom=28),
        OCRLine(text="ideal", left=62, top=10, right=120, bottom=28),
        OCRLine(text="/ai'dial/ adj. 理想的；完美的", left=150, top=10, right=420, bottom=28),
        OCRLine(text="This dictionary is ideal", left=92, top=36, right=360, bottom=52),
        OCRLine(text="1918", left=20, top=70, right=50, bottom=88),
        OCRLine(text="identical", left=62, top=70, right=145, bottom=88),
        OCRLine(text="/ai'dentikal/ adj. 同一的；完全相同的", left=150, top=70, right=450, bottom=88),
    ]
    assert extract_entry_words_from_positioned_lines(lines) == ["ideal", "identical"]


def test_extract_entry_meanings_from_positioned_lines_aligns_meanings():
    lines = [
        OCRLine(text="1917 ideal", left=20, top=10, right=120, bottom=28),
        OCRLine(text="/ai'dial/ adj. 理想的；完美的", left=150, top=10, right=420, bottom=28),
        OCRLine(text="This dictionary is ideal", left=90, top=36, right=360, bottom=52),
        OCRLine(text="1918 identical", left=20, top=70, right=150, bottom=88),
        OCRLine(text="/ai'dentikal/ adj. 同一的；完全相同的", left=150, top=70, right=450, bottom=88),
    ]
    assert extract_entry_meanings_from_positioned_lines(lines) == ["理想的；完美的", "同一的；完全相同的"]


def test_extract_entry_meanings_merges_same_entry_meaning():
    lines = [
        "1917 ideal /ai'dial/ adj. 理想的；完美的",
        "n. 理想；努力目标",
        "This dictionary is ideal - it's exactly what I need.",
        "这本词典很理想，正是我所需要的。",
        "1918 identical /ai'dentikal/ adj. 同一的；（完全）相同的",
    ]
    assert extract_entry_meanings(lines) == ["理想的；完美的", "同一的；完全相同的"]


def test_template_2_uses_entry_meanings_for_dictionary_pages():
    async def run_test():
        return await extract_items_from_ocr(
            image_bytes=None,
            ocr_lines=[
                "1917 ideal /ai'dial/ adj. 理想的；完美的",
                "n. 理想；努力目标",
                "1918 identical /ai'dentikal/ adj. 同一的；（完全）相同的",
                "Our opinions are identical.",
            ],
            ocr_words=["ideal", "identical", "our", "opinions"],
            ocr_line_details=None,
            template_id="template_2",
            prompt_text="",
        )

    assert asyncio.run(run_test()) == ["理想的；完美的", "同一的；完全相同的"]


def test_resolve_prompt_uses_builtin_template_when_empty():
    template_id, prompt_text = resolve_prompt("template_1", "")
    assert template_id == "template_1"
    assert "英文单词" in prompt_text


def test_template_1_prefers_positioned_lines_over_raw_words():
    async def run_test():
        return await extract_items_from_ocr(
            image_bytes=None,
            ocr_lines=[
                "1917 ideal /ai'dial/ adj. 理想的；完美的",
                "This dictionary is ideal",
            ],
            ocr_words=["ideal", "this", "dictionary", "is", "ideal"],
            ocr_line_details=[
                OCRLine(text="1917 ideal", left=20, top=10, right=120, bottom=28),
                OCRLine(text="/ai'dial/ adj. 理想的；完美的", left=150, top=10, right=420, bottom=28),
                OCRLine(text="This dictionary is ideal", left=90, top=36, right=360, bottom=52),
            ],
            template_id="template_1",
            prompt_text="",
        )

    assert asyncio.run(run_test()) == ["ideal"]


def test_custom_prompt_requires_model_config(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)

    async def run_test():
        await extract_items_from_ocr(
            image_bytes=None,
            ocr_lines=["abandon 放弃；抛弃"],
            ocr_words=["abandon", "放弃"],
            ocr_line_details=None,
            template_id="custom",
            prompt_text="请只提取例句",
        )

    try:
        asyncio.run(run_test())
        assert False, "Expected PromptExtractionConfigError"
    except PromptExtractionConfigError as exc:
        assert "AZURE_OPENAI_ENDPOINT" in str(exc)
