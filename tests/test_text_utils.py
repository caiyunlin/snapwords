from app.services.text_utils import clean_and_filter_words

def test_clean_and_filter_words_basic():
    words = ["Apple", "banana", "BANANA", "car", "A", "123", "peel!"]
    assert clean_and_filter_words(words) == ["apple", "banana", "car"]
