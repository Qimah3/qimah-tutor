import os
import uuid
from datetime import datetime, timezone

from app.indexer.chunker import chunk_text
from app.indexer.classifier import classify_source
from app.indexer.docx_extractor import extract_docx
from app.indexer.ocr_extractor import extract_image
from app.indexer.pdf_extractor import extract_pdf


def index_local_folder(folder_path: str, collection_name: str, client) -> object:
    """Index all supported files in folder_path into a ChromaDB collection.

    Routes each file by extension:
      .pdf              → extract_pdf  (returns list of page segments)
      .jpg/.jpeg/.png   → extract_image (returns single OCR result dict)
      .docx             → extract_docx  (returns single text dict)

    Each chunk is stored with metadata:
      source_file, page_number, source_type, extraction_method,
      text_length, ocr_confidence, indexed_at

    Returns the ChromaDB collection.
    """
    collection = client.get_or_create_collection(collection_name)
    indexed_at = datetime.now(timezone.utc).isoformat()

    documents: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    if not os.path.isdir(folder_path):
        raise ValueError(f"index_local_folder: path does not exist or is not a directory: {folder_path!r}")

    for filename in sorted(os.listdir(folder_path)):
        filepath = os.path.join(folder_path, filename)
        if not os.path.isfile(filepath):
            continue

        ext = os.path.splitext(filename)[1].lower()
        source_type = classify_source(filename)

        if ext == ".pdf":
            segments = extract_pdf(filepath)
            for seg in segments:
                for chunk in chunk_text(seg["text"]):
                    if not chunk.strip():
                        continue
                    documents.append(chunk)
                    metadatas.append({
                        "source_file": filename,
                        "page_number": int(seg["page"]),
                        "source_type": source_type,
                        "extraction_method": seg["method"],
                        "text_length": len(chunk),
                        "ocr_confidence": float(seg.get("ocr_confidence") or 0.0),
                        "indexed_at": indexed_at,
                    })
                    ids.append(str(uuid.uuid4()))

        elif ext in (".jpg", ".jpeg", ".png"):
            try:
                result = extract_image(filepath)
            except Exception as exc:
                print(f"[index_runner] Skipping {filename}: OCR failed ({exc})")
                continue
            for chunk in chunk_text(result["text"]):
                if not chunk.strip():
                    continue
                documents.append(chunk)
                metadatas.append({
                    "source_file": filename,
                    "page_number": 0,
                    "source_type": source_type,
                    "extraction_method": "tesseract",
                    "text_length": len(chunk),
                    "ocr_confidence": float(result.get("confidence") or 0.0),
                    "indexed_at": indexed_at,
                })
                ids.append(str(uuid.uuid4()))

        elif ext == ".docx":
            result = extract_docx(filepath)
            for chunk in chunk_text(result["text"]):
                if not chunk.strip():
                    continue
                documents.append(chunk)
                metadatas.append({
                    "source_file": filename,
                    "page_number": 0,
                    "source_type": source_type,
                    "extraction_method": "python-docx",
                    "text_length": len(chunk),
                    "ocr_confidence": 0.0,
                    "indexed_at": indexed_at,
                })
                ids.append(str(uuid.uuid4()))

    if documents:
        collection.add(documents=documents, metadatas=metadatas, ids=ids)

    return collection


def index_from_drive(course_config: dict, client) -> None:
    """Stub: will index files from Google Drive once drive_client.py is implemented."""
    return None
