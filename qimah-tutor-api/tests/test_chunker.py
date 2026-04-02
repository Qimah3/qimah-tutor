def test_classify_exam():
    from app.indexer.classifier import classify_source
    assert classify_source("Major CS101 251.pdf") == "old_exam"
    assert classify_source("Quiz4_answers.pdf") == "old_exam"
    assert classify_source("midterm-2024.pdf") == "old_exam"


def test_classify_lecture():
    from app.indexer.classifier import classify_source
    assert classify_source("lab6.jpg") == "lecture_note"
    assert classify_source("lecture-notes.pdf") == "lecture_note"


def test_classify_screenshot():
    from app.indexer.classifier import classify_source
    assert classify_source("WhatsApp Image 2025-10-11.jpg") == "screenshot"


def test_classify_handout():
    from app.indexer.classifier import classify_source
    assert classify_source("chapter3.pdf") == "handout"


def test_classify_override():
    from app.indexer.classifier import classify_source
    assert classify_source("lab6.jpg", overrides={"lab6.jpg": "old_exam"}) == "old_exam"


def test_chunking_covers_all_content():
    from app.indexer.chunker import chunk_text
    text = "A" * 1200
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    assert len(chunks) >= 2
    assert all(len(c) > 0 for c in chunks)
    assert all(len(c) <= 500 for c in chunks)


def test_chunking_short_text_single_chunk():
    from app.indexer.chunker import chunk_text
    text = "short text"
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    assert len(chunks) == 1
    assert chunks[0] == "short text"


def test_chunking_overlap_creates_continuity():
    from app.indexer.chunker import chunk_text
    text = " ".join(f"word{i}" for i in range(100))
    chunks = chunk_text(text, chunk_size=200, overlap=50)
    for i in range(len(chunks) - 1):
        tail = chunks[i][-50:]
        assert any(word in chunks[i + 1] for word in tail.split() if word)
