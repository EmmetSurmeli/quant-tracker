"""Readable, mention-safe Discord webhook alerts."""

from __future__ import annotations

import time
from typing import Any

import requests


def short(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[:limit - 3].rstrip() + "..."


def build_discord_message(item: dict[str, Any], found_date: str) -> str:
    def field(name: str, limit: int = 300) -> str:
        return short(item.get(name, ""), limit) or "Not found"

    message = (
        "🚨 NEW QUANT OPPORTUNITY\n\n"
        f"Firm: {field('firm', 90)}\n"
        f"Source: {field('source', 90)}\n"
        f"Type: {field('type', 40)}\n"
        f"Title/Snippet: {field('title_or_snippet', 180)}\n"
        f"Summary: {field('summary', 250)}\n\n"
        f"Eligibility: {field('eligibility', 420)}\n"
        f"Location: {field('location', 120)}\n"
        f"Application Deadline: {field('application_deadline', 140)}\n"
        f"Program Date / Timeline: {field('program_date_or_timeline', 140)}\n\n"
        f"Reason Matched: {field('match_reason', 110)}\n\n"
        f"Opportunity URL:\n{field('url', 350)}\n\n"
        f"Source Page:\n{field('source_page_url', 350)}\n\n"
        f"Found: {found_date}"
    )
    return message if len(message) <= 2000 else message[:1997].rstrip() + "..."


def retry_delay(response: requests.Response) -> float:
    try:
        payload = response.json()
        if isinstance(payload, dict) and isinstance(payload.get("retry_after"), (int, float)):
            return max(0.0, float(payload["retry_after"]))
    except ValueError:
        pass
    try:
        return max(0.0, float(response.headers.get("Retry-After", "0")))
    except ValueError:
        return 0.0


def send_discord_alert(webhook_url: str, item: dict[str, Any], found_date: str,
                       dry_run: bool = False) -> dict[str, Any]:
    """Return status sent, pending, delivery_unknown, or dry_run."""
    message = build_discord_message(item, found_date)
    if dry_run:
        return {"status": "dry_run", "message": message, "error": ""}
    if not webhook_url:
        return {"status": "pending", "message": message, "error": "Missing DISCORD_WEBHOOK_URL"}
    payload = {"content": message, "allowed_mentions": {"parse": []}}
    for attempt in range(3):
        try:
            response = requests.post(webhook_url, params={"wait": "true"}, json=payload, timeout=15)
        except requests.RequestException as exc:
            # The server may have accepted a message before the connection failed.
            return {"status": "delivery_unknown", "message": message,
                    "error": f"{type(exc).__name__}; check the Discord channel before retrying"}
        if response.status_code in (200, 204):
            return {"status": "sent", "message": message, "error": ""}
        if response.status_code == 429:
            if attempt < 2:
                time.sleep(retry_delay(response))
                continue
            return {"status": "pending", "message": message, "error": "Discord rate limit persisted"}
        if response.status_code >= 500:
            return {"status": "delivery_unknown", "message": message,
                    "error": f"Discord HTTP {response.status_code}; check channel before retrying"}
        return {"status": "pending", "message": message,
                "error": f"Discord HTTP {response.status_code}: {short(response.text, 160)}"}
    return {"status": "pending", "message": message, "error": "Rate limit retries exhausted"}
