import os

import chromadb

TEST_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "test drive")


def test_index_local_folder():
    from app.indexer.index_runner import index_local_folder

    client = chromadb.Client()
    collection = index_local_folder(TEST_DIR, "cs101_test", client)
    assert collection.count() > 30
    result = collection.get(limit=1, include=["metadatas"])
    meta = result["metadatas"][0]
    assert "source_file" in meta
    assert "source_type" in meta
    assert "extraction_method" in meta
    assert "page_number" in meta
    assert "text_length" in meta
    assert "ocr_confidence" in meta
    assert "indexed_at" in meta
