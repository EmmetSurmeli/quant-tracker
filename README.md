# Quant Opportunity Tracker

A small run-once Python bot that checks official student pages and public job-board feeds for quant/trading internships and student programs. It sends new matches to Discord and keeps local JSON history. No database, browser automation, or AI service is needed.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your Discord webhook URL. Keep it private:

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DRY_RUN=true
```

Start with `DRY_RUN=true`. The bot shows every pending match but does not post or mark opportunities sent. The alert cap applies only to live Discord sends. After reviewing results, set `DRY_RUN=false` and run again. A quick webhook-only test is `python3 test_webhook.py`; it follows `DRY_RUN` and does not touch history.

## Run

```bash
python3 main.py
```

The script checks each configured source once and exits. Edit URLs and `MAX_ALERTS_PER_RUN` in `config.py`. Sources can be `html`, `detail`, `events`, `greenhouse`, or `lever`. Filtering and extraction rules are in `filters.py`.

## History and delivery

`seen.json` is created automatically. Each record contains firm, source, title, URL, summary, eligibility, location, deadline, timeline, identity keys, first-seen date, and a delivery status. It is ignored by Git. The pre-rebuild history is backed up locally as `seen.pre-rebuild-2026-10-14.json`; the rebuilt tracker starts with an empty history.

- `sent`: Discord confirmed delivery; never sent again for the same opportunity.
- `pending`: found but capped, dry-run-only, missing webhook, or definitely failed; eligible next run only if the listing is found again. A failed source will not trigger stale pending alerts.
- `delivery_unknown`: a timeout/connection error or server error may have happened after acceptance. Check the channel before manually changing this record back to `pending`.

To start over later, back up `seen.json` and replace its contents with `[]`. This can resend all currently detected opportunities. Avoid deleting a valid history by accident.

Deduplication uses ATS posting IDs or canonical opportunity URLs where available, plus a normalized firm/title/type/event-cycle fallback. It is best-effort: sites can rename or repost roles, and a crash between Discord delivery and history write can still cause a duplicate.

## Daily macOS cron

Use `crontab -e` and add a line like this (replace both paths with your own absolute paths):

```cron
0 8 * * * cd /absolute/path/quant_tracker && /absolute/path/quant_tracker/.venv/bin/python main.py >> /absolute/path/quant_tracker/bot.log 2>&1
```

Run it manually first. `bot.log`, `.env`, and all `seen` JSON files are ignored by Git.

## Limitations

The bot reads visible HTML with `requests`/BeautifulSoup and public Greenhouse/Lever feeds. JavaScript-only listings, changed page layouts, or anti-bot pages may yield zero candidates. Some sources return HTTP 403; the bot logs these and continues rather than trying to bypass them. Deadline, program dates, eligibility, and summary are extracted only from explicit listing text, so missing fields stay blank. Review links before applying. No live webhook is exercised by the test suite.
