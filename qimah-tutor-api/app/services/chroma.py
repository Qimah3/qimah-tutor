"""ChromaDB singleton wrapper with lazy init (L003)."""

import chromadb

_client: chromadb.ClientAPI | None = None


def get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.Client()
    return _client


def get_collection(course_id: int, topic_id: int) -> chromadb.Collection:
    return get_client().get_or_create_collection(
        name=f"course_{course_id}_topic_{topic_id}"
    )
