"""Tests for Google Drive client — Task 8."""
from unittest.mock import MagicMock, patch
import io
import os
import pytest


def test_list_files():
    """list_files returns filtered file metadata from a Drive folder."""
    from app.indexer.drive_client import DriveClient

    mock_service = MagicMock()
    mock_service.files().list().execute.return_value = {
        "files": [
            {"id": "abc", "name": "midterm.pdf", "md5Checksum": "hash1"},
            {"id": "def", "name": "lab6.jpg", "md5Checksum": "hash2"},
        ]
    }
    client = DriveClient(service=mock_service)
    files = client.list_files("folder_id_123")
    assert len(files) == 2
    assert files[0]["name"] == "midterm.pdf"


def test_list_files_empty_folder():
    """list_files returns empty list when folder has no matching files."""
    from app.indexer.drive_client import DriveClient

    mock_service = MagicMock()
    mock_service.files().list().execute.return_value = {"files": []}
    client = DriveClient(service=mock_service)
    files = client.list_files("empty_folder")
    assert files == []


def test_list_files_no_files_key():
    """list_files returns empty list when API response has no 'files' key."""
    from app.indexer.drive_client import DriveClient

    mock_service = MagicMock()
    mock_service.files().list().execute.return_value = {}
    client = DriveClient(service=mock_service)
    files = client.list_files("folder_id_123")
    assert files == []


def test_skip_unchanged_files():
    """filter_changed excludes files whose md5 matches existing_hashes by file ID."""
    from app.indexer.drive_client import DriveClient

    client = DriveClient(service=MagicMock())
    existing_hashes = {"file_id_abc": "hash1"}
    files = [
        {"id": "file_id_abc", "name": "midterm.pdf", "md5Checksum": "hash1"},  # unchanged
        {"id": "file_id_def", "name": "quiz.pdf", "md5Checksum": "hash2"},  # new
    ]
    changed = client.filter_changed(files, existing_hashes)
    assert len(changed) == 1
    assert changed[0]["name"] == "quiz.pdf"


def test_filter_changed_detects_updated_hash():
    """filter_changed includes files whose md5 changed (same ID, different hash)."""
    from app.indexer.drive_client import DriveClient

    client = DriveClient(service=MagicMock())
    existing_hashes = {"file_id_abc": "old_hash"}
    files = [
        {"id": "file_id_abc", "name": "midterm.pdf", "md5Checksum": "new_hash"},
    ]
    changed = client.filter_changed(files, existing_hashes)
    assert len(changed) == 1
    assert changed[0]["id"] == "file_id_abc"


def test_filter_changed_all_new():
    """filter_changed returns all files when existing_hashes is empty."""
    from app.indexer.drive_client import DriveClient

    client = DriveClient(service=MagicMock())
    files = [
        {"id": "a", "name": "f1.pdf", "md5Checksum": "h1"},
        {"id": "b", "name": "f2.pdf", "md5Checksum": "h2"},
    ]
    changed = client.filter_changed(files, {})
    assert len(changed) == 2


def test_download_file_success(tmp_path):
    """download_file writes content to dest_path via MediaIoBaseDownload."""
    from app.indexer.drive_client import DriveClient

    mock_service = MagicMock()
    dest = str(tmp_path / "test.pdf")

    # Mock MediaIoBaseDownload to simulate a single-chunk download
    with patch("app.indexer.drive_client.MediaIoBaseDownload") as mock_dl_cls:
        mock_downloader = MagicMock()
        # next_chunk returns (status, done) — done=True on first call
        mock_downloader.next_chunk.return_value = (MagicMock(progress=lambda: 1.0), True)
        mock_dl_cls.return_value = mock_downloader

        client = DriveClient(service=mock_service)
        result = client.download_file("file_abc", dest)

    assert result is True
    mock_service.files().get_media.assert_called_once_with(fileId="file_abc")


def test_download_file_handles_api_error(tmp_path):
    """download_file catches exceptions and returns False (L005)."""
    from app.indexer.drive_client import DriveClient

    mock_service = MagicMock()
    mock_service.files().get_media.side_effect = Exception("API quota exceeded")

    client = DriveClient(service=mock_service)
    dest = str(tmp_path / "fail.pdf")
    result = client.download_file("file_abc", dest)

    assert result is False


def test_lazy_service_init():
    """When no service is injected, _get_service builds one lazily (L003)."""
    from app.indexer.drive_client import DriveClient

    client = DriveClient()  # no service injected
    assert client._service is None  # not built yet


def test_injected_service_used_directly():
    """When a service is injected, _get_service returns it without building."""
    from app.indexer.drive_client import DriveClient

    mock_service = MagicMock()
    client = DriveClient(service=mock_service)
    assert client._get_service() is mock_service
