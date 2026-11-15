from __future__ import annotations

import uuid


def parse_uuid(identifier: str) -> uuid.UUID:
    """Helper to parse a UUID string or deterministically map standard demo IDs.
    
    If the string is already a valid UUID (32 hex digits with or without hyphens),
    it is parsed directly. Otherwise, a deterministic UUIDv5 is generated within
    the Sentra-X namespace.
    """
    try:
        return uuid.UUID(identifier)
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"), f"sentrax.{identifier}")

