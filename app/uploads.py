"""Safe file uploads.

Uploaded files are never stored under the name the user gave. Each one gets a
random name, the extension must be on an allow-list, and the first bytes of the
file must match what the extension claims. Files live in the "instance" folder
(outside the public static folder) and are only served after a permission check.
"""
import os
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

OLE_HEADER = b"\xd0\xcf\x11\xe0"  # old .doc / .xls / .ppt files
ZIP_HEADER = b"PK\x03\x04"        # .docx / .xlsx / .pptx files


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _matches_signature(ext: str, head: bytes, whole_file_head: bytes) -> bool:
    if ext == "pdf":
        return head.startswith(b"%PDF")
    if ext == "png":
        return head.startswith(b"\x89PNG")
    if ext in ("jpg", "jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext in ("docx", "xlsx", "pptx"):
        return head.startswith(ZIP_HEADER)
    if ext in ("doc", "xls", "ppt"):
        return head.startswith(OLE_HEADER)
    if ext == "webp":
        return head.startswith(b"RIFF") and head[8:12] == b"WEBP"
    if ext == "txt":
        return b"\x00" not in whole_file_head
    return False


class FileStore:
    """Saves and removes uploaded files."""

    @staticmethod
    def _folder(key: str) -> Path:
        folder = Path(current_app.config[key])
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    @classmethod
    def _save(cls, upload, allowed: set, folder_key: str, max_bytes: int):
        if upload is None or not upload.filename:
            raise ValueError("Choose a file to upload.")
        original = secure_filename(upload.filename)
        ext = _extension(original or upload.filename)
        if ext not in allowed:
            raise ValueError("That file type is not allowed. Use: " + ", ".join(sorted(allowed)).upper() + ".")
        head = upload.stream.read(2048)
        upload.stream.seek(0)
        if not head:
            raise ValueError("That file is empty.")
        if not _matches_signature(ext, head[:16], head):
            raise ValueError("The file does not look like a real ." + ext + " file.")
        stored = f"{uuid.uuid4().hex}.{ext}"
        destination = cls._folder(folder_key) / stored
        upload.save(destination)
        size = destination.stat().st_size
        if size > max_bytes:
            destination.unlink(missing_ok=True)
            raise ValueError(f"The file is too large. The limit is {max_bytes // (1024 * 1024)} MB.")
        display_name = (original if original else f"file.{ext}")[:200]
        return display_name, stored, size

    @classmethod
    def save_order_file(cls, upload):
        """Returns (display_name, stored_name, size_in_bytes) or raises ValueError."""
        return cls._save(upload, current_app.config["ORDER_FILE_EXTENSIONS"], "UPLOAD_DIR",
                         current_app.config["MAX_CONTENT_LENGTH"])

    @classmethod
    def save_avatar(cls, upload):
        _, stored, _ = cls._save(upload, current_app.config["AVATAR_EXTENSIONS"], "AVATAR_DIR",
                                 current_app.config["AVATAR_MAX_BYTES"])
        return stored

    @classmethod
    def order_file_path(cls, stored: str) -> Path:
        return cls._folder("UPLOAD_DIR") / os.path.basename(stored)

    @classmethod
    def avatar_path(cls, stored: str) -> Path:
        return cls._folder("AVATAR_DIR") / os.path.basename(stored)

    @classmethod
    def delete_order_file(cls, stored: str) -> None:
        if stored:
            cls.order_file_path(stored).unlink(missing_ok=True)

    @classmethod
    def delete_avatar(cls, stored: str) -> None:
        if stored:
            cls.avatar_path(stored).unlink(missing_ok=True)
