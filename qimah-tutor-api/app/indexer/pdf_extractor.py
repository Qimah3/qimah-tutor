import os
import tempfile

import fitz  # PyMuPDF

from app.indexer.ocr_extractor import extract_image

_SCANNED_PAGE_THRESHOLD = 50  # chars below which a page is treated as scanned


def extract_pdf(path: str, threshold: int = _SCANNED_PAGE_THRESHOLD) -> list[dict]:
    """Extract text from a PDF, falling back to OCR for scanned pages.

    For each page:
      - If get_text() returns more than `threshold` chars → pymupdf segment
      - Otherwise → extract embedded images and OCR each one

    Returns:
        list of {"text": str, "page": int, "method": str, "ocr_confidence": float}
    """
    segments = []

    with fitz.open(path) as doc:
        for page in doc:
            page_text = page.get_text()

            if len(page_text) > threshold:
                segments.append({
                    "text": page_text,
                    "page": page.number,
                    "method": "pymupdf",
                    "ocr_confidence": 100.0,
                })
            else:
                # Scanned page — OCR each embedded image
                for img_info in page.get_images(full=True):
                    xref = img_info[0]
                    img_data = doc.extract_image(xref)
                    ext = img_data.get("ext", "png")

                    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                        tmp.write(img_data["image"])
                        tmp_path = tmp.name

                    try:
                        result = extract_image(tmp_path)
                        if result["text"].strip():
                            segments.append({
                                "text": result["text"],
                                "page": page.number,
                                "method": "tesseract",
                                "ocr_confidence": result["confidence"],
                            })
                    finally:
                        os.unlink(tmp_path)

    return segments
