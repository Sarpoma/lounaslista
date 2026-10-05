"""Restaurants, grouped by the office they are walkable from.

`opts` tunes the generic weekday extractor in core.py. `handler` names a
strategy in handlers.py for the sites that do not publish a weekday-headed
page; without it a restaurant is read straight off its own HTML.
"""
from __future__ import annotations

LOCATIONS = [
    {"id": "linnakallio", "name": "Linnakallio"},
    {"id": "juhanilantie", "name": "Juhanilantie"},
]

RESTAURANTS = [
    # --- Linnakallio ------------------------------------------------------
    {
        "id": "linkosuo", "location": "linnakallio",
        "name": "Linkosuo Linnakallio",
        "url": "https://linkosuo.fi/toimipaikka/linkosuo-linnakallio/",
        "area": "Linnakallio", "hours": "ma-pe 10:30-13:30",
        "opts": {"max_items": 12},
    },
    {
        "id": "tiina", "location": "linnakallio",
        "name": "Tiinan Kotiruoka",
        "url": "https://tiinankotiruoka.fi/lounas-linnakallio/",
        "area": "Linnakallio", "hours": "ma-pe 10:30-14:00",
        "opts": {"max_items": 12},
    },
    {
        "id": "nina", "location": "linnakallio",
        "name": "Ninan Keittiö",
        "url": "https://www.ninankeittio.fi/pirkkala-linnakallio-veho/",
        "area": "Linnakallio / Veho", "hours": "ma-pe 10:30-14:00",
        "opts": {"max_items": 10},
    },
    {
        "id": "stahlberg", "location": "linnakallio",
        "name": "Ståhlberg Jasperintie",
        "url": "https://stahlbergkahvilat.fi/lounasravintolat/jasperintie/",
        "area": "Jasperintie", "hours": "ma-pe 10:30-14:00",
        "opts": {"max_items": 10},
    },
    {
        "id": "rasavil", "location": "linnakallio",
        "name": "Ra-Sa-Vil",
        "url": "https://www.ra-sa-vil.fi/tampere",
        "area": "Tampere", "hours": "ma-pe",
        "opts": {"max_items": 10},
    },
    {
        "id": "bufferi", "location": "linnakallio",
        "name": "Ravintola Bufferi",
        "url": "https://bufferi.com/pirkkala/",
        "area": "Pirkkala", "hours": "ma-pe 10:30-14:00",
        "opts": {"max_items": 12},
    },

    # --- Juhanilantie (Vantaa) -------------------------------------------
    {
        "id": "clove", "location": "juhanilantie",
        "name": "Clove",
        "url": "https://clove.fi/lounas",
        "area": "Vantaa", "hours": "ma-pe",
        "opts": {"max_items": 10},
    },
    {
        "id": "lumo", "location": "juhanilantie",
        "name": "Lumo Lounasravintola",
        "url": "https://ravintolalumo.fi/",
        "area": "Tuupakankuja 1", "hours": "ma-pe 10:00-13:30",
        "opts": {"max_items": 10},
    },
    {
        "id": "kuumakauha", "location": "juhanilantie",
        "name": "KuumaKauha",
        "url": "https://kuumakauha.fi",
        "area": "Vantaa", "hours": "ma-pe",
        "opts": {"max_items": 10},
    },
    {
        "id": "antell", "location": "juhanilantie",
        "name": "Antell Kehämylly",
        "url": "https://www.lounaat.info/lounas/antell-kehamylly/vantaa",
        "area": "Vantaankoskentie 14", "hours": "ma-pe 10:30-13:00",
        "opts": {"max_items": 10},
    },
    {
        "id": "maria", "location": "juhanilantie",
        "name": "Ravintola La Maria",
        "url": "https://ravintolalamaria.fi/",
        "area": "Kalustetie 1", "hours": "ma-pe 10:00-16:00",
        "handler": "maria_json",
    },
    {
        "id": "fajo", "location": "juhanilantie",
        "name": "Pegasus Fajo",
        "url": "https://www.pegasus-ravintolat.fi/pegasus-fajo-lounas-vantaa",
        "area": "Suokallionkuja 2", "hours": "ma-pe 10:30-14:00",
        "handler": "fajo_image",
    },
    # Both render their menus in the browser and are carried by no aggregator
    # we may use (lounasnyt.fi has an API but disallows /api/ in robots.txt,
    # and does not list either of them anyway). A link beats a blank card.
    {
        "id": "maggadu", "location": "juhanilantie",
        "name": "Ravintola Maggadu",
        "url": "https://foodzone.fi/vantaa/ravintolamaggadu/lunch",
        "area": "Tulkintie 29", "hours": "ma-pe 10:30-14:00",
        "handler": "link_only",
    },
    {
        "id": "fuudii", "location": "juhanilantie",
        "name": "Lounasravintola Fuudii",
        "url": "https://fuudii.fi",
        "area": "Vantaa", "hours": "ma-pe",
        "handler": "link_only",
    },
]


def by_id(rid: str) -> dict:
    for r in RESTAURANTS:
        if r["id"] == rid:
            return r
    raise KeyError(rid)
