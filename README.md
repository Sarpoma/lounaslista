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

The eight restaurants around the Juhanilantie office in Vantaa are less
uniform. Most publish weekday-headed HTML like the Linnakallio six; La Maria
is read from a JSON API its own bundle pointed at; Pegasus Fajo publishes the
week as a single image, shown inline and enlarged on tap; and Maggadu renders
only in the browser and is carried by no aggregator we may use, so it gets a
card that says so and links out.

Not every page is UTF-8. Fuudii is served as ISO-8859-1 with no declared
charset at all, so `core.decode` tries strict UTF-8 first and falls back to
cp1252 rather than quietly replacing every umlaut.

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

## Commits, and what "stale" means

A run only commits when the **menus** change. `generatedAt` is deliberately
carried over from the previous run when the scraped content is identical, so
the file stays byte-identical and produces no commit — otherwise the moving
timestamp alone would mean two empty commits a day, every day.

That makes the timestamp mean "when the food last changed" rather than "when
we last looked", so the page does not use it to judge staleness. Two narrower
signals do that instead, and they catch different failures.

**`weekStart` — has anything run this week?** It is taken from the dates the
restaurants print, by majority, because that is evidence about the food
rather than about the clock. The clock is only the fallback when nothing is
dated, and on a weekend it points at the week about to start. If the page sees a `weekStart` from a week already gone, no run
has written the file this week and *everything* on display is old. The page
says so in a banner.

**`week` (per restaurant) — is this restaurant's food actually from this
week?** Derived from the dates the restaurant itself prints, so it is real
evidence rather than the runner's clock. A restaurant whose `week` disagrees
with `weekStart` is still serving an older menu, and gets a banner plus a
badge on its own card.

The second check matters because `weekStart` comes from the clock. A run that
fires before a restaurant has published the new week will happily stamp the
file "this week" over last week's food — and without `week` nothing would
notice. That risk grew when the schedule moved earlier, which is why the check
exists. It also makes a latched stale fallback visible instead of silent.

Only three of the six sites print dates. For the other three `week` is `null`
and there is nothing to check against; the page does not guess.

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

The workflow runs three times per weekday, plus three times on Sunday to pick
up next week's lists as soon as they appear. It can also be run by hand from
the Actions tab.

The cron times look absurdly early on purpose. **GitHub does not run scheduled
workflows on time.** Measured over three weeks on this repo, runs started
**5 to 7.5 hours** after the requested time, and the lag grew week on week:

| requested (UTC) | actually started (UTC) |
|---|---|
| 03:10 | 08:21 – 10:01 |
| 07:00 | 12:13 – 14:43 |

A schedule asking for 06:10 and 10:00 Helsinki was therefore delivering menus
at roughly 11:30 and 15:00 — during and after lunch. The fix is to ask for the
small hours and let the queue deliver before lunch, and to ask several times,
since a run that finds nothing new takes ~30s, commits nothing, and costs
nothing on a public repo.

Cron is UTC-only with no daylight-saving support, so every time above shifts
an hour in local terms when Finland leaves EEST at the end of October. With
three spread-out runs that no longer matters much.

Note that the workflow does **not** need the repository's "Workflow
permissions" set to read/write: `update.yml` declares `permissions: contents:
write` for itself, which takes precedence over the repo-wide default.

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
