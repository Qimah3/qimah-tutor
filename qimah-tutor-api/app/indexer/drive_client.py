"""Google Drive client with change detection via md5 hashes.

Uses file ID (not filename) as the change-detection key to handle
renames and duplicate filenames across subfolders.
"""
import logging
import os

from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)

# MIME types we support extracting text from
SUPPORTED_MIMES = (
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)


class DriveClient:
    """Thin wrapper around Google Drive API v3 for listing, filtering, and downloading files."""

    def __init__(self, service=None):
        # L003: lazy init — accept injected service for testing, build later if None
        self._service = service

    def _get_service(self):
        """Return the Drive API service, building it lazily if not injected."""
        if self._service is None:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
            if not creds_json:
                raise RuntimeError(
                    "GOOGLE_SERVICE_ACCOUNT_JSON env var is not set. "
                    "Provide a path to the service account JSON file."
                )
            creds = service_account.Credentials.from_service_account_file(
                creds_json,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
            self._service = build("drive", "v3", credentials=creds)
        return self._service

    def list_files(self, folder_id: str) -> list[dict]:
        """List supported files in a Drive folder.

        Returns list of dicts with keys: id, name, md5Checksum.
        Filters to PDFs, images (JPEG/PNG), and DOCX only.
        """
        service = self._get_service()
        mime_query = " or ".join(f"mimeType='{m}'" for m in SUPPORTED_MIMES)
        q = f"'{folder_id}' in parents and trashed=false and ({mime_query})"

        try:
            response = service.files().list(
                q=q,
                fields="files(id, name, md5Checksum)",
                pageSize=1000,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
        except Exception as exc:
            logger.error("Failed to list files in folder %s: %s", folder_id, exc)
            return []

        return response.get("files", [])

    def filter_changed(self, files: list[dict], existing_hashes: dict[str, str]) -> list[dict]:
        """Return only files that are new or have a different md5 hash.

        Args:
            files: List of file dicts from list_files (must have 'id' and 'md5Checksum').
            existing_hashes: Mapping of {drive_file_id: md5_checksum} from previous run.

        Returns:
            List of file dicts that are new or changed.
        """
        changed = []
        for f in files:
            file_id = f.get("id", "")
            checksum = f.get("md5Checksum", "")
            if existing_hashes.get(file_id) != checksum:
                changed.append(f)
        return changed

    def download_file(self, file_id: str, dest_path: str) -> bool:
        """Download a file from Drive to dest_path.

        Returns True on success, False on failure (L005: never crash the caller).
        """
        service = self._get_service()
        try:
            request = service.files().get_media(fileId=file_id)
            os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
            with open(dest_path, "wb") as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _status, done = downloader.next_chunk()
            return True
        except Exception as exc:
            logger.error("Failed to download file %s to %s: %s", file_id, dest_path, exc)
            return False
