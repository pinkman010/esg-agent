from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4


@dataclass(frozen=True)
class StoredDocument:
    original_filename: str
    path: Path
    stored_path: str
    file_hash: str


class DocumentStore:
    def __init__(self, upload_dir: Path, derived_dir: Path):
        self.upload_dir = Path(upload_dir)
        self.derived_dir = Path(derived_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.derived_dir.mkdir(parents=True, exist_ok=True)

    def save_upload(self, file_obj: BinaryIO, original_filename: str) -> StoredDocument:
        content = file_obj.read()
        file_hash = sha256(content).hexdigest()
        destination = self._unique_destination(original_filename)
        destination.write_bytes(content)
        return StoredDocument(
            original_filename=original_filename,
            path=destination,
            stored_path=destination.as_posix(),
            file_hash=file_hash,
        )

    def _unique_destination(self, original_filename: str) -> Path:
        suffix = Path(original_filename).suffix or ".pdf"
        stem = Path(original_filename).stem or "report"
        candidate = self.upload_dir / f"{stem}{suffix}"
        if not candidate.exists():
            return candidate
        return self.upload_dir / f"{stem}-{uuid4().hex[:12]}{suffix}"