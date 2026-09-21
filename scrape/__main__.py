"""Scrape every restaurant and write data/menus.json.

    python3 -m scrape                 # fetch live
    python3 -m scrape --offline DIR   # reparse saved <id>.html files
    python3 -m scrape --only bufferi  # one restaurant
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time

from .core import Day, Result, dump, extract_week, fetch
from .restaurants import RESTAURANTS

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "menus.json"


def load_previous() -> dict[str, dict]:
    """Last run's menus, keyed by restaurant id, for fallback on failure."""
    try:
        with open(OUT, encoding="utf-8") as fh:
            return {r["id"]: r for r in json.load(fh).get("restaurants", [])}
    except (OSError, ValueError, KeyError):
        return {}


def result_from_dict(d: dict) -> Result:
    days = [Day(**x) for x in d.get("days", [])]
    return Result(**{k: v for k, v in d.items() if k != "days"}, days=days)


def scrape_one(spec: dict, markup: str) -> Result:
    result = Result(
        id=spec["id"], name=spec["name"], url=spec["url"],
        area=spec.get("area", ""), hours=spec.get("hours", ""),
    )
    result.days = extract_week(markup, **spec.get("opts", {}))
    if not any(d.items for d in result.days):
        result.status = "empty"
        result.error = "no menu items found on the page"
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="scrape")
    ap.add_argument("--offline", metavar="DIR", help="parse saved <id>.html instead of fetching")
    ap.add_argument("--only", metavar="ID", action="append", help="limit to these ids")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between requests")
    args = ap.parse_args(argv)

    specs = RESTAURANTS
    if args.only:
        specs = [r for r in specs if r["id"] in set(args.only)]
        if not specs:
            print(f"no restaurant matches {args.only}", file=sys.stderr)
            return 2

    previous = load_previous()
    results: list[Result] = []

    for i, spec in enumerate(specs):
        if args.offline:
            markup = (pathlib.Path(args.offline) / f"{spec['id']}.html").read_text(
                encoding="utf-8", errors="replace")
        else:
            if i:
                time.sleep(args.delay)      # be a considerate visitor
            try:
                markup = fetch(spec["url"])
            except Exception as exc:        # noqa: BLE001 - one site must not sink the rest
                markup = None
                print(f"  ! {spec['name']}: {exc}", file=sys.stderr)

        if markup is None:
            result = Result(
                id=spec["id"], name=spec["name"], url=spec["url"],
                area=spec.get("area", ""), hours=spec.get("hours", ""),
                status="error", error="site unreachable",
            )
        else:
            result = scrape_one(spec, markup)

        # A site that changed shape should not blank the page - keep what we
        # had and let the badge say it is stale.
        if result.status != "ok" and spec["id"] in previous:
            stale = previous[spec["id"]]
            if any(d.get("items") for d in stale.get("days", [])):
                result.days = [Day(**d) for d in stale["days"]]
                result.status = "stale"
                result.error = "could not re-read the site; showing the last menu we got"

        results.append(result)
        count = sum(len(d.items) for d in result.days)
        mark = {"ok": "✓", "stale": "~", "empty": "!", "error": "✗"}[result.status]
        print(f"  {mark} {result.name}: {len(result.days)} days, {count} items")

    ok = sum(r.status == "ok" for r in results)
    scraped = {r.id: r for r in results}

    # Keep the untouched restaurants (--only) rather than writing them away.
    merged = []
    for spec in RESTAURANTS:
        if spec["id"] in scraped:
            merged.append(scraped[spec["id"]])
        elif spec["id"] in previous:
            merged.append(result_from_dict(previous[spec["id"]]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = dump(merged, OUT)

    print(f"\n{ok}/{len(results)} ok -> {OUT.relative_to(ROOT)} "
          f"(week of {payload['weekStart']})")

    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(f"\n### Lounaslista\n\n{ok}/{len(results)} restaurants ok\n\n")
            for r in results:
                note = f" - {r.error}" if r.error else ""
                fh.write(f"- **{r.name}**: {r.status}{note}\n")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
