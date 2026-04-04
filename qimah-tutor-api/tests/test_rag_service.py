"""Tests for RAG service — Task 9."""
import os

import chromadb
import pytest


TEST_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "test drive")

RAG_CONFIG = {
    "initial_candidates": 15,
    "final_top_k": 5,
    "ocr_confidence_min": 60,
    "ocr_text_length_min": 100,
    "weak_threshold": 1.3,
    "min_grounding_chunks": 3,
    "source_weights": {
        "old_exam": 1.5,
        "lecture_note": 1.2,
        "handout": 1.0,
        "screenshot": 0.8,
    },
}


@pytest.fixture(scope="module")
def rag_collection():
    """Build a ChromaDB collection from test drive fixtures (once per module)."""
    from app.indexer.index_runner import index_local_folder
    client = chromadb.Client()
    collection = index_local_folder(TEST_DIR, "cs101_rag_test", client)
    return collection


def test_retrieve_relevant_chunks(rag_collection):
    from app.services.rag_service import retrieve
    result = retrieve("What does indexOf() do in Java?", rag_collection, config=RAG_CONFIG)
    assert len(result["chunks"]) <= 5
    assert len(result["chunks"]) > 0
    assert result["grounding_level"] in ("high", "medium", "low")


def test_weak_retrieval_detected(rag_collection):
    from app.services.rag_service import retrieve
    result = retrieve("quantum entanglement in physics", rag_collection, config=RAG_CONFIG)
    assert result["grounding_level"] in ("low", "medium")


def test_chunk_dict_shape(rag_collection):
    from app.services.rag_service import retrieve
    result = retrieve("Java arrays", rag_collection, config=RAG_CONFIG)
    expected_keys = {"text", "source_file", "page_number", "source_type", "score"}
    for chunk in result["chunks"]:
        assert set(chunk.keys()) == expected_keys


def test_chunks_sorted_by_score_descending(rag_collection):
    from app.services.rag_service import retrieve
    result = retrieve("Java arrays", rag_collection, config=RAG_CONFIG)
    scores = [c["score"] for c in result["chunks"]]
    assert scores == sorted(scores, reverse=True)


def test_grounding_summary_present(rag_collection):
    from app.services.rag_service import retrieve
    result = retrieve("Java variables", rag_collection, config=RAG_CONFIG)
    assert isinstance(result["grounding_summary"], str)
    assert len(result["grounding_summary"]) > 0


def test_result_keys(rag_collection):
    from app.services.rag_service import retrieve
    result = retrieve("loops in Java", rag_collection, config=RAG_CONFIG)
    assert set(result.keys()) == {"chunks", "grounding_level", "grounding_summary"}


def test_final_top_k_respected(rag_collection):
    from app.services.rag_service import retrieve
    config = {**RAG_CONFIG, "final_top_k": 2}
    result = retrieve("Java methods", rag_collection, config=config)
    assert len(result["chunks"]) <= 2


def test_source_type_in_chunks_is_valid(rag_collection):
    from app.services.rag_service import retrieve
    valid_types = {"old_exam", "lecture_note", "handout", "screenshot"}
    result = retrieve("data structures", rag_collection, config=RAG_CONFIG)
    for chunk in result["chunks"]:
        assert chunk["source_type"] in valid_types


def test_empty_collection_returns_low_grounding():
    from app.services.rag_service import retrieve
    client = chromadb.Client()
    empty_col = client.get_or_create_collection("empty_test")
    result = retrieve("anything", empty_col, config=RAG_CONFIG)
    assert result["grounding_level"] == "low"
    assert result["chunks"] == []
    assert isinstance(result["grounding_summary"], str)


def test_score_is_positive_float(rag_collection):
    from app.services.rag_service import retrieve
    result = retrieve("Java programming", rag_collection, config=RAG_CONFIG)
    for chunk in result["chunks"]:
        assert isinstance(chunk["score"], float)
        assert chunk["score"] > 0


def test_page_number_is_int(rag_collection):
    from app.services.rag_service import retrieve
    result = retrieve("Java classes", rag_collection, config=RAG_CONFIG)
    for chunk in result["chunks"]:
        assert isinstance(chunk["page_number"], int)
