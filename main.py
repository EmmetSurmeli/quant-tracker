"""Run the tracker once; schedule this script externally for daily checks."""

from __future__ import annotations

import os
from datetime import date

from dotenv import load_dotenv

from config import MAX_ALERTS_PER_RUN, MONITORED_SITES, SEEN_FILE_PATH
from filters import evaluate
from notifier import send_discord_alert
from scraper import fetch_site
from storage import load_seen_items, merge_discovery, save_seen_items


def dry_run_enabled() -> bool:
    return os.getenv("DRY_RUN", "false").strip().lower() in {"1", "true", "yes", "on"}


def run(sites: list[dict[str, str]] | None = None, history_path: str = SEEN_FILE_PATH) -> dict[str, int]:
    load_dotenv()
    sites = MONITORED_SITES if sites is None else sites
    today = date.today()
    dry_run = dry_run_enabled()
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    records = load_seen_items(history_path)
    stats = {"sites": 0, "errors": 0, "candidates": 0, "matches": 0,
             "new": 0, "attempted": 0, "sent": 0, "previewed": 0, "pending": 0, "unknown": 0}
    print(f"[START] {len(sites)} sources | {len(records)} saved | dry-run={dry_run} | cap={MAX_ALERTS_PER_RUN}")
    for index, site in enumerate(sites, 1):
        stats["sites"] += 1
        print(f"[SITE {index}/{len(sites)}] {site['firm']} - {site['source']}")
        cards, error = fetch_site(site)
        if error:
            stats["errors"] += 1
            print(f"  ERROR: {error}")
            continue
        if not cards:
            print("  WARNING: no listing cards found (page may require JavaScript or a parser update)")
        stats["candidates"] += len(cards)
        matched = added = 0
        for card in cards:
            item = evaluate(card, site, today)
            if not item:
                continue
            matched += 1
            if merge_discovery(records, item, today.isoformat()):
                added += 1
        stats["matches"] += matched
        stats["new"] += added
        print(f"  candidates={len(cards)} relevant={matched} new={added}")
    # Persist discoveries before sending so a crash cannot lose pending items.
    save_seen_items(history_path, records)
    for record in records:
        if record["status"] != "pending":
            continue
        if stats["attempted"] >= MAX_ALERTS_PER_RUN:
            stats["pending"] += 1
            continue
        stats["attempted"] += 1
        result = send_discord_alert(webhook_url, record, record["first_seen_date"], dry_run=dry_run)
        status = result["status"]
        label = f"{record['firm']} | {record['title_or_snippet'][:85]}"
        if status == "dry_run":
            stats["previewed"] += 1
            print(f"[DRY RUN] {label}\n{result['message']}\n")
            continue
        if status == "sent":
            record["status"] = "sent"
            record["alerted"] = True
            stats["sent"] += 1
            save_seen_items(history_path, records)
            print(f"[SENT] {label}")
        elif status == "delivery_unknown":
            record["status"] = "delivery_unknown"
            stats["unknown"] += 1
            save_seen_items(history_path, records)
            print(f"[REVIEW DELIVERY] {label}: {result['error']}")
        else:
            stats["pending"] += 1
            print(f"[PENDING] {label}: {result['error']}")
    print("[SUMMARY] " + " ".join(f"{key}={value}" for key, value in stats.items()))
    return stats


if __name__ == "__main__":
    run()
