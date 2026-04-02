import docx


def extract_docx(path: str) -> dict:
    """Extract text from a DOCX file by joining non-empty paragraphs.

    Returns:
        {"text": str, "chars": int}
    """
    doc = docx.Document(path)
    lines = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(lines)
    return {"text": text, "chars": len(text)}
