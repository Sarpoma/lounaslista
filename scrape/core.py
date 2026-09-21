"""Fetching and menu extraction. Standard library only."""
from __future__ import annotations

import html as _html
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

WEEKDAYS = ["maanantai", "tiistai", "keskiviikko", "torstai", "perjantai",
            "lauantai", "sunnuntai"]
WEEKDAY_LABEL = ["Maanantai", "Tiistai", "Keskiviikko", "Torstai", "Perjantai",
                 "Lauantai", "Sunnuntai"]

# A line is a day heading when it *starts* with a weekday name. Trailing junk
# ("Maanantai 21.9.", "MAANANTAI 10:30-14:00") is expected and ignored.
_HEADING = re.compile(r"^(%s)\b" % "|".join(WEEKDAYS), re.IGNORECASE)
_DATE = re.compile(r"(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{4})?")

# Lines that are never food.
_NOISE = re.compile(
    r"eväste|evästeit|cookie|tietosuoja|yhteystied|copyright|©|all rights|"
    r"seuraa meitä|facebook|instagram|lue lisää|katso lisää|siirry|"
    r"varaa pöytä|tilaa uutiskirje|hyväksy|asetukset|valikko|etusivu|"
    r"^\s*(ma|ti|ke|to|pe)\s*$|^\s*lounas\s*$|^\s*€?\s*[\d,.\s]+€?\s*$|"
    r"^\s*(avoinna|aukiolo)",
    re.IGNORECASE,
)

# Hitting one of these means the menu is over and the page furniture has
# started - stop the block rather than filtering the line and reading on.
_STOP = re.compile(
    r"^(allergeenit|aukioloaj|yhteystied|kaikki lounaat|tilaa |seuraa |lataa |"
    r"tilaisuudet|alennukset|etsitkö|klikkaa|kysy lisää|à?\s*la carte|"
    r"lounasbuffet|lounas\s+(ma|ti|ke|to|pe|arkisin)|"
    r"(ma|ti|ke|to|pe|la|su)\s*-\s*(ma|ti|ke|to|pe|la|su)\s*\d|"
    r"l\u00f6yd\u00e4t meid\u00e4t|varaa |palaute|"
    r"(lounas|keitto|salaatti)\w*\s*\d+[,.]\d{2}|"
    r"\d{5}\s+\w+|[\w.+-]+@[\w-]+\.\w+|\+?\d[\d\s()-]{7,}$)",
    re.IGNORECASE,
)

# A dish split across markup lines: "Kuohkea peruna-purjososekeitto L,G &"
_CONTINUES = re.compile(r"[&=+,/]\s*$|^\s*[&=]")

_BULLET = re.compile(r"^[\s •·*\-–—•\t]+")
_WS = re.compile(r"[\s ]+")


def fetch(url: str, *, timeout: int = 25, retries: int = 3) -> str:
    """GET a page as text, retrying transient failures with backoff."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "fi-FI,fi;q=0.9,en;q=0.6",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                charset = resp.headers.get_content_charset()
            if not charset:
                m = re.search(rb'charset=["\']?([\w-]+)', raw[:4096], re.I)
                charset = m.group(1).decode("ascii", "ignore") if m else "utf-8"
            return raw.decode(charset, errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            last = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"fetch failed for {url}: {last}")


def html_to_lines(markup: str) -> list[str]:
    """Flatten HTML to visible text lines, one per block/break element."""
    s = re.sub(r"(?is)<(script|style|noscript|svg|head)\b.*?</\1>", " ", markup)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|li|tr|h[1-6]|section|article|td|dt|dd|dl)\s*>", "\n", s)
    s = re.sub(r"(?i)<(li|dt|dd)\b[^>]*>", "\n", s)
    s = re.sub(r"(?s)<!--.*?-->", " ", s)
    s = re.sub(r"(?s)<[^>]+>", "", s)
    s = _html.unescape(s)

    out = []
    for raw in s.split("\n"):
        line = _WS.sub(" ", _BULLET.sub("", raw)).strip()
        if line:
            out.append(line)
    return out


def _headings(lines: list[str]) -> list[tuple[int, int]]:
    """(line index, weekday index) for every line that opens a day."""
    found = []
    for i, line in enumerate(lines):
        m = _HEADING.match(line)
        if m:
            found.append((i, WEEKDAYS.index(m.group(1).lower())))
    return found


def _best_run(found: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Pick the Mon->Fri sequence that looks like the real menu.

    Pages often name weekdays more than once (navigation, opening hours,
    a second week). Split the headings wherever the weekday stops advancing,
    then keep the longest resulting run.
    """
    if not found:
        return []
    runs, current = [], [found[0]]
    for prev, item in zip(found, found[1:]):
        if item[1] > prev[1]:
            current.append(item)
        else:
            runs.append(current)
            current = [item]
    runs.append(current)
    return max(runs, key=len)


@dataclass
class Day:
    weekday: int                 # 0 = Monday
    label: str
    date: str | None = None      # ISO, when the page states one
    items: list[str] = field(default_factory=list)


@dataclass
class Result:
    id: str
    name: str
    url: str
    area: str = ""
    hours: str = ""
    status: str = "ok"           # ok | empty | error
    error: str | None = None
    days: list[Day] = field(default_factory=list)


def _join_continuations(chunk: list[str]) -> list[str]:
    """Rejoin a dish that the markup broke across several lines."""
    out: list[str] = []
    for line in chunk:
        if out and _CONTINUES.search(out[-1]) and not _HEADING.match(line):
            out[-1] = f"{out[-1].rstrip()} {line.lstrip()}".replace("  ", " ")
        else:
            out.append(line)
    return out


def _clean_items(chunk: list[str], max_items: int, max_len: int) -> list[str]:
    items, seen = [], set()
    for line in _join_continuations(chunk):
        if _STOP.match(line):
            break
        if len(line) > max_len or len(line) < 3:
            continue
        if _NOISE.search(line):
            continue
        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        items.append(line)
        if len(items) >= max_items:
            break
    return items


def extract_week(
    markup: str,
    *,
    max_items: int = 12,
    max_len: int = 180,
    gap: int = 25,
    max_weekday: int = 4,
) -> list[Day]:
    """Pull one Mon-Fri menu out of a page.

    Works off the weekday headings rather than CSS selectors, so a site
    restyling its markup does not break the parser as long as it still
    prints "Maanantai" above Monday's food.
    """
    lines = html_to_lines(markup)
    run = _best_run(_headings(lines))
    if not run:
        return []

    days: list[Day] = []
    for pos, (idx, weekday) in enumerate(run):
        if weekday > max_weekday:
            break
        end = run[pos + 1][0] if pos + 1 < len(run) else min(len(lines), idx + gap)
        day = Day(weekday=weekday, label=WEEKDAY_LABEL[weekday])

        m = _DATE.search(lines[idx])
        tail = lines[idx + 1:end]
        if not m and tail:
            m = _DATE.fullmatch(tail[0].strip().rstrip("."))
            if m:
                tail = tail[1:]
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
            year = int(y) if y else date.today().year
            try:
                day.date = date(year, mo, d).isoformat()
            except ValueError:
                pass

        day.items = _clean_items(tail, max_items, max_len)
        days.append(day)

    return _trim_last(days)


def _trim_last(days: list[Day]) -> list[Day]:
    """Cut page furniture off the final day.

    Every other day is bounded by the next day's heading; the last one runs
    until the extractor gives up, so it tends to swallow whatever the page
    prints next. The other days say how long a day is here, so use them.
    """
    if len(days) >= 3:
        ref = max(len(d.items) for d in days[:-1])
        if len(days[-1].items) > ref:
            days[-1].items = days[-1].items[:ref]
    return days


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def dump(results: list[Result], path: str) -> dict:
    today = date.today()
    payload = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "weekStart": monday_of(today).isoformat(),
        "restaurants": [asdict(r) for r in results],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    return payload
