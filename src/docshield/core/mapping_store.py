"""Encrypted mapping file (FR-5.1, FR-5.2, FR-5.3).

A ``.dsm`` is a binary file with this layout:

    DSM1   (4-byte magic)
    salt   (16 bytes, random per-file)
    body   (Fernet token over UTF-8 JSON of the mapping)

The Fernet key is derived from the user's master password via PBKDF2-HMAC-
SHA256 with 200_000 iterations and the per-file salt. Per-file salt means
two files with the same password still produce different ciphertexts and
neither leaks key material if one password is broken.

JSON shape (FR-9.1):

    {
      "version": 1,
      "created_at": "...",
      "source_file": "...",
      "language": "...",
      "entries": [{"placeholder": "[PERSON_1]", "original": "...", "type": "PERSON"}, ...]
    }
"""

from __future__ import annotations

import base64
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"DSM1"
SALT_LEN = 16
PBKDF2_ITERS = 200_000


class MappingStoreError(Exception):
    """Raised on bad password, corrupt file, or version mismatch."""


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERS,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


@dataclass
class MappingFile:
    source_file: str
    language: str
    entries: list[dict[str, str]]
    version: int = 1
    created_at: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at or datetime.now(timezone.utc).isoformat(),
            "source_file": self.source_file,
            "language": self.language,
            "entries": self.entries,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "MappingFile":
        if data.get("version") != 1:
            raise MappingStoreError(f"unsupported mapping version: {data.get('version')}")
        return cls(
            version=data["version"],
            created_at=data.get("created_at", ""),
            source_file=data.get("source_file", ""),
            language=data.get("language", ""),
            entries=list(data.get("entries", [])),
        )


def save(path: str | Path, mapping: MappingFile, password: str) -> Path:
    """Encrypt + write atomically (NFR-4.2)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    salt = secrets.token_bytes(SALT_LEN)
    key = _derive_key(password, salt)
    payload = json.dumps(mapping.to_json(), ensure_ascii=False).encode("utf-8")
    token = Fernet(key).encrypt(payload)

    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_bytes(MAGIC + salt + token)
    os.replace(tmp, out)
    return out


def load(path: str | Path, password: str) -> MappingFile:
    raw = Path(path).read_bytes()
    if not raw.startswith(MAGIC):
        raise MappingStoreError("not a DocShield mapping file")
    salt = raw[len(MAGIC) : len(MAGIC) + SALT_LEN]
    token = raw[len(MAGIC) + SALT_LEN :]
    key = _derive_key(password, salt)
    try:
        plain = Fernet(key).decrypt(token)
    except InvalidToken as exc:
        raise MappingStoreError("invalid password or corrupt file") from exc
    return MappingFile.from_json(json.loads(plain.decode("utf-8")))
