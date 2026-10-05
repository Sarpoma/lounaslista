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
# Aggregators write the partitive ("Maanantaina 5.10."), restaurants mostly
# write the nominative ("Maanantai 5.10."). Accept either.
_HEADING = re.compile(r"^(%s)(?:na)?\b" % "|".join(WEEKDAYS), re.IGNORECASE)
_DATE = re.compile(r"(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{4})?")

# Lines that are never food.
_NOISE = re.compile(
    r"eväste|evästeit|cookie|tietosuoja|yhteystied|copyright|©|all rights|"
    r"seuraa meitä|facebook|instagram|lue lisää|katso lisää|siirry|"
    r"varaa pöytä|tilaa uutiskirje|hyväksy|asetukset|valikko|etusivu|"
    r"^\s*(ma|ti|ke|to|pe)\s*$|^\s*lounas\s*$|^\s*€?\s*[\d,.\s]+€?\s*$|"
    r"katso p\u00e4iv\u00e4n lounaslista|lounaslista puuttuu|^~?\s*sis\.|"
    r"^\s*sis\u00e4lt\u00e4\u00e4 |salaattip\u00f6yd\u00e4n, juomat|"
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
_CONTINUES = re.compile(r"[&=+,/(]\s*$|^\s*[&=]|^\s*[A-Z]{1,2}(\s*,\s*[A-Z]{1,2})*\s*\)")

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


# "Menu 5.-9.10.2026" above a block of weekdays - the week those days belong
# to, when the days themselves carry no dates.
# Two shapes in the wild, and they must be tried in this order: the fuller
# one first, or "05.10.-09.10.2026" matches the shorter pattern at the wrong
# offset and reads the 10th as the week start.
_WEEK_RANGES = (
    # 05.10.-09.10.2026  - day and month on both sides
    re.compile(r"(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*[-\u2013\u2014]\s*"
               r"\d{1,2}\s*\.\s*\d{1,2}\s*\.\s*(\d{4})"),
    # 5.-9.10.2026       - month only on the end
    re.compile(r"(\d{1,2})\s*\.\s*[-\u2013\u2014]\s*\d{1,2}\s*\.\s*"
               r"(\d{1,2})\s*\.\s*(\d{4})"),
)


def _run_week(lines: list[str], start: int) -> date | None:
    """The week heading immediately above a run of weekdays, if there is one."""
    for i in range(max(0, start - 4), start):
        for pattern in _WEEK_RANGES:
            m = pattern.search(lines[i])
            if m:
                d, mo, y = (int(g) for g in m.groups())
                try:
                    return date(y, mo, d)
                except ValueError:
                    break
    return None


def _choose_run(lines: list[str],
                found: list[tuple[int, int]]) -> tuple[list[tuple[int, int]], date | None]:
    """Pick the Mon->Fri sequence that is actually this week's menu.

    Pages name weekdays more than once - navigation, opening hours, and
    sometimes a whole stale menu left above the current one. Split the
    headings wherever the weekday stops advancing, then choose between the
    runs: a dated week heading beats everything, because length alone once
    picked a nine-month-old menu that happened to come first in the markup.
    """
    if not found:
        return [], None
    runs, current = [], [found[0]]
    for prev, item in zip(found, found[1:]):
        if item[1] > prev[1]:
            current.append(item)
        else:
            runs.append(current)
            current = [item]
    runs.append(current)

    dated = [(r, w) for r in runs if (w := _run_week(lines, r[0][0]))]
    if dated:
        today = date.today()
        return min(dated, key=lambda rw: abs((rw[1] - today).days))
    return max(runs, key=len), None


@dataclass
class Day:
    weekday: int                 # 0 = Monday
    label: str
    date: str | None = None      # ISO, when the page states one
    items: list[str] = field(default_factory=list)


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_of(days: list[Day]) -> str | None:
    """The Monday the scraped dates point at, or None when the site prints
    no dates and there is nothing to check against."""
    mondays = [monday_of(date.fromisoformat(d.date)) for d in days if d.date]
    if not mondays:
        return None
    return max(set(mondays), key=mondays.count).isoformat()


@dataclass
class Result:
    id: str
    name: str
    url: str
    location: str = ""
    area: str = ""
    hours: str = ""
    status: str = "ok"           # ok | empty | error
    error: str | None = None
    week: str | None = None      # Monday the scraped dates say; None if undated
    image: str | None = None     # a menu published only as a picture
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
    run, run_week = _choose_run(lines, _headings(lines))
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
            if y:
                try:
                    day.date = date(int(y), mo, d).isoformat()
                except ValueError:
                    pass
            else:
                # Most sites print "5.10." with no year. Pick the year that
                # puts the date nearest today, so the turn of the year does
                # not read January's menu as eleven months stale.
                today, best = date.today(), None
                for cand in (today.year - 1, today.year, today.year + 1):
                    try:
                        c = date(cand, mo, d)
                    except ValueError:
                        continue
                    if best is None or abs((c - today).days) < abs((best - today).days):
                        best = c
                if best:
                    day.date = best.isoformat()

        if day.date is None and run_week is not None:
            day.date = (run_week + timedelta(days=weekday)).isoformat()

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


def dump(results: list[Result], path: str, generated_at: str | None = None,
         locations: list[dict] | None = None) -> dict:
    """Write menus.json. `generated_at` keeps an earlier stamp when nothing
    changed, so the file stays byte-identical and no commit is produced."""
    today = date.today()
    payload = {
        "generatedAt": generated_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        "weekStart": monday_of(today).isoformat(),
        "locations": locations or [],
        "restaurants": [asdict(r) for r in results],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    return payload
