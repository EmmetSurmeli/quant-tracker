"""JSON history, canonical identities, and atomic saves."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode(sorted((key, value) for key, value in parse_qsl(parts.query)
                           if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/", query, ""))


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def identity_keys(item: dict[str, Any]) -> set[str]:
    """Aliases let the same listing match across a source page and an ATS feed."""
    firm = norm(item["firm"])
    title = norm(item["title_or_snippet"])
    cycle_text = " ".join((item.get("title_or_snippet", ""), item.get("application_deadline", ""),
                           item.get("program_date_or_timeline", "")))
    years = re.findall(r"\b20\d{2}\b", cycle_text)
    cycle = max(years) if years else "undated"
    fallback = f"fallback:{firm}:{title}:{norm(item['type'])}:{cycle}"
    keys: set[str] = set()
    posting_id = item.get("posting_id", "")
    if posting_id:
        keys.add(f"posting:{posting_id}")
    url = canonical_url(item.get("url", ""))
    source = canonical_url(item.get("source_page_url", ""))
    if url and url != source:
        keys.add(f"url:{firm}:{url}:{cycle}")
    if not keys:
        keys.add(fallback)
    return keys


def stable_item_hash(item: dict[str, Any]) -> str:
    keys = identity_keys(item)
    primary = sorted(key for key in keys if key.startswith("posting:"))
    if not primary:
        primary = sorted(key for key in keys if key.startswith("url:"))
    if not primary:
        primary = sorted(keys)
    return hashlib.sha256(primary[0].encode("utf-8")).hexdigest()


def new_record(item: dict[str, Any], found_date: str) -> dict[str, Any]:
    return {**item, "hash": stable_item_hash(item), "identity_keys": sorted(identity_keys(item)),
            "first_seen_date": found_date, "status": "pending", "alerted": False}


def load_seen_items(path: str) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, list) or any(not isinstance(item, dict) or "status" not in item for item in data):
        raise ValueError(f"{path} uses the old/invalid history format; back it up and replace it with []")
    return data


def save_seen_items(path: str, items: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(items, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def merge_discovery(records: list[dict[str, Any]], item: dict[str, Any], found_date: str) -> bool:
    """Add a new item or enrich a pending one. Return True only if newly added."""
    keys = identity_keys(item)
    for record in records:
        existing = set(record.get("identity_keys") or identity_keys(record))
        if keys & existing:
            record["identity_keys"] = sorted(keys | existing)
            if record["status"] == "pending":
                for field in ("summary", "application_deadline", "program_date_or_timeline", "eligibility", "location"):
                    if not record.get(field) and item.get(field):
                        record[field] = item[field]
            return False
    records.append(new_record(item, found_date))
    return True
