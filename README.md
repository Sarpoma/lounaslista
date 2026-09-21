# Lounaslista

Lunch menus from six restaurants around Linnakallio, Pirkkala and Tampere,
collected onto one page.

The menus are scraped **on a schedule by GitHub Actions**, not in the browser.
The scraper commits `data/menus.json`, and the page just reads that file. This
sidesteps CORS entirely (none of the six sites send permissive CORS headers),
keeps the page fast, and means one visit per restaurant per run instead of one
per visitor.

## Restaurants

| Restaurant | Area | Source |
|---|---|---|
| Linkosuo Linnakallio | Linnakallio | [linkosuo.fi](https://linkosuo.fi/toimipaikka/linkosuo-linnakallio/) |
| Tiinan Kotiruoka | Linnakallio | [tiinankotiruoka.fi](https://tiinankotiruoka.fi/lounas-linnakallio/) |
| Ninan Keittiö | Linnakallio / Veho | [ninankeittio.fi](https://www.ninankeittio.fi/pirkkala-linnakallio-veho/) |
| Ståhlberg Jasperintie | Jasperintie | [stahlbergkahvilat.fi](https://stahlbergkahvilat.fi/lounasravintolat/jasperintie/) |
| Ra-Sa-Vil | Tampere | [ra-sa-vil.fi](https://www.ra-sa-vil.fi/tampere) |
| Ravintola Bufferi | Pirkkala | [bufferi.com](https://bufferi.com/pirkkala/) |

All six serve their menus in server-rendered HTML, and all six allow this in
`robots.txt`.

## Running it locally

No dependencies — Python 3.11+ standard library only.

```bash
python3 -m scrape          # fetch all six, write data/menus.json
python3 -m http.server 8000   # then open http://localhost:8000
```

Useful flags while developing a parser:

```bash
python3 -m scrape --only bufferi     # just one restaurant
python3 -m scrape --offline saved/   # reparse saved <id>.html, no network
```

## How the parsing works

There are no per-site CSS selectors. `scrape/core.py` flattens the HTML to text
lines and then finds the lines that *start* with a Finnish weekday, treating
everything between one weekday and the next as that day's food. A site can
restyle its markup completely and the parser keeps working, as long as it still
prints "Maanantai" above Monday's list.

Three details make that hold up in practice:

- **Picking the right run of weekdays.** Pages name weekdays in navigation and
  opening hours too, so the headings are split wherever the weekday stops
  advancing, and the longest Mon-to-Fri run wins.
- **Bounding the last day.** Friday has no following heading, so it tends to
  swallow the page footer. The other four days establish how long a day is
  here, and Friday is trimmed to match.
- **Rejoining split dishes.** A dish broken across markup lines (`"... &"`) is
  glued back together.

`scrape/restaurants.py` holds the list of sites and a small `opts` dict each.
Adding a restaurant usually means adding one entry there and nothing else.

## When a site breaks

Scrapers rot; sites get redesigned. Two things limit the damage:

- A restaurant that fails keeps its **previous menu**, flagged `stale` in the
  JSON and badged "Vanha tieto" on the page. One broken site never blanks the
  others.
- Each run writes a summary to the Actions run page listing every restaurant
  and its status, so a break is visible without reading logs.

To investigate, save the page and iterate offline:

```bash
curl -sL https://bufferi.com/pirkkala/ -o saved/bufferi.html
python3 -m scrape --offline saved/ --only bufferi
```

## Deploying to GitHub Pages

1. Push this repo to GitHub.
2. **Settings → Pages → Source: Deploy from a branch**, branch `main`, folder
   `/ (root)`.
3. **Settings → Actions → General → Workflow permissions**: *Read and write*,
   so the scheduled run can commit `data/menus.json`.

The workflow runs at 06:10 and 09:10 Helsinki time on weekdays, and can be run
by hand from the Actions tab.

Two things worth knowing about scheduled Actions: GitHub **disables cron
workflows in repos with no pushes for 60 days** (it emails first — any commit
re-arms it), and scheduled runs can lag the requested time by 10–20 minutes
under load. Neither matters much for lunch.

## Layout

```
scrape/core.py          fetching, HTML flattening, weekday extraction
scrape/restaurants.py   the six sites
scrape/__main__.py      runner; writes data/menus.json
data/menus.json         scraper output, committed
index.html assets/      the page: no build step, no dependencies
```
