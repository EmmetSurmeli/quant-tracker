"""Fetch public ATS feeds or extract self-contained HTML opportunity cards."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from config import REQUEST_TIMEOUT_SECONDS, USER_AGENT

HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json"}
CARD_HINT = re.compile(r"job|career|opening|position|program|event|intern|role", re.I)
BAD_LINK = re.compile(r"mailto:|tel:|javascript:|\.pdf(?:$|\?)", re.I)


def clean(value: str) -> str:
    return " ".join(value.split())


def lines(tag: Tag) -> str:
    return "\n".join(dict.fromkeys(
        text for text in (clean(s) for s in tag.stripped_strings) if text
    ))


def visible_soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template", "nav", "footer", "header"]):
        tag.decompose()
    return soup


def card_for(anchor: Tag) -> Tag:
    """Find the smallest useful container around a listing link."""
    for parent in list(anchor.parents)[:5]:
        if not isinstance(parent, Tag) or parent.name in {"body", "main", "html"}:
            break
        content = lines(parent)
        classes = " ".join(parent.get("class", []))
        has_heading = parent.find(re.compile("^h[2-6]$")) is not None
        if (parent.name in {"article", "li"} or CARD_HINT.search(classes) or has_heading) and 20 <= len(content) <= 1600:
            return parent
    return anchor


def html_cards(soup: BeautifulSoup, source_url: str) -> list[dict[str, str]]:
    root = soup.find("main") or soup.body or soup
    cards: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    source_host = urlparse(source_url).hostname or ""
    for anchor in root.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        if not href or BAD_LINK.search(href) or href.startswith("#"):
            continue
        target = urljoin(source_url, href)
        host = urlparse(target).hostname or ""
        if host != source_host and not any(x in host for x in ("greenhouse.io", "lever.co", "workdayjobs.com")):
            continue
        card = card_for(anchor)
        heading = card.find(re.compile("^h[1-6]$")) if card is not anchor else None
        title = clean(heading.get_text(" ", strip=True) if heading else anchor.get_text(" ", strip=True))
        description = lines(card)
        if not title or len(title) > 140 or len(description) > 1600:
            continue
        # A link should look like an opportunity, not a global navigation link.
        if not (CARD_HINT.search(target) or CARD_HINT.search(title) or CARD_HINT.search(description[:220])):
            continue
        if title.lower() in {"apply", "apply now", "learn more", "read more", "explore further"}:
            if not heading:
                continue
        key = (target.rstrip("/").lower(), title.lower())
        if key in seen:
            continue
        seen.add(key)
        cards.append({"title": title, "description": description, "url": target, "posting_id": "", "location": ""})
    return cards


def detail_card(soup: BeautifulSoup, site: dict[str, str]) -> list[dict[str, str]]:
    root = soup.find("main") or soup.body or soup
    heading = root.find("h1")
    title = clean(heading.get_text(" ", strip=True) if heading else site["source"])
    description = lines(root)
    if not description or len(description) < 40:
        return []
    return [{"title": title, "description": description[:12000], "url": site["url"], "posting_id": "", "location": ""}]


def event_cards(soup: BeautifulSoup, site: dict[str, str]) -> list[dict[str, str]]:
    root = soup.find("main") or soup.body or soup
    page_text = lines(root)
    # Shared introduction is used for relevance only, never for dates/eligibility.
    shared = page_text[:6000]
    cards: list[dict[str, str]] = []
    for heading in root.find_all(re.compile("^h[2-5]$")):
        title = clean(heading.get_text(" ", strip=True))
        if not re.search(r"discover|summit|symposium|invitational|event|competition", title, re.I):
            continue
        pieces = [title]
        for sibling in heading.next_elements:
            if isinstance(sibling, Tag) and re.fullmatch(r"h[2-5]", sibling.name or ""):
                if sibling.name <= heading.name or re.search(r"discover|summit|symposium|event", sibling.get_text(" ", strip=True), re.I):
                    break
            if isinstance(sibling, str):
                part = clean(sibling)
                if part and part != title:
                    pieces.append(part)
            if sum(map(len, pieces)) > 1200:
                break
        section = "\n".join(pieces)
        if "deadline" not in section.lower() and "date" not in section.lower():
            continue
        cards.append({"title": title, "description": section[:1600], "context": shared,
                      "url": site["url"], "posting_id": "", "location": ""})
    return cards


def fetch_site(site: dict[str, str]) -> tuple[list[dict[str, str]], str]:
    """Return (listing candidates, error). One failed site never stops the run."""
    kind = site.get("kind", "html")
    url = site["url"]
    if kind == "greenhouse":
        request_url = f"https://boards-api.greenhouse.io/v1/boards/{site['board']}/jobs?content=true"
    elif kind == "lever":
        request_url = f"https://api.lever.co/v0/postings/{site['board']}?mode=json"
    else:
        request_url = url
    try:
        response = requests.get(request_url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        if kind == "greenhouse":
            jobs = response.json()["jobs"]
            return [{"title": clean(job.get("title", "")),
                     "description": lines(visible_soup(job.get("content") or "")),
                     "url": job.get("absolute_url") or url,
                     "posting_id": f"greenhouse:{site['board']}:{job['id']}",
                     "location": clean((job.get("location") or {}).get("name", ""))}
                    for job in jobs if job.get("id")], ""
        if kind == "lever":
            jobs = response.json()
            cards = []
            for job in jobs:
                if not job.get("id"):
                    continue
                parts = [job.get("descriptionPlain", ""), job.get("additionalPlain", "")]
                parts.extend(section.get("content", "") for section in job.get("lists", []))
                description = "\n".join(lines(visible_soup(part)) for part in parts if part)
                cards.append({"title": clean(job.get("text", "")), "description": description,
                              "url": job.get("hostedUrl") or url,
                              "posting_id": f"lever:{site['board']}:{job['id']}",
                              "location": clean((job.get("categories") or {}).get("location", ""))})
            return cards, ""
        soup = visible_soup(response.text)
        if kind == "detail":
            return detail_card(soup, site), ""
        if kind == "events":
            return event_cards(soup, site), ""
        return html_cards(soup, url), ""
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        return [], f"{type(exc).__name__}: {exc}"
