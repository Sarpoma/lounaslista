"""One entry per restaurant.

`opts` tunes the generic weekday extractor in core.py. Add a `prepare`
callable only when a page needs narrowing before the generic pass.
"""
from __future__ import annotations

import re

RESTAURANTS = [
    {
        "id": "linkosuo",
        "name": "Linkosuo Linnakallio",
        "url": "https://linkosuo.fi/toimipaikka/linkosuo-linnakallio/",
        "area": "Linnakallio",
        "hours": "ma-pe 10:30-13:30",
        "opts": {"max_items": 12},
    },
    {
        "id": "tiina",
        "name": "Tiinan Kotiruoka",
        "url": "https://tiinankotiruoka.fi/lounas-linnakallio/",
        "area": "Linnakallio",
        "hours": "ma-pe 10:30-14:00",
        "opts": {"max_items": 12},
    },
    {
        "id": "nina",
        "name": "Ninan Keittiö",
        "url": "https://www.ninankeittio.fi/pirkkala-linnakallio-veho/",
        "area": "Linnakallio / Veho",
        "hours": "ma-pe 10:30-14:00",
        "opts": {"max_items": 10},
    },
    {
        "id": "stahlberg",
        "name": "Ståhlberg Jasperintie",
        "url": "https://stahlbergkahvilat.fi/lounasravintolat/jasperintie/",
        "area": "Jasperintie",
        "hours": "ma-pe 10:30-14:00",
        "opts": {"max_items": 10},
    },
    {
        "id": "rasavil",
        "name": "Ra-Sa-Vil",
        "url": "https://www.ra-sa-vil.fi/tampere",
        "area": "Tampere",
        "hours": "ma-pe",
        "opts": {"max_items": 10},
    },
    {
        "id": "bufferi",
        "name": "Ravintola Bufferi",
        "url": "https://bufferi.com/pirkkala/",
        "area": "Pirkkala",
        "hours": "ma-pe 10:30-14:00",
        "opts": {"max_items": 12},
    },
]


def by_id(rid: str) -> dict:
    for r in RESTAURANTS:
        if r["id"] == rid:
            return r
    raise KeyError(rid)
