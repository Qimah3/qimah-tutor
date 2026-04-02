import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch


# ── PDF extractor tests ──────────────────────────────────────────────────────

def test_pdf_text_page_returns_pymupdf_segment():
    """Page with enough text → method=pymupdf, no OCR."""
    with patch("fitz.open") as mock_open:
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "A" * 200  # well above threshold
        mock_page.number = 0
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_open.return_value.__enter__ = MagicMock(return_value=mock_doc)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        from app.indexer.pdf_extractor import extract_pdf
        segments = extract_pdf("fake.pdf")

    assert len(segments) == 1
    assert segments[0]["method"] == "pymupdf"
    assert segments[0]["page"] == 0
    assert "A" * 10 in segments[0]["text"]


def test_pdf_scanned_page_triggers_ocr():
    """Page with sparse text (<= threshold) → OCR attempted on embedded images."""
    from app.indexer import pdf_extractor  # ensure imported before patching

    with patch("fitz.open") as mock_open, \
         patch.object(pdf_extractor, "extract_image") as mock_ocr:

        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "tiny"  # below threshold
        mock_page.number = 0
        mock_page.get_images.return_value = [(1, 0, 0, 0, 0, "CS", "Image")]
        mock_doc.extract_image.return_value = {"image": b"fake_image_bytes", "ext": "png"}
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_open.return_value.__enter__ = MagicMock(return_value=mock_doc)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        mock_ocr.return_value = {"text": "OCR result text here", "chars": 20, "confidence": 85.0}

        segments = pdf_extractor.extract_pdf("fake.pdf")

    # OCR segment should be present
    assert len(segments) == 1
    assert segments[0]["method"] == "tesseract"
    assert segments[0]["text"] == "OCR result text here"
    assert mock_ocr.called


def test_pdf_returns_list():
    """extract_pdf always returns a list even for an empty PDF."""
    with patch("fitz.open") as mock_open:
        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        mock_doc.__len__ = MagicMock(return_value=0)
        mock_open.return_value.__enter__ = MagicMock(return_value=mock_doc)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        from app.indexer.pdf_extractor import extract_pdf
        result = extract_pdf("empty.pdf")

    assert isinstance(result, list)


# ── OCR extractor tests ──────────────────────────────────────────────────────

def test_ocr_extract_image_returns_dict():
    with patch("pytesseract.image_to_data") as mock_data, \
         patch("PIL.Image.open") as mock_img:
        mock_img.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_img.return_value.__exit__ = MagicMock(return_value=False)
        mock_data.return_value = {
            "text": ["Hello", "World", "", "Java"],
            "conf": [90, 85, -1, 88],
        }

        from app.indexer.ocr_extractor import extract_image
        result = extract_image("fake.jpg")

    assert "text" in result
    assert "chars" in result
    assert "confidence" in result
    assert result["chars"] >= 0


def test_ocr_filters_empty_words():
    """Empty strings and negative-confidence tokens must not appear in output."""
    with patch("pytesseract.image_to_data") as mock_data, \
         patch("PIL.Image.open") as mock_img:
        mock_img.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_img.return_value.__exit__ = MagicMock(return_value=False)
        mock_data.return_value = {
            "text": ["Hello", "", "", "World"],
            "conf": [90, -1, -1, 88],
        }

        from app.indexer.ocr_extractor import extract_image
        result = extract_image("fake.jpg")

    assert "  " not in result["text"]  # no double spaces from empty tokens
    assert result["text"] == "Hello World"


# ── DOCX extractor tests ──────────────────────────────────────────────────────

def test_docx_extract_joins_paragraphs():
    with patch("docx.Document") as mock_doc_cls:
        mock_doc = MagicMock()
        mock_para1 = MagicMock()
        mock_para1.text = "First paragraph."
        mock_para2 = MagicMock()
        mock_para2.text = ""  # empty, should be skipped
        mock_para3 = MagicMock()
        mock_para3.text = "Third paragraph."
        mock_doc.paragraphs = [mock_para1, mock_para2, mock_para3]
        mock_doc_cls.return_value = mock_doc

        from app.indexer.docx_extractor import extract_docx
        result = extract_docx("fake.docx")

    assert "First paragraph." in result["text"]
    assert "Third paragraph." in result["text"]
    assert result["chars"] > 0


def test_docx_skips_empty_paragraphs():
    with patch("docx.Document") as mock_doc_cls:
        mock_doc = MagicMock()
        p1 = MagicMock()
        p1.text = "Real content here."
        p2 = MagicMock()
        p2.text = "   "  # whitespace only
        p3 = MagicMock()
        p3.text = ""
        mock_doc.paragraphs = [p1, p2, p3]
        mock_doc_cls.return_value = mock_doc

        from app.indexer.docx_extractor import extract_docx
        result = extract_docx("fake.docx")

    assert result["text"].strip() == "Real content here."
    assert result["chars"] == len(result["text"])
