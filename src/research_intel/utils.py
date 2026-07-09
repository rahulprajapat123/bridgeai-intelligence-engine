from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime
from typing import Iterable


WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{1,}")


def utc_now() -> datetime:
    return datetime.now(UTC)


def stable_id(*parts: str, length: int = 32) -> str:
    digest = hashlib.sha256("||".join(parts).encode("utf-8", errors="ignore")).hexdigest()
    return digest[:length]


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in WORD_RE.finditer(text or "")]


def sentence_split(text: str) -> list[str]:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if not clean:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", clean)
    return [part.strip() for part in parts if len(part.strip()) > 20]


def clamp(value: float, low: float = 0, high: float = 1) -> float:
    return max(low, min(high, value))


def parse_year(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(19|20)\d{2}", value)
    return int(match.group(0)) if match else None


def date_to_iso(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def unique_keep_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized = value.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            output.append(normalized)
            seen.add(key)
    return output

