"""Basic tests for text_processor."""

from text_processor import chunk_for_tts, detect_language, fix_spacing, process_book, strip_ocr_noise


def test_fix_spacing():
    assert fix_spacing("h e l l o world") == "hello world"


def test_strip_page_numbers():
    text = "Page 1\n\nHello world\n\n- 2 -"
    cleaned = strip_ocr_noise(text)
    assert "Hello world" in cleaned
    assert "Page 1" not in cleaned


def test_chunk_for_tts():
    text = "Short."
    assert chunk_for_tts(text) == ["Short."]
    long_text = "Word. " * 80
    chunks = chunk_for_tts(long_text, min_chars=50, max_chars=100)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)


def test_process_book_chapters():
    text = "CHAPTER 1\n\nFirst.\n\nCHAPTER 2\n\nSecond."
    chapters = process_book(text)
    assert len(chapters) == 2
    assert chapters[0]["title"] == "CHAPTER 1"
    assert "chunks" in chapters[0]


def test_detect_language():
    assert detect_language("The quick brown fox") == "en"
    assert detect_language("El gato está en la casa") == "es"
