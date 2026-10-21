"""Offline acceptance checks; no live sites or webhook calls."""

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import main
from filters import evaluate, extract_metadata, summary_from
from notifier import send_discord_alert
from scraper import event_cards, fetch_site, html_cards, visible_soup
from storage import load_seen_items, merge_discovery, save_seen_items

TODAY = date(2026, 10, 14)
SITE = {"firm": "Arrowstreet Capital", "source": "Students", "url": "https://example.com/students", "kind": "html"}


def card(title, description, url="https://example.com/jobs/123"):
    return {"title": title, "description": description, "url": url, "posting_id": "", "location": ""}


class FilteringTests(unittest.TestCase):
    def test_quant_intern_yes_generic_roles_no(self):
        self.assertIsNotNone(evaluate(card("Quantitative Research Intern", "Research systematic trading strategies for undergraduate students."), SITE, TODAY))
        self.assertIsNotNone(evaluate(card("Quantitative Research Summer Analyst", "Undergraduate students research systematic trading strategies."), SITE, TODAY))
        self.assertIsNone(evaluate(card("Investment Banking Summer Analyst", "Students learn about markets and trading."), SITE, TODAY))
        self.assertIsNone(evaluate(card("Software Engineer Intern", "Build trading software with quantitative researchers."), SITE, TODAY))
        self.assertIsNone(evaluate(card("Operations Intern", "Support trading operations for students."), SITE, TODAY))
        self.assertIsNone(evaluate(card("Senior Quantitative Researcher", "Experienced full-time position."), SITE, TODAY))
        self.assertIsNone(evaluate(card("2027 PhD Quantitative Research Intern", "Quant trading research internship."), SITE, TODAY))
        self.assertIsNone(evaluate(card("2027 Systematic COO Intern", "Trading internship for students."), SITE, TODAY))
        self.assertIsNone(evaluate(card("Graduate Trader Program Chicago 2027", "Students learn quantitative trading."), SITE, TODAY))
        self.assertIsNone(evaluate(card("LINK 2027: Software Development Intensive Program", "Second-year students learn about a trading firm."), SITE, TODAY))
        self.assertIsNone(evaluate(card("Trading Internship", "Undergraduate students learn trading.", "https://example.com/stories/my-internship/"), SITE, TODAY))
        self.assertIsNone(evaluate(card("Trading Internship", "Undergraduate students learn trading.", "https://example.com/internships/trading/"), SITE, TODAY))
        self.assertIsNotNone(evaluate(card("Quantitative Trading Intern 2027", "Students work on trading models.", "https://example.com/jobs/team/12345"), SITE, TODAY))
        self.assertIsNotNone(evaluate(card("Quantitative Intern", "Students work on trading models.", "https://example.com/vacancies/quantitative-intern/"), SITE, TODAY))
        dedicated = {**SITE, "kind": "detail", "url": "https://example.com/careers/quant-intern-2027"}
        self.assertIsNotNone(evaluate(card("Quantitative Research Internship 2027", "Students research trading models.", dedicated["url"]), dedicated, TODAY))

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
        self.assertEqual(extract_metadata("FutureFocus is a five-day discovery program for first-year students.")["program_date_or_timeline"], "five-day discovery program")
        self.assertEqual(extract_metadata("The internship will be 3-6 months, including the summer.")["program_date_or_timeline"], "3-6 months")

    def test_summary_and_eligibility_skip_headings(self):
        description = "Your five-day pathway to an internship\nFutureFocus is a five-day discovery program for students interested in quantitative trading.\nWho is eligible for the program?"
        self.assertTrue(summary_from(description, "FutureFocus").startswith("FutureFocus is"))
        self.assertNotIn("Who is eligible", extract_metadata(description)["eligibility"])
        self.assertEqual(extract_metadata(description)["program_date_or_timeline"], "five-day discovery program")
        self.assertEqual(summary_from("Please only apply to one of our Job Postings.\nYou will research systematic trading strategies with our team.", "Quant Research Intern"), "You will research systematic trading strategies with our team.")
        self.assertEqual(summary_from("If you would like to be considered for our London internship, applications will open in September.\nJoin our nine-week trading internship in Amsterdam, where you will learn options market making.", "Amsterdam Trader Intern"), "Join our nine-week trading internship in Amsterdam, where you will learn options market making.")

    def test_card_scope(self):
        html = '''<main><article><h3>Quantitative Trader Intern</h3><p>Students trade options.</p><a href="/jobs/1">Apply</a></article><article><h3>Quantitative Research Intern</h3><p>Application deadline: May 1, 2027</p><a href="/jobs/2">Apply</a></article></main>'''
        cards = html_cards(visible_soup(html), "https://example.com/students")
        self.assertEqual(len(cards), 2)
        self.assertNotIn("deadline", cards[0]["description"].lower())
        self.assertIn("deadline", cards[1]["description"].lower())

    def test_skip_story_department_and_filtered_search_links(self):
        html = '''<main><article><h3>Trading internship</h3><p>Students learn quantitative trading.</p><a href="/stories/trading-internship/">Read story</a></article><article><h3>Explore our trading internship</h3><p>Students learn quantitative trading.</p><a href="/departments/?dept=trading">Explore</a></article><article><h3>Career Kickstarter - Trading 2027</h3><p>Students learn trading.</p><a href="/jobs/?department=trading&department=technology">Apply</a></article></main>'''
        self.assertEqual(html_cards(visible_soup(html), "https://example.com/students"), [])

    def test_html_bytes_use_declared_encoding(self):
        html = '<meta charset="utf-8"><main><h1>FTTP</h1><p>Jane Street’s trading program for students.</p></main>'.encode()
        soup = visible_soup(html)
        self.assertIn("Street’s", soup.get_text())

    def test_greenhouse_escaped_html_is_decoded(self):
        site = {"firm": "Five Rings", "source": "Open Roles", "url": "https://job-boards.greenhouse.io/fiveringsllc", "kind": "greenhouse", "board": "fiveringsllc"}
        class Response:
            def raise_for_status(self):
                pass
            def json(self):
                return {"jobs": [{"id": 123, "title": "Quantitative Trader Intern", "content": "&lt;p&gt;Students trade options.&lt;/p&gt;", "absolute_url": "https://job-boards.greenhouse.io/fiveringsllc/jobs/123", "location": {"name": "Chicago"}}]}
        with patch("scraper.requests.get", return_value=Response()):
            cards, error = fetch_site(site)
        self.assertEqual(error, "")
        self.assertEqual(cards[0]["description"], "Students trade options.")

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

    def test_detail_page_dedupes_with_listing(self):
        listed = evaluate(card("Launchpad", "Second-year students explore quantitative trading.", "https://example.com/programs/launchpad"), {**SITE, "kind": "html"}, TODAY)
        detail_site = {**SITE, "kind": "detail", "source": "Launchpad", "url": "https://example.com/programs/launchpad"}
        detailed = evaluate(card("LAUNCHPAD", "Second-year students explore quantitative trading.", detail_site["url"]), detail_site, TODAY)
        records = []
        self.assertTrue(merge_discovery(records, listed, "2026-10-14"))
        self.assertFalse(merge_discovery(records, detailed, "2026-10-14"))
        self.assertEqual(len(records), 1)

    def test_delivery_state_cap_dry_run_and_no_repeat(self):
        site = dict(SITE)
        candidates = [card("Quantitative Research Intern", "Undergraduate students research trading signals.", "https://example.com/jobs/a"),
                      card("Quantitative Trader Intern", "Undergraduate students learn options trading.", "https://example.com/jobs/b")]
        with tempfile.TemporaryDirectory() as directory, patch.object(main, "fetch_site", return_value=(candidates, "")), patch.object(main, "MAX_ALERTS_PER_RUN", 1):
            path = str(Path(directory) / "seen.json")
            with patch.dict("os.environ", {"DRY_RUN": "true", "DISCORD_WEBHOOK_URL": ""}):
                stats = main.run([site], path)
            self.assertEqual(stats["previewed"], 2)
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

    def test_pending_not_sent_if_source_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "seen.json")
            item = evaluate(card("Quantitative Research Intern", "Students research trading signals."), SITE, TODAY)
            records = []
            merge_discovery(records, item, TODAY.isoformat())
            save_seen_items(path, records)
            with patch.object(main, "fetch_site", return_value=([], "HTTP 403")), patch.object(main, "send_discord_alert") as sender:
                stats = main.run([SITE], path)
            self.assertEqual(stats["not_seen"], 1)
            sender.assert_not_called()
            self.assertEqual(load_seen_items(path)[0]["status"], "pending")


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
