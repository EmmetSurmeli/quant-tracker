"""Conservative, listing-level relevance and explicit metadata extraction."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE = rf"(?:(?:early|mid|late|end of)\s+{MONTH}\s+\d{{4}}|{MONTH}\s+\d{{1,2}}(?:,?\s+\d{{4}})?|{MONTH}\s+\d{{4}}|\d{{1,2}}/\d{{1,2}}/\d{{2,4}})"
DATE_VALUE = re.compile(rf"\b(?:{DATE}\s*(?:-|–|—|to|through)\s*(?:{DATE}|\d{{1,2}}(?:,?\s+\d{{4}})?)|{DATE})\b", re.I)
DURATION = re.compile(
    r"\bover the course of (?:a few days|(?:one|two|three|\d+)\s*[- ]\s*(?:day|week|month)s?)\b"
    r"|\b(?:one|two|three|\d+)\s*[- ]\s*(?:day|week|month)s?\b"
    r"(?:\s+(?:summer\s+)?(?:internship|program|offsite|discovery)(?:\s+program)?(?:\s+followed by\s+\d+\s+weeks?)?)?"
    r"|\ba few days\b", re.I)
DEADLINE = re.compile(r"\b(?:apply by|apply before|application deadline|applications close|deadline|closes on|due by)\b", re.I)
TIMELINE = re.compile(r"\b(?:program dates?|event dates?|summit dates?|internship timeline|begins|starts on|runs from|week of|from)\b", re.I)
LOCATION = re.compile(r"^\s*(?:location|where)\s*:\s*(.+)$", re.I)
ELIGIBILITY = re.compile(r"\b(?:first[- ]year|second[- ]year|third[- ]year|fourth[- ]year|sophomore|freshman|junior|senior|undergraduates?|graduat(?:e|ion)\s+(?:date|year|between)|class of \d{4}|degree|bachelor|master|major(?:ing)? in|studying|pursuing|eligib(?:le|ility)|who (?:can|should) apply|must be|must have|open to|students interested in|students with)\b", re.I)
STRONG_QUANT = re.compile(r"\b(?:quant(?:itative)?|trading|trader|strats?|systematic|market\s*making|statistical\s*arbitrage|alpha\s*research)\b", re.I)
RESEARCH = re.compile(r"\b(?:research|researcher|machine learning|data science|portfolio)\b", re.I)
STUDENT = re.compile(r"\b(?:intern(?:ship)?s?|undergraduate|students?|first[- ]year|second[- ]year|sophomore|campus|early careers?)\b", re.I)
EVENT_STUDENT = re.compile(r"\b(?:undergraduates?|students?|first[- ]year|second[- ]year|sophomore|campus|early careers?)\b", re.I)
PROGRAM = re.compile(r"\b(?:program|summit|symposium|insight|immersion|discovery|discover|launchpad|futurefocus|kickstarter|event|competition|invitational|hackathon|fellowship)\b", re.I)
EVENT = re.compile(r"\b(?:summit|symposium|event|competition|invitational|hackathon|discover)\b", re.I)
EXCLUDED_TITLE = re.compile(r"\b(?:investment banking|wealth management|private banking|audit|tax|hr|human resources|recruit(?:ment|ing)|marketing|sales|compliance|legal|accounting|operations|administrative|customer support|phd[- ]only|experienced (?:hire|professional)|full[- ]time only)\b", re.I)
GENERIC_TECH = re.compile(r"\b(?:software engineer(?:ing)?|frontend|backend|devops|infrastructure|it support|cybersecurity)\b", re.I)
FULL_TIME_TITLE = re.compile(r"\b(?:full[- ]time|experienced|senior|principal|staff|director|vp)\b", re.I)
ROLE_STUDENT_TITLE = re.compile(r"\b(?:intern(?:ship)?|summer analyst)\b", re.I)
SPECIFIC_ELIGIBILITY = re.compile(r"\b(?:first[- ]year|second[- ]year|third[- ]year|fourth[- ]year|sophomore|freshman|junior|senior|graduat(?:e|ion)|class of|degree|bachelor|master|major|studying|pursuing|must be|must have|eligible|open to)\b", re.I)


def compact(value: str) -> str:
    return " ".join(value.split())


def value_after_trigger(lines: list[str], trigger: re.Pattern[str], value: re.Pattern[str]) -> str:
    for index, line in enumerate(lines):
        match = trigger.search(line)
        if not match:
            continue
        found = value.search(line[match.end():])
        if found:
            return compact(found.group(0)).strip(" -:,.;")[:140]
        if index + 1 < len(lines) and len(lines[index + 1]) < 150:
            found = value.search(lines[index + 1])
            if found:
                return compact(found.group(0)).strip(" -:,.;")[:140]
    return ""


def extract_metadata(description: str, location_hint: str = "") -> dict[str, str]:
    lines = [compact(line) for line in description.splitlines() if compact(line)]
    deadline = value_after_trigger(lines, DEADLINE, DATE_VALUE)
    timeline = value_after_trigger(lines, TIMELINE, DATE_VALUE) or value_after_trigger(lines, TIMELINE, DURATION)
    if not timeline:
        for line in lines:
            range_match = DATE_VALUE.search(line)
            if range_match and len(line) < 110 and (re.search(r"(?:-|–|—|\bto\b|\bthrough\b)", range_match.group(0), re.I)
                                                   and re.match(r"^(?:from\s+)?" + MONTH, line, re.I)):
                timeline = compact(range_match.group(0))
                break
            if DURATION.search(line) and (re.search(r"\b(?:program|internship|summit|event|offsite|discovery)\b", line, re.I)
                                          or re.search(r"\b(?:over the course of|a few days)\b", line, re.I)):
                timeline = compact(DURATION.search(line).group(0)).strip(" -:,.;")[:140]
                break
    eligibility_matches: list[tuple[int, str]] = []
    for line in lines:
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            if ELIGIBILITY.search(sentence) and len(sentence) <= 260 and sentence not in [part for _, part in eligibility_matches]:
                eligibility_matches.append((2 if SPECIFIC_ELIGIBILITY.search(sentence) else 1, sentence))
    eligibility_parts = [part for _, part in sorted(eligibility_matches, key=lambda match: -match[0])[:3]]
    location = location_hint
    if not location:
        for line in lines:
            match = LOCATION.match(line)
            if match:
                location = compact(match.group(1))[:120]
                break
    return {"application_deadline": deadline,
            "program_date_or_timeline": timeline,
            "eligibility": " ".join(eligibility_parts)[:420],
            "location": location}


def summary_from(description: str, title: str) -> str:
    for line in description.splitlines():
        cleaned = compact(line)
        if cleaned.lower() == title.lower() or len(cleaned) < 35:
            continue
        if cleaned.lower() in {"apply now", "learn more", "read more"}:
            continue
        sentence = re.split(r"(?<=[.!?])\s+", cleaned)[0]
        return sentence[:237].rstrip() + ("..." if len(sentence) > 240 else "")
    return ""


def classify(title: str, description: str) -> str:
    if ROLE_STUDENT_TITLE.search(title):
        return "Internship"
    if EVENT.search(title):
        return "Event"
    return "Program"


def is_past(item: dict[str, str], today: date) -> bool:
    """Reject only explicitly dated prior-year opportunities; never infer a date."""
    text = " ".join((item.get("title", ""), item.get("application_deadline", ""),
                     item.get("program_date_or_timeline", "")))
    years = [int(year) for year in re.findall(r"\b20\d{2}\b", text)]
    return bool(years and max(years) < today.year)


def evaluate(candidate: dict[str, str], site: dict[str, str], today: date | None = None) -> dict[str, Any] | None:
    title = compact(candidate.get("title", ""))
    description = candidate.get("description", "")
    context = candidate.get("context", "")
    if not title or not description:
        return None
    if EXCLUDED_TITLE.search(title) or FULL_TIME_TITLE.search(title):
        return None
    full = f"{title}\n{description}\n{context}"
    title_quant = STRONG_QUANT.search(title)
    body_quant = STRONG_QUANT.search(full)
    student = STUDENT.search(full)
    internship = ROLE_STUDENT_TITLE.search(title)
    program = PROGRAM.search(title) or (site.get("kind") in {"detail", "events"} and PROGRAM.search(full))
    if internship:
        # A generic SWE or banking internship does not become quant just because
        # the company description mentions trading or research somewhere.
        if GENERIC_TECH.search(title) and not title_quant:
            return None
        if not (title_quant or (RESEARCH.search(title) and body_quant)):
            return None
        kind = "Internship"
    elif program and student and body_quant:
        if GENERIC_TECH.search(title) and not title_quant:
            return None
        kind = classify(title, description)
        if kind == "Event" and not EVENT_STUDENT.search(description + "\n" + context):
            return None
    else:
        return None
    meta = extract_metadata(description, candidate.get("location", ""))
    if not meta["eligibility"] and context:
        meta["eligibility"] = extract_metadata(context)["eligibility"]
    opportunity = {
        "firm": site["firm"], "source": site["source"], "source_page_url": site["url"],
        "title_or_snippet": title[:180], "summary": summary_from(context or description, title),
        "url": candidate.get("url") or site["url"], "posting_id": candidate.get("posting_id", ""),
        "type": kind, "match_reason": "quant/trading role + internship" if kind == "Internship" else "student program/event + quant/trading focus",
        **meta,
    }
    if is_past({"title": title, **meta}, today or date.today()):
        return None
    return opportunity
