"""Hybrid RAG retrieval with 6-stage reranking pipeline."""
import logging

import chromadb

logger = logging.getLogger(__name__)

_LOW_RESULT = {
    "chunks": [],
    "grounding_level": "low",
    "grounding_summary": "No relevant source material found",
}


def retrieve(query: str, collection: chromadb.Collection, config: dict) -> dict:
    """Retrieve and rerank chunks from a ChromaDB collection.

    6-stage pipeline:
      1. Vector search (initial candidates)
      2. Keyword boost (query term overlap)
      3. Quality filter (OCR confidence + text length)
      4. Source type weighting
      5. Top-K selection by combined score
      6. Grounding level assessment

    Returns dict with keys: chunks, grounding_level, grounding_summary.
    """
    # --- Stage 1: Retrieve initial candidates via ChromaDB vector search ---
    try:
        results = collection.query(
            query_texts=[query],
            n_results=config["initial_candidates"],
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        logger.error("ChromaDB query failed: %s", exc)
        return dict(_LOW_RESULT)

    # Guard against empty results (L001: guard every [0] access)
    if not results["documents"] or not results["documents"][0]:
        return dict(_LOW_RESULT)

    documents = results["documents"][0]
    distances = results["distances"][0]
    metadatas = results["metadatas"][0]

    # Build candidate list
    candidates = []
    for doc, dist, meta in zip(documents, distances, metadatas):
        candidates.append({
            "text": doc,
            "distance": dist,
            "similarity": 1.0 / (1.0 + dist),
            "source_file": meta["source_file"],
            "page_number": int(meta["page_number"]),
            "source_type": meta["source_type"],
            "ocr_confidence": float(meta.get("ocr_confidence", 0.0)),
            "text_length": int(meta.get("text_length", 0)),
            "extraction_method": meta.get("extraction_method", ""),
        })

    # --- Stage 2: Keyword boost (topic term overlap) ---
    query_terms = set(query.lower().split())
    for candidate in candidates:
        text_lower = candidate["text"].lower()
        matches = sum(1 for term in query_terms if term in text_lower)
        candidate["keyword_boost"] = matches * 0.1

    # --- Stage 3: Quality filter (OCR confidence + text length) ---
    filtered = []
    for c in candidates:
        if c["extraction_method"] == "tesseract":
            if (c["ocr_confidence"] < config["ocr_confidence_min"]
                    or c["text_length"] < config["ocr_text_length_min"]):
                continue
        filtered.append(c)
    candidates = filtered

    if not candidates:
        return dict(_LOW_RESULT)

    # --- Stage 4: Source type weighting ---
    source_weights = config["source_weights"]
    for c in candidates:
        weight = source_weights.get(c["source_type"], 1.0)
        c["combined_score"] = (c["similarity"] + c["keyword_boost"]) * weight

    # --- Stage 5: Select top K by combined score ---
    candidates.sort(key=lambda c: c["combined_score"], reverse=True)
    top_k = candidates[:config["final_top_k"]]

    # --- Stage 6: Assess grounding level ---
    # L002: "best distance > threshold" means >, not >=
    best_distance = min(c["distance"] for c in top_k)  # safe: top_k is non-empty here

    if best_distance > config["weak_threshold"] or len(top_k) == 0:
        grounding_level = "low"
    elif len(top_k) < config["min_grounding_chunks"]:
        grounding_level = "medium"
    else:
        grounding_level = "high"

    # Build grounding summary
    if grounding_level == "low":
        grounding_summary = "No relevant source material found"
    else:
        source_files = list(dict.fromkeys(c["source_file"] for c in top_k))
        count = len(source_files)
        if count == 1:
            grounding_summary = f"Based on {count} source document: {source_files[0]}"
        else:
            grounding_summary = f"Based on {count} source documents including {source_files[0]}"

    # Build return value (L004: consistent chunk shape)
    chunks = [
        {
            "text": c["text"],
            "source_file": c["source_file"],
            "page_number": c["page_number"],
            "source_type": c["source_type"],
            "score": round(c["combined_score"], 4),
        }
        for c in top_k
    ]

    return {
        "chunks": chunks,
        "grounding_level": grounding_level,
        "grounding_summary": grounding_summary,
    }
