from __future__ import annotations

import re
from typing import Any


_WINDOWS_PATH = re.compile(r"(?i)\b[a-z]:\\[^\s]+")
_POSIX_PATH = re.compile(
    r"(?<![:/\w])/"
    r"(?!api(?:/|$)|openapi(?:/|$)|health(?:/|$))"
    r"(?:[^/\s]+/)+[^\s]+"
)
_CONNECTION_URL = re.compile(
    r"(?i)\b(?:postgresql|postgres|mysql|mariadb|mongodb|redis)://[^\s]+"
)
_BEARER_TOKEN = re.compile(r"(?i)authorization:\s*bearer\s+[^\s]+")
_NAMED_SECRET = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|secret)\s*[:=]\s*[^\s]+"
)
_BLOCKED_KEY_PARTS = (
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "password",
    "secret",
    "stored_path",
    "source_path",
    "output_path",
    "pdf_path",
    "database_url",
    "raw_response",
    "raw_prompt",
    "stderr",
)
_MAX_TEXT_LENGTH = 500
_MAX_LIST_ITEMS = 100
_MAX_DEPTH = 6


def sanitize_audit_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_value(payload, depth=0)
    return sanitized if isinstance(sanitized, dict) else {}


def sanitize_audit_text(value: str) -> str:
    return _sanitize_text(value)


def _sanitize_value(value: Any, *, depth: int) -> Any:
    if depth >= _MAX_DEPTH:
        return "[truncated]"
    if isinstance(value, dict):
        return {
            str(key): _sanitize_value(item, depth=depth + 1)
            for key, item in value.items()
            if not _blocked_key(str(key))
        }
    if isinstance(value, list):
        return [
            _sanitize_value(item, depth=depth + 1)
            for item in value[:_MAX_LIST_ITEMS]
        ]
    if isinstance(value, str):
        return _sanitize_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _sanitize_text(str(value))


def _blocked_key(key: str) -> bool:
    normalized = key.casefold()
    return any(part in normalized for part in _BLOCKED_KEY_PARTS)


def _sanitize_text(value: str) -> str:
    text = " ".join(value.split())
    text = _WINDOWS_PATH.sub("[path redacted]", text)
    text = _POSIX_PATH.sub("[path redacted]", text)
    text = _CONNECTION_URL.sub("[connection redacted]", text)
    text = _BEARER_TOKEN.sub("Authorization: Bearer [redacted]", text)
    text = _NAMED_SECRET.sub("[secret redacted]", text)
    if len(text) > _MAX_TEXT_LENGTH:
        return text[: _MAX_TEXT_LENGTH - 3] + "..."
    return text
