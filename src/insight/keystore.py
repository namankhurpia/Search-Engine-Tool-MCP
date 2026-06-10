"""CSV-backed API key store.

Keys file format (keys.csv):
    name,key,created_at,active
    my-agent,ink_a1b2c3d4e5f6...,2026-06-10T12:00:00,true

Keys are prefixed with `ink_` (insight-key) for easy identification.
"""
from __future__ import annotations

import csv
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_KEY_PREFIX = "ink_"
_FIELDNAMES = ["name", "key", "created_at", "active"]


class KeyStore:
    def __init__(self, path: str | Path = "keys.csv"):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.path.exists():
            with self._lock:
                with open(self.path, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
                    writer.writeheader()

    def _read_all(self) -> list[dict]:
        with open(self.path, newline="") as f:
            return list(csv.DictReader(f))

    def _write_all(self, rows: list[dict]) -> None:
        with open(self.path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)

    def create_key(self, name: str) -> dict:
        """Create a new API key with the given name. Returns the key record."""
        key = _KEY_PREFIX + secrets.token_hex(24)
        record = {
            "name": name.strip(),
            "key": key,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "active": "true",
        }
        with self._lock:
            rows = self._read_all()
            rows.append(record)
            self._write_all(rows)
        return record

    def validate_key(self, key: str) -> Optional[str]:
        """Check if a key is valid and active. Returns the key name or None."""
        rows = self._read_all()
        for row in rows:
            if row["key"] == key and row.get("active", "true").lower() == "true":
                return row["name"]
        return None

    def list_keys(self) -> list[dict]:
        """List all keys (masks the actual key value for security)."""
        rows = self._read_all()
        for row in rows:
            k = row["key"]
            row["key"] = k[:8] + "..." + k[-4:] if len(k) > 12 else "***"
        return rows

    def revoke_key(self, name: str) -> bool:
        """Revoke all keys with the given name. Returns True if any were revoked."""
        with self._lock:
            rows = self._read_all()
            found = False
            for row in rows:
                if row["name"] == name and row.get("active", "true").lower() == "true":
                    row["active"] = "false"
                    found = True
            if found:
                self._write_all(rows)
            return found
