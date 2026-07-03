from hashlib import sha256

MAX_DATABASE_ID_LENGTH = 64


def database_safe_id(raw_id: str, fallback_prefix: str, max_length: int = MAX_DATABASE_ID_LENGTH) -> str:
    if len(raw_id) <= max_length:
        return raw_id
    digest = sha256(raw_id.encode("utf-8")).hexdigest()[:32]
    return f"{fallback_prefix}-{digest}"
