"""Per-site fetch strategies.

Most restaurants publish a weekday-headed page that core.extract_week reads
directly, so they need nothing here. These are the ones that do not.
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import date

from .core import UA, Day, WEEKDAY_LABEL, fetch

# --- La Maria -------------------------------------------------------------
# A React app with no server-rendered menu, but its bundle pointed at a public
# JSON API, which is steadier than any amount of HTML parsing.
MARIA_API = "https://api.ravintolalamaria.fi/api/menu"
_DAY_KEYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]


def maria_json(spec: dict) -> dict:
    req = urllib.request.Request(MARIA_API, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        payload = json.load(resp)

    current = payload.get("current") or {}
    week_no = payload.get("current_week")
    monday = None
    if isinstance(week_no, int):
        try:
            monday = date.fromisocalendar(date.today().year, week_no, 1)
        except ValueError:
            monday = None

    days: list[Day] = []
    for i, key in enumerate(_DAY_KEYS):
        items = []
        for dish in (current.get(key) or {}).get("dishes") or []:
            name = ((dish.get("fi") or {}).get("name") or "").strip()
            if name:
                items.append(name)
        days.append(Day(
            weekday=i,
            label=WEEKDAY_LABEL[i],
            date=date.fromordinal(monday.toordinal() + i).isoformat() if monday else None,
            items=items,
        ))
    return {"days": days}


# --- Pegasus Fajo ---------------------------------------------------------
# Publishes the week as a single image. The <img id="buffet"> hook is stable
# even though the filename changes every week, and the filename carries the
# week number ("fajo ig vko 41.png"), which is what lets the staleness check
# cover an image the same way it covers text.
_BUFFET_IMG = re.compile(r'<img[^>]*\bid="buffet"[^>]*>', re.IGNORECASE)
_SRC = re.compile(r'\bsrc="([^"]+)"', re.IGNORECASE)
_VKO = re.compile(r"vko[%\s_-]*(\d{1,2})", re.IGNORECASE)


def fajo_image(spec: dict) -> dict:
    markup = fetch(spec["url"])
    tag = _BUFFET_IMG.search(markup)
    if not tag:
        return {"days": [], "error": "no <img id=\"buffet\"> on the page"}

    src = _SRC.search(tag.group(0))
    if not src:
        return {"days": [], "error": "buffet image has no src"}

    url = src.group(1)
    week = None
    m = _VKO.search(urllib.request.unquote(url))
    if m:
        try:
            week = date.fromisocalendar(date.today().year, int(m.group(1)), 1).isoformat()
        except ValueError:
            pass
    return {"days": [], "image": url, "week": week}


# --- Link-only ------------------------------------------------------------
# Maggadu and Fuudii render their menus in the browser and are carried by no
# aggregator we may use, so the honest thing is to say so and link out rather
# than show a stale or empty card.
def link_only(spec: dict) -> dict:
    return {"days": [], "status": "link"}


HANDLERS = {"maria_json": maria_json, "fajo_image": fajo_image, "link_only": link_only}
