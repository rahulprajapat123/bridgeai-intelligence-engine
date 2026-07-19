from __future__ import annotations

import hashlib
import html
import math
import re
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMETERS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", html.unescape(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalized_language(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalize_text(value).lower()).strip()


def canonicalize_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parts = urlsplit(value.strip())
        host = (parts.hostname or "").lower()
        if not host:
            return value.strip()
        port = f":{parts.port}" if parts.port and parts.port not in {80, 443} else ""
        path = re.sub(r"/{2,}", "/", parts.path).rstrip("/") or "/"
        query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMETERS))
        return urlunsplit(((parts.scheme or "https").lower(), host + port, path, query, ""))
    except ValueError:
        return value.strip()


def fingerprint(*values: str | None) -> str:
    return hashlib.sha256("\x1f".join(normalized_language(v or "") for v in values).encode()).hexdigest()


def cosine_similarity(left: str, right: str) -> float:
    a, b = Counter(normalized_language(left).split()), Counter(normalized_language(right).split())
    if not a or not b:
        return 0.0
    dot = sum(count * b.get(term, 0) for term, count in a.items())
    return dot / math.sqrt(sum(x*x for x in a.values()) * sum(x*x for x in b.values()))


def vector_similarity(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right): return 0.0
    denom = math.sqrt(sum(x*x for x in left) * sum(x*x for x in right))
    return sum(a*b for a, b in zip(left, right, strict=True)) / denom if denom else 0.0


def recency_weight(published_at: datetime | None, half_life_days: float, now: datetime | None = None) -> float:
    if not published_at: return 0.5
    now = now or datetime.now(UTC)
    if published_at.tzinfo is None: published_at = published_at.replace(tzinfo=UTC)
    age = max(0.0, (now - published_at).total_seconds() / 86400)
    return math.exp(-math.log(2) * age / half_life_days)
