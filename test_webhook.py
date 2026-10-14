"""Preview or send one sample alert without scraping or changing history."""

from __future__ import annotations

import os
from datetime import date

from dotenv import load_dotenv

from notifier import send_discord_alert


def run() -> None:
    load_dotenv()
    dry_run = os.getenv("DRY_RUN", "true").strip().lower() in {"1", "true", "yes", "on"}
    sample = {
        "firm": "Sample Firm", "source": "Webhook Test", "type": "Internship",
        "title_or_snippet": "Quantitative Research Intern", "summary": "Sample opportunity message for webhook testing.",
        "eligibility": "Undergraduate students", "location": "New York",
        "application_deadline": "", "program_date_or_timeline": "",
        "match_reason": "webhook test", "url": "https://example.com/opportunity",
        "source_page_url": "https://example.com/students",
    }
    result = send_discord_alert(os.getenv("DISCORD_WEBHOOK_URL", "").strip(), sample,
                                date.today().isoformat(), dry_run=dry_run)
    print(f"Webhook test: {result['status']}")
    print(result["message"] if dry_run else result["error"])


if __name__ == "__main__":
    run()
