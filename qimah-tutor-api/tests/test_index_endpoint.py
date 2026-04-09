"""Tests for POST /index endpoint — Drive-backed course content indexing."""

import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SECRET = "test-secret-key"


# --- Helpers (same HMAC pattern as test_generate.py) ---


def _sign_request(body_dict, secret=SECRET):
    body_bytes = json.dumps(body_dict).encode()
    ts = str(int(time.time()))
    nonce = str(uuid.uuid4())
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    sig = hmac.new(
        secret.encode(), (ts + nonce + body_hash).encode(), hashlib.sha256
    ).hexdigest()
    headers = {
        "X-Signature": sig,
        "X-Timestamp": ts,
        "X-Nonce": nonce,
        "Content-Type": "application/json",
    }
    return body_bytes, headers


def _make_index_body(course_id=1, topic_id=10, folder_id="folder_abc123"):
    return {
        "course_id": course_id,
        "topic_id": topic_id,
        "drive_folder_id": folder_id,
    }


def _mock_drive_class(files, download_side_effect=None):
    """Return a mock *class* whose instances have list_files / download_file."""
    instance = MagicMock()
    instance.list_files.return_value = files
    if download_side_effect is not None:
        instance.download_file.side_effect = download_side_effect
    else:
        instance.download_file.return_value = True
    cls = MagicMock(return_value=instance)
    return cls


# --- Tests ---


def test_index_happy_path():
    """Mock Drive returns 2 files (1 PDF, 1 DOCX) -> 200, indexed==2."""
    files = [
        {"id": "pdf1", "name": "midterm_2024.pdf"},
        {"id": "docx1", "name": "lecture_notes.docx"},
    ]
    drive_cls = _mock_drive_class(files)
    mock_collection = MagicMock()

    pdf_segments = [{"text": "A" * 100, "page": 1, "method": "pdfplumber"}]
    docx_result = {"text": "B" * 100}

    body = _make_index_body()
    body_bytes, headers = _sign_request(body)

    with (
        patch("app.routers.index.DriveClient", drive_cls),
        patch("app.routers.index.get_collection", return_value=mock_collection),
        patch("app.routers.index.extract_pdf", return_value=pdf_segments),
        patch("app.routers.index.extract_docx", return_value=docx_result),
        patch.dict(os.environ, {"HMAC_SECRET": SECRET}),
    ):
        resp = client.post("/index", content=body_bytes, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["indexed"] == 2
    assert data["skipped"] == 0
    assert data["collection"] == "course_1_topic_10"
    # One upsert call per successfully-indexed file
    assert mock_collection.upsert.call_count == 2


def test_index_auth_failure():
    """Bad signature -> 401."""
    body = _make_index_body()
    body_bytes = json.dumps(body).encode()
    headers = {
        "X-Signature": "bad",
        "X-Timestamp": str(int(time.time())),
        "X-Nonce": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }
    with patch.dict(os.environ, {"HMAC_SECRET": SECRET}):
        resp = client.post("/index", content=body_bytes, headers=headers)
    assert resp.status_code == 401


def test_index_drive_list_failure():
    """list_files raises -> 500."""
    instance = MagicMock()
    instance.list_files.side_effect = RuntimeError("Drive API down")
    drive_cls = MagicMock(return_value=instance)

    body = _make_index_body()
    body_bytes, headers = _sign_request(body)

    with (
        patch("app.routers.index.DriveClient", drive_cls),
        patch.dict(os.environ, {"HMAC_SECRET": SECRET}),
    ):
        resp = client.post("/index", content=body_bytes, headers=headers)
    assert resp.status_code == 500


def test_index_skips_failed_download():
    """First file download raises, second succeeds -> indexed==1, skipped==1."""
    files = [
        {"id": "bad_file", "name": "broken.pdf"},
        {"id": "good_file", "name": "lecture_notes.docx"},
    ]
    drive_cls = _mock_drive_class(
        files,
        download_side_effect=[RuntimeError("network timeout"), True],
    )
    mock_collection = MagicMock()
    docx_result = {"text": "C" * 100}

    body = _make_index_body()
    body_bytes, headers = _sign_request(body)

    with (
        patch("app.routers.index.DriveClient", drive_cls),
        patch("app.routers.index.get_collection", return_value=mock_collection),
        patch("app.routers.index.extract_docx", return_value=docx_result),
        patch.dict(os.environ, {"HMAC_SECRET": SECRET}),
    ):
        resp = client.post("/index", content=body_bytes, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["indexed"] == 1
    assert data["skipped"] == 1
    assert mock_collection.upsert.call_count == 1


def test_index_empty_folder():
    """Drive returns empty list -> 200, indexed==0, skipped==0."""
    drive_cls = _mock_drive_class([])
    mock_collection = MagicMock()

    body = _make_index_body()
    body_bytes, headers = _sign_request(body)

    with (
        patch("app.routers.index.DriveClient", drive_cls),
        patch("app.routers.index.get_collection", return_value=mock_collection),
        patch.dict(os.environ, {"HMAC_SECRET": SECRET}),
    ):
        resp = client.post("/index", content=body_bytes, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["indexed"] == 0
    assert data["skipped"] == 0
    mock_collection.upsert.assert_not_called()
