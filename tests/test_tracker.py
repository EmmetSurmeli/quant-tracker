"""Offline acceptance checks; no live sites or webhook calls."""

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import main
from filters import evaluate, extract_metadata
from notifier import send_discord_alert
from scraper import event_cards, html_cards, visible_soup
from storage import load_seen_items, merge_discovery, save_seen_items

TODAY = date(2026, 10, 14)
SITE = {"firm": "Arrowstreet Capital", "source": "Students", "url": "https://example.com/students", "kind": "html"}


def card(title, description, url="https://example.com/opportunity"):
    return {"title": title, "description": description, "url": url, "posting_id": "", "location": ""}


class FilteringTests(unittest.TestCase):
    def test_quant_intern_yes_generic_roles_no(self):
        self.assertIsNotNone(evaluate(card("Quantitative Research Intern", "Research systematic trading strategies for undergraduate students."), SITE, TODAY))
        self.assertIsNotNone(evaluate(card("Quantitative Research Summer Analyst", "Undergraduate students research systematic trading strategies."), SITE, TODAY))
        self.assertIsNone(evaluate(card("Investment Banking Summer Analyst", "Students learn about markets and trading."), SITE, TODAY))
        self.assertIsNone(evaluate(card("Software Engineer Intern", "Build trading software with quantitative researchers."), SITE, TODAY))
        self.assertIsNone(evaluate(card("Operations Intern", "Support trading operations for students."), SITE, TODAY))
        self.assertIsNone(evaluate(card("Senior Quantitative Researcher", "Experienced full-time position."), SITE, TODAY))

    def test_symposium_explicit_details(self):
        item = evaluate(card("Quant Finance Symposium", "First- and second-year undergraduate students interested in quantitative trading.\nApplication deadline: March 5, 2027\nProgram dates: Early April 2027\nLocation: Boston"), SITE, TODAY)
        self.assertEqual(item["type"], "Event")
        self.assertEqual(item["application_deadline"], "March 5, 2027")
        self.assertEqual(item["program_date_or_timeline"], "Early April 2027")
        self.assertIn("second-year", item["eligibility"])
        self.assertEqual(item["location"], "Boston")

    def test_missing_metadata_and_expired_event(self):
        item = evaluate(card("Quant Finance Symposium", "Undergraduate students explore trading research at the firm."), SITE, TODAY)
        self.assertEqual(item["application_deadline"], "")
        self.assertEqual(item["program_date_or_timeline"], "")
        old = evaluate(card("Quant Finance Symposium 2025", "Undergraduate students explore quantitative trading.\nEvent date: April 10, 2025"), SITE, TODAY)
        self.assertIsNone(old)

    def test_vague_but_explicit_timeline(self):
        site = {**SITE, "kind": "detail"}
        item = evaluate(card("FTTP", "Over the course of a few days, first-year undergraduates learn about trading models at Jane Street.\nMath and technology are at the core of the program."), site, TODAY)
        self.assertIn("over the course of a few days", item["program_date_or_timeline"].lower())
        self.assertEqual(extract_metadata("Runs from July 8 to July 12, 2027")["program_date_or_timeline"], "July 8 to July 12, 2027")
        self.assertEqual(extract_metadata("July 8–12, 2027")["program_date_or_timeline"], "July 8–12, 2027")

    def test_card_scope(self):
        html = '''<main><article><h3>Quantitative Trader Intern</h3><p>Students trade options.</p><a href="/jobs/1">Apply</a></article><article><h3>Quantitative Research Intern</h3><p>Application deadline: May 1, 2027</p><a href="/jobs/2">Apply</a></article></main>'''
        cards = html_cards(visible_soup(html), "https://example.com/students")
        self.assertEqual(len(cards), 2)
        self.assertNotIn("deadline", cards[0]["description"].lower())
        self.assertIn("deadline", cards[1]["description"].lower())

    def test_regional_events_keep_their_own_dates(self):
        site = {**SITE, "kind": "events", "source": "Discover"}
        html = '''<main><h1>Discover Citadel</h1><p>Undergraduate students explore quantitative research and trading.</p><p>Must be a first-year or second-year to apply.</p><h3>Discover - U.S.</h3><p>Location: New York</p><p>Program Dates: Early April 2027</p><p>Application Deadline: March 5, 2027</p><h3>Discover - EMEA</h3><p>Location: London</p><p>Event Date: End of March 2027</p><p>Application Deadline: January 29, 2027</p></main>'''
        cards = event_cards(visible_soup(html), site)
        self.assertEqual(len(cards), 2)
        us, emea = [evaluate(candidate, site, TODAY) for candidate in cards]
        self.assertEqual(us["application_deadline"], "March 5, 2027")
        self.assertEqual(emea["application_deadline"], "January 29, 2027")
        self.assertEqual(us["location"], "New York")
        self.assertEqual(emea["location"], "London")
        self.assertIn("first-year", us["eligibility"])


class HistoryTests(unittest.TestCase):
    def test_cross_source_dedupe_and_cycle(self):
        item = evaluate(card("Quantitative Research Intern", "Students research trading signals.", "https://example.com/jobs/123?utm_source=a"), SITE, TODAY)
        records = []
        self.assertTrue(merge_discovery(records, item, "2026-10-14"))
        duplicate = {**item, "source": "Other Page", "source_page_url": "https://example.com/other", "url": "https://example.com/jobs/123?utm_source=b"}
        self.assertFalse(merge_discovery(records, duplicate, "2026-10-14"))
        self.assertEqual(len(records), 1)
        other_posting = {**item, "url": "https://example.com/jobs/456", "posting_id": "greenhouse:example:456"}
        self.assertTrue(merge_discovery(records, other_posting, "2026-10-14"))
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "seen.json")
            save_seen_items(path, records)
            self.assertEqual(len(load_seen_items(path)), 2)
        next_year = {**item, "title_or_snippet": "Quantitative Research Intern 2027"}
        self.assertTrue(merge_discovery(records, next_year, "2027-01-01"))

    def test_delivery_state_cap_dry_run_and_no_repeat(self):
        site = dict(SITE)
        candidates = [card("Quantitative Research Intern", "Undergraduate students research trading signals.", "https://example.com/a"),
                      card("Quantitative Trader Intern", "Undergraduate students learn options trading.", "https://example.com/b")]
        with tempfile.TemporaryDirectory() as directory, patch.object(main, "fetch_site", return_value=(candidates, "")), patch.object(main, "MAX_ALERTS_PER_RUN", 1):
            path = str(Path(directory) / "seen.json")
            with patch.dict("os.environ", {"DRY_RUN": "true", "DISCORD_WEBHOOK_URL": ""}):
                stats = main.run([site], path)
            self.assertEqual(stats["previewed"], 1)
            self.assertTrue(all(item["status"] == "pending" for item in load_seen_items(path)))
            with patch.dict("os.environ", {"DRY_RUN": "false", "DISCORD_WEBHOOK_URL": "https://example.com/webhook"}), patch.object(main, "send_discord_alert", return_value={"status": "sent", "error": ""}) as sender:
                stats = main.run([site], path)
                self.assertEqual(stats["sent"], 1)
                self.assertEqual(sender.call_count, 1)
                stats = main.run([site], path)
                self.assertEqual(stats["sent"], 1)
                self.assertEqual(sender.call_count, 2)
                stats = main.run([site], path)
                self.assertEqual(stats["sent"], 0)
                self.assertEqual(sender.call_count, 2)
            self.assertTrue(all(item["status"] == "sent" for item in load_seen_items(path)))


class NotificationTests(unittest.TestCase):
    def test_mention_safe_payload_and_dry_run(self):
        item = {"firm": "@everyone", "source": "Test", "type": "Program", "title_or_snippet": "Quant Program", "url": "https://example.com", "source_page_url": "https://example.com"}
        dry = send_discord_alert("", item, "2026-10-14", dry_run=True)
        self.assertEqual(dry["status"], "dry_run")
        self.assertIn("Eligibility: Not found", dry["message"])
        self.assertIn("\nFirm: @everyone\n", dry["message"])
        class Response:
            status_code = 200
        with patch("notifier.requests.post", return_value=Response()) as post:
            result = send_discord_alert("https://example.com/webhook", item, "2026-10-14")
        self.assertEqual(result["status"], "sent")
        self.assertEqual(post.call_args.kwargs["json"]["allowed_mentions"], {"parse": []})


if __name__ == "__main__":
    unittest.main()
