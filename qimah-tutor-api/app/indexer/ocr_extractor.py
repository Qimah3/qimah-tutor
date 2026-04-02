import os

import pytesseract
from PIL import Image

# Allow overriding tesseract binary path via env var (useful on Windows or custom installs)
pytesseract.pytesseract.tesseract_cmd = os.environ.get("TESSERACT_CMD", "tesseract")


def extract_image(path: str) -> dict:
    """Run OCR on an image file using Tesseract (eng+ara).

    Returns:
        {"text": str, "chars": int, "confidence": float}
    """
    with Image.open(path) as img:
        data = pytesseract.image_to_data(
            img,
            lang="eng+ara",
            output_type=pytesseract.Output.DICT,
        )

    words = []
    confidences = []
    for word, conf in zip(data["text"], data["conf"]):
        if word.strip() and int(conf) > 0:
            words.append(word)
            confidences.append(float(conf))

    text = " ".join(words)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return {"text": text, "chars": len(text), "confidence": avg_confidence}
