# tripsite (v0)

Turns a trip profile (`trips/<trip>.md`) into a static, shareable trip page:
a Leaflet/OpenStreetMap map of our places plus toggleable popular places, a
day-by-day schedule, and an "About this trip" section.

CLI only. The output folder (`dist/`) *is* the export. No server, no UI.

## Usage

```bash
uv run tripsite/build.py trips/mexico-city-2026.md                 # build one trip
uv run tripsite/build.py trips/mexico-city-2026.md trips/lisbon.md # build several in one run
uv run tripsite/build.py trips/mexico-city-2026.md --dry-run       # validate only
uv run tripsite/build.py trips/mexico-city-2026.md --out /tmp/site
uv run tripsite/build.py trips/mexico-city-2026.md --refresh-transit  # re-fetch airport/metro
```

The build is offline apart from one step: a trip that asks for an `airport:` or a
`map: {metro: ...}` layer fetches that data from Overpass **once** and caches it under
`cache/tripsite/`. Every later build reads the cache and makes no request at all.

Writes:

| File | What |
|---|---|
| `dist/<slug>/index.html` | one trip page per trip file (single file, trip data embedded as JSON) |
| `dist/<slug>/metro.json` | **only** when a trip's metro geometry is too big to embed (>400 KB of JSON); the page then loads it on demand. Mexico City doesn't need one |
| `dist/index.html` | neutral "World Cities" placeholder (no trip listing, so slugs don't leak) |
| `dist/404.html` | neutral "Not found" page (noindex, no slugs). Without a top-level `404.html`, Cloudflare Pages treats the site as a single-page app and serves `index.html` with status 200 for every missing path; with it, a missing path gets a real 404 |
| `dist/robots.txt` | `Disallow: /` |
| `dist/_headers` | Cloudflare Pages headers: `X-Robots-Tag: noindex, nofollow` on every path |

**`dist/` holds exactly the trips passed on this run.** A Cloudflare Pages
direct upload is a full-site snapshot: whatever is in `dist/` becomes the whole
site, and anything missing from it is taken down. So:

- **Rebuild every live trip in the same run**, e.g.
  `uv run tripsite/build.py trips/mexico-city-2026.md trips/lisbon-2027.md`.
  (`trips/*.md` works too, but only if `trips/` holds live trips alone. Move
  finished trips to `trips/archive/` or they'll be published again.)
- Any `dist/<slug>/` folder that isn't in this run is **removed**, and the build
  prints the slugs left in `dist/`. `--dry-run` shows what would be removed.
- The build only removes things it wrote itself. Every page it writes carries
  `<meta name="generator" content="tripsite">`, and a stale trip folder is removed
  only if it holds nothing but an `index.html` with that marker in its `<head>`
  (plus an optional `metro.json` and `.DS_Store`). The marker in the page body or
  inside an HTML comment doesn't count. A folder without the marker or without an
  `index.html`, any
  symlink, or any other file stops the build: it is listed and nothing is deleted
  or written. Symlinks are never followed, written through or deleted. Every
  output is written to a temp file and then renamed into place, so a hardlinked
  output is replaced, never written through.
- Pages built before the marker existed (before 2026-09-18) don't have it.
  Rebuilding the same slug overwrites the old page as normal. An old *stale* folder
  is refused, so delete it by hand once.
- Every slug in `dist/` must have its own Access app before an upload (Gate 4, then Gate 5).

Both `dist/` and `trips/` are gitignored.

Preview (opening the file via `file://` may not load OSM tiles, because it sends no Referer):

```bash
python -m http.server -d dist
# open http://localhost:8000/<slug>/
```

`http.server` doesn't reproduce Cloudflare Pages' 404 handling (it never serves
`404.html` for a missing path), so it can't check the 404 behaviour. Gate 2's
verify does that on Pages.

Invalid profiles fail with every problem listed (missing fields, bad dates,
end before start, unknown place ids, bad or unquoted times, unknown theme,
out-of-range coordinates, duplicate YAML keys, `NO`/`yes`/`on` read as
true/false, a malformed or unresolvable IATA code). Events outside `start..end`
are dropped with a warning. If any trip in a run fails, nothing is written.

Tests: `uv run python -m unittest discover -s tripsite -p 'test_*.py' -v`
(the 7 "expected failure" results are the accepted limits below, not open bugs)

## Trip profile format

Markdown with YAML frontmatter. The body below the frontmatter becomes "About this trip".
The body supports basic Markdown only: headings, paragraphs, lists, `code`,
**bold**, *italic*, and http(s) links.

```yaml
---
trip:
  name: Mexico City 2026
  slug: mexico-city-2026-xxxx      # lowercase/digits/hyphens; add a random suffix of
                                   # your own. Never paste a live slug into this file:
                                   # the slug is the only thing guarding an unlisted page
  start: 2026-10-22                # YYYY-MM-DD
  end: 2026-10-31
  timezone: America/Mexico_City    # IANA name
  city: Mexico City
  country: Mexico                  # quote yes/no-like words: "NO" (Norway)
  center: {lat: 19.42, lon: -99.155}
  zoom: 12                         # 1..19
  theme: terracotta                # any themes/<name>.json (page colours only)
  airport: MEX                     # optional; IATA code, looked up once and cached
privacy:
  hotel_display: approximate       # exact | approximate | hidden
  noindex: true                    # pages are always noindex regardless
map:                               # optional reference layers
  metro: off                       # on | off. Absent = no metro layer at all
locations:                         # our places, always on the map
  - {id: hotel, name: ..., category: stay, address: ..., lat: .., lon: .., notes: .., url: https://..}
  - {id: aunts, name: ..., category: visit, private: true, address: ..., lat: .., lon: ..}
popular:                           # toggleable pins (checkbox per place + per category)
  - {id: zocalo, name: Zócalo, category: sight, lat: .., lon: .., default_on: true, url: .., notes: ..}
events:
  - date: 2026-10-31
    time: "12:00"                  # optional; QUOTE it. A bare number like 930 is rejected
    kind: city                     # plan (ours) | city (happening in town)
    name: Gran Desfile de Día de Muertos
    location: zocalo               # a place id, or {lat, lon, label}; optional
    booked: false                  # optional
    keep: true                     # optional; keep it even though it is outside start..end
    url: https://...               # optional; the thing itself (tickets, venue, museum)
    source: https://...            # optional; where the information came from
    notes: ...                     # optional
---
```

- Every **place** needs hand-entered `lat`/`lon`. The build never geocodes a place name.
  (`trip.airport` is the one exception, and it resolves an IATA *code*, not a name —
  see "Airport" below.)
- `category` is free text (lowercased). It groups the popular-places checkboxes and is
  shown in the map popup, capitalised — except for the few in `CATEGORY_LABELS`, which
  have a proper display name: `daytrip` reads **"Day trip"** in both places. A day-trip
  place keeps the ordinary blue "popular" marker; the category heading is the hint.
- Ids must be unique across `locations` and `popular`. Numeric ids work (`id: 1`, `location: 1`).
- `url`/`source` must be `http(s)://`. Anything else fails the build.
- Duplicate keys anywhere in the frontmatter are an error, not a silent overwrite.

### Events outside the trip dates (`keep`)

An event whose `date` falls outside `trip.start .. trip.end` is **dropped** with a
warning naming it — that is still the default, and the warning now says how to keep it.

With `keep: true` it is kept instead and rendered in its own section, **"Just outside
your dates"**, below the day-by-day list:

- sorted by date, each row showing its own date and weekday ("Sat 31 Oct"), plus the
  year when it isn't the trip's year;
- never inside a day group — the day list still covers only `start..end`;
- still pinned on the map, still clickable (⌖), still shows its `url` (`↗`), `source`
  and `notes`, exactly like an in-range event;
- subject to every privacy rule: a kept event within 400 m of a non-`exact` stay is
  treated as the stay (same warning, same map behaviour), and its text goes through the
  leak scan.

The section is not rendered at all when nothing was kept. On an event inside the dates
`keep` does nothing. Use it for the day after you fly home, or a parade you want on the
page even though you miss it.

### Links (`url` and `source`)

Both are optional, both are validated the same way, and both open in a new tab
(`target="_blank" rel="noopener noreferrer"`). They mean different things:

| Field | On | Means | Shown as |
|---|---|---|---|
| `url` | places (`locations`, `popular`) and events | **the thing itself** — the museum's own page, the venue, the ticket page | "Website" in the map popup; a small `↗` after the name in the side list and in the event row |
| `source` | events only | **where the information came from** — the listing or article you read the date and time in | "Source" in the event row and in the map popup |

If an event has both, the popup shows `Website · Source`.

The `↗` in the side lists is a plain `<a>` placed **outside** the checkbox `<label>`
and outside the pan-to-map `<button>`, so clicking it only follows the link: it never
toggles a popular place's checkbox and never moves the map. It is an ordinary anchor,
so it is reachable by Tab, and it carries an accessible label such as
"Open the Museo Frida Kahlo (Casa Azul) website in a new tab".

A stay's `url` is **never published** unless `hotel_display: exact` — see below.

### Airport (`trip.airport`)

Optional. A trip's airport is a **reference point, never a place**: it is not in
`locations` or `popular`, it can never be a stay, it takes no part in the privacy
rules or the leak scan, and it does not change the initial view (still
`trip.center`/`trip.zoom`).

```yaml
trip:
  airport: MEX                                              # short form: just the code
  airport: {code: MEX, name: Benito Juárez}                 # override the name only
  airport: {code: TLC, name: Toluca, lat: 19.337, lon: -99.566}   # no lookup at all
  airport: [MEX, {code: TLC, name: Toluca, lat: .., lon: ..}]     # a trip using two
```

- The code is upper-cased for you (`mex` works) and must be exactly three letters.
- **Coordinates come from Overpass**, matching `aeroway=aerodrome` + `iata=<CODE>` —
  never a guess. The answer is cached (below), so only the first build makes a request.
- `name` in the trip file always wins. Otherwise OSM's `name:en`, then `name`.
- If the code can't be resolved and you gave no `lat`/`lon`, **the build fails** and
  prints the line to paste in, with the coordinates spelled out. It never falls back to
  an approximate position.

On the page: an amber disc with a white plane, deliberately unlike the round place pins;
a popup with the name, `Airport · <CODE>` and a Google Maps link; its own legend entry;
and a single **Airport** checkbox under "Getting around" in the side panel, **on by
default** (it is a reference point, so it is more useful visible). "Show all places on
map" includes it.

### Metro lines (`map.metro`)

Optional, and **opt-in**: with no `map:` section there is no metro layer and no network
call. `metro: on` draws the lines at load; `metro: off` puts the layer and its checkbox
on the page with the lines hidden until asked for — that is the suggested default, so the
trip pins stay the focus. Switching between them is a one-word edit; nothing is re-fetched.

- Fetched from Overpass as subway **route relations** (`type=route` + `route=subway`)
  inside a square about 60 km across centred on `trip.center`, with member geometry
  inline (`out geom`).
- The two running directions of a line share the same `ref`, so they are merged into one
  entry, and their shared way geometry is de-duplicated. Platform and stop members are
  ignored — this is track, not furniture.
- Each line is drawn in its **official OSM `colour` tag**; a line without a usable hex
  colour falls back to a readable palette colour. Lines sort by number, then letter.
- Geometry is simplified with Douglas-Peucker at a 15 m tolerance (endpoints always kept)
  and rounded to 5 decimals. For Mexico City that is 12 lines and 938 points, ~21 KB of
  JSON, down from ~82 KB unsimplified.
- **One "Metro lines" checkbox** turns the whole network on or off, with a compact
  colour-chip legend of the line numbers beside it (each chip's tooltip is the full line
  name). The lines are drawn in their own map pane *below* the pins and are
  non-interactive, so they never cover a marker or swallow a click. They are deliberately
  **excluded from "Show all places on map"** — a 60 km network would zoom the trip away.
- **Stations are not drawn.** They are a second query and several hundred more points for
  something the base OSM tiles already label; interchanges alone would still need the
  station relations. Not worth the weight today.
- Any city with subway relations in OSM works. If the query returns nothing (no metro, or
  the wrong centre), the build **warns and carries on** with no layer — a missing
  reference overlay is never worth failing a build for. Same for an Overpass outage.

### Overpass, caching and page weight

Both lookups go to `https://overpass-api.de/api/interpreter` as **GET** requests, with a
named User-Agent, at least 1.1 s between requests, a patient timeout, and a backing-off
retry on 429 and 504 only. A build makes **at most one request per airport code plus one
per city**, and **none at all** once the cache is warm.

Everything fetched is cached under `cache/tripsite/` (gitignored, outside `dist/`):

| File | What |
|---|---|
| `airports.json` | one entry per IATA code: code, name, lat, lon, source, date |
| `metro-<city>-<hash>.json` | the **raw** Overpass response, keyed by city and rounded bounding box, with the query that produced it |

A miss is never cached, so fixing a typo'd code and rebuilding just works.
`--refresh-transit` ignores both caches and re-fetches.

```bash
uv run tripsite/build.py trips/mexico-city-2026.md --refresh-transit
```

**Page weight.** The metro geometry is embedded in the page while it stays under 400 KB
of JSON. Above that the build writes it to `dist/<slug>/metro.json` instead and the page
fetches it the first time the layer is switched on; the build prints which route it took,
and `metro.json` must then be uploaded with the page (see Gate 5). Mexico City is
~21 KB, so it is embedded and there is no sibling file.

For the Mexico City trip, adding the airport and the (default-off) metro layer took the
page from **28,966 to 58,040 bytes** raw, 16,279 bytes gzipped: ~21 KB of metro geometry,
~0.5 KB for the airport, and ~5.4 KB of layer code and CSS that is now present on every
trip page, layers or not.

### Privacy behaviour (stays)

A place is a **stay** if its `category` is one of `stay`, `hotel`, `lodging`,
`airbnb`, `accommodation` or `hostel` (any case), **or** if it has `private: true`.
Stays belong under `locations`. A stay under `popular` fails the build with
"put stays under locations".

| `hotel_display` | On the page |
|---|---|
| `exact` | normal marker with name, address, notes, Google Maps link |
| `approximate` | a 400 m circle whose **centre is moved 150–250 m** from the stay, in a direction derived from a hash of the slug, id, name and exact coordinates. The stay is always inside the circle but never near its centre. Focusing it never zooms past 14. **id, name, address, notes, url and the real category are removed** from the page. It is labelled "Where we’re staying" for a stay category, or "Private place" for anything else marked `private: true` (e.g. `aunts` above), and numbered if there are several of one kind ("Where we’re staying 1", "… 2"). |
| `hidden` | not on the page at all; events that pointed at it keep their text but lose the map link |

For a stay that isn't `exact`:

- An event with an inline `location: {lat, lon, label}` within 400 m of the stay is
  treated as the stay. Its coordinates and label are never published. Under
  `approximate` it points at the stay's circle; under `hidden` it loses its map
  link. You get a warning; use a place id if it really is somewhere else.
- The build warns if the stay's name or address appears in the body, an event,
  or another place's name/notes/address.
- The build warns (it doesn't fail) if a `popular` place is within 100 m of the
  stay, because its pin shows roughly where the stay is.
- **Final safety net:** after rendering, the page is scanned for the stay's name,
  street, postcode, url and coordinates (as a lat/lon pair at 4 or more decimals).
  Any hit fails the build and nothing is written.

The circle is the same on every rebuild (same slug, stay name and coordinates).
The code is public, so anyone who reads it knows the stay is 150–250 m from the
drawn centre, on a bearing 20–70° into one of the four quadrants. That puts the
stay in about 14% of the circle's area. The circle hides the building, not the
neighbourhood.

#### Known limits (accepted)

Rob accepted these on 2026-09-18: the sites are invite-only behind Cloudflare
Access, and it's fine if invitees know the hotel. The tests for them in
`test_qa_round2.py` stay marked as expected failures.

- **M1, the circle is an oracle.** Its position is a fixed function of the slug
  and the stay's id, name and coordinates exactly as typed. Someone who guesses
  all of those (e.g. id `hotel`, the hotel's name, coordinates copied from Google
  Maps) can recompute the circle from the public code and confirm the guess.
  Changing the slug, or the stay's name or coordinates, moves the circle, and
  anyone who saw both versions can overlap them to narrow the stay to about a
  60 m radius.
- **M2, the leak scan can be dodged.** It matches text literally, so it misses
  the stay's name when it's split by formatting (`**Casa** Pátzcuaro`), written
  without accents or with decomposed accents, or has doubled spaces. It also
  misses the street when the address has no commas or starts with a building
  name. It is a backstop: keep the stay's details out of the body, events and
  other places yourself.
- **L7, 3-decimal coordinates pass the leak scan.** The scan only flags the
  stay's coordinates at 4 or more decimals. The stay's coordinates rounded to 3
  decimals (about 100 m) deliberately pass, so a nearby pin or a body mention at
  3 decimals is not caught.

**Open interaction (metro layer × leak scan), not yet decided.** The coordinate half of
the leak scan flags any number on the page starting with the stay's latitude at 4 dp when
a number starting with its longitude at 4 dp sits within 80 characters. Metro geometry is
hundreds of 5-dp lat/lon pairs. So a **non-`exact`** stay within roughly 15 m of a metro
line's drawn geometry would make the build fail with "private stay coordinates appear on
the page" — a false positive (the vertex comes from OSM and says nothing about the stay),
but a confusing one. It is the safe direction to fail in, so nothing was changed. Checked
on 2026-09-20 against the live trip in all three `hotel_display` modes: no metro vertex
falls in either of the stay's 4-dp coordinate bands, and the leak scan reports no hits.
If it ever does bite, the choice is to exempt the metro block from the coordinate scan or
to set `map.metro` off for that trip — Rob's call, not the build's. (Distances between a
private stay and anything else stay out of this file: they narrow down where it is.)

Every page carries `noindex,nofollow` (meta tag and `X-Robots-Tag` header) and
`referrer: strict-origin-when-cross-origin`, so OSM and unpkg see only the
origin (`https://worldcities.ca`), never the slug path.

Map markers use a fixed palette that stays visible on OSM tiles in every theme:
our places red, popular places blue, event spots teal (one marker, reused), the
approximate stay area a purple circle with a dashed dark outline, and the airport
an amber disc with a white plane (a different *shape*, not just a different
colour, so it reads as "not one of our pins"). Metro lines are the exception that
proves the rule: they keep their own official OSM colours. The theme only colours
the page (header, panel, text). The legend under the map lists only the groups
that are on the page. The stay swatch has a white ring so its dashed edge also
shows on dark themes such as noir.

Third-party requests from the page: Leaflet 1.9.4 from unpkg (pinned with SRI
hashes) and map tiles from `tile.openstreetmap.org` (standard OSM tiles,
attributed, no prefetching). The favicon is inline, so it makes no request. The
airport and metro data are fetched **at build time**, not by the page, and are
embedded in it — so a visitor's browser never talks to Overpass. (The one
exception: if the metro geometry was too big to embed, the page fetches its own
`metro.json`, same origin.)

---

## Deploy (Rob runs these; nothing here has been run)

Target: Cloudflare Pages project `worldcities`, served on `worldcities.ca`,
each trip at `https://worldcities.ca/<slug>/`, behind Cloudflare Access (email one-time PIN).

**Order matters.** A trip page is uploaded only *after* Access protects its
path (Gate 4) **and** the `*.pages.dev` hostnames redirect to `worldcities.ca`
(Gate 3b). Until then, only the placeholder `index.html`, `404.html`,
`robots.txt` and `_headers` go up.

**Every upload replaces the whole site.** Build all live trips in one run
before every Gate 5 upload (see Usage).

Dashboard labels and Cloudflare behaviour below come from Rex's research
(2026-09-18). Gage hasn't checked them against the live dashboard. If a label
doesn't match, stop and paste what you see; don't guess.

```
GATE 1: Confirm worldcities.ca is an active zone on Cloudflare DNS   Plan ref: brief step 1
Class: DNS/zone (read-only)
Preconditions: none
Blast radius: none (read-only). Sibling projects in the worldcities.ca zone: unknown
  to Gage. Rob lists any existing records here; Gate 3 adds an apex record.
Do exactly (dashboard):
  dash.cloudflare.com › Websites (Domains) › worldcities.ca
  Status shows "Active".
  DNS › Records › Import and Export › Export  -> save the BIND file OUTSIDE the repo
    (e.g. ~/Backups/worldcities.ca-zone-<date>.txt)
Do exactly (CLI, read-only, from any terminal):
  dig +short NS worldcities.ca
Expect: two *.ns.cloudflare.com nameservers; dashboard status "Active".
Verify: the NS answer matches the nameservers shown on the zone's Overview page.
Rollback card: N/A (read-only).
Paste back: dig output, zone status, and the list of existing apex / www records
  (from the export) so Gage can write Gate 3's blast radius.
```

```
GATE 2: Create Pages project "worldcities" with the placeholder only (direct upload)
Plan ref: brief step 2
Class: deploy
Preconditions: local build output (see "Verified locally" in Gage's report);
  uv run tripsite/build.py trips/mexico-city-2026.md exits 0.
Blast radius: creates a new Pages project and its *.pages.dev hostname. No zone changes.
  Only index.html, 404.html, robots.txt and _headers are uploaded, so no trip data leaves
  the machine.
Do exactly (CLI, from the repo root, all in ONE terminal session):
  PH="$(mktemp -d)"             # a new, empty folder every time (never reuse an old one)
  cp dist/index.html dist/404.html dist/robots.txt dist/_headers "$PH"/
  ls -A "$PH"                   # must show exactly: 404.html  _headers  index.html  robots.txt
  npx wrangler login            # if not already logged in; opens a browser
  npx wrangler pages deploy "$PH" --project-name worldcities --branch main
  (--branch main is required: this repo is on branch "vscode", and without it wrangler
   uses that branch and makes a PREVIEW deploy. If the first run asks to create the
   project or for a production branch name, create it and enter "main".)
Expect: "Deployment complete" with a https://<hash>.worldcities.pages.dev URL.
  Note that <hash> URL: Gate 3b verifies it.
Verify: curl -s https://worldcities.pages.dev/ | grep -c "World Cities"   -> 1
        curl -s https://worldcities.pages.dev/robots.txt                  -> Disallow: /
        curl -sI https://worldcities.pages.dev/ | grep -i x-robots-tag    -> noindex, nofollow
        curl -sI https://worldcities.pages.dev/no-such-page/ | head -1     -> HTTP/2 404
          (a 200 here means 404.html didn't upload: Pages is serving index.html for
           every path. Stop and paste the ls -A output.)
Rollback card: trigger = anything other than the placeholder is served ·
  action = dashboard › Workers & Pages › worldcities › Settings › Delete project ·
  run by Rob · data-loss window: none (static; rebuildable from trips/) ·
  limit: none · rehearsed locally: placeholder served 200 from python http.server
  (the 404 behaviour can't be rehearsed locally; the Pages verify above is its only check).
Paste back: the wrangler output and the three curl results.
```

```
GATE 3: Attach custom domain worldcities.ca to the Pages project   Plan ref: brief step 3
Class: DNS/zone
Preconditions: Gate 1 zone export saved; Gate 2 verify passed.
Blast radius: adds or changes the apex record for worldcities.ca. If the Gate 1
  export shows an existing apex A/AAAA/CNAME (another site), STOP and send it to
  Gage/Alice first. Other records (MX, TXT, subdomains) are untouched.
Do exactly (dashboard):
  Workers & Pages › worldcities › Custom domains › Set up a domain
  Domain = worldcities.ca › Continue › Activate domain
Expect: domain status goes from "Initializing" to "Active" (SSL can take a few minutes).
  DNS › Records shows a new proxied (orange-cloud) apex CNAME: worldcities.ca -> worldcities.pages.dev
Verify: curl -sI https://worldcities.ca/ | head -1   -> HTTP/2 200
        curl -s https://worldcities.ca/ | grep -c "World Cities"   -> 1
        export the zone again; diff against the Gate 1 export: only the apex CNAME was added.
Rollback card: trigger = a sibling record changed, or the site doesn't resolve after 30 min ·
  action = BOTH (1) Custom domains › worldcities.ca › Remove, AND (2) DNS › Records ›
  delete the apex CNAME worldcities.ca -> worldcities.pages.dev; then restore any changed
  record from the Gate 1 export · run by Rob · data-loss: none · limit: none ·
  rehearsed: no (dashboard-only step).
Paste back: both curl results, the new DNS record line, and the zone diff.
```

```
GATE 3b: Lock down *.pages.dev: redirect everything to worldcities.ca   Plan ref: Rex 2026-09-18
Set up once for the project, not per trip. Must pass before any Gate 5.
Class: DNS/zone (account-level edge redirect)
Preconditions: Gate 3 verify passed (worldcities.ca serves the placeholder).
Blast radius: an account-level Bulk Redirect whose source is the hostname
  worldcities.pages.dev and its subdomains (hash previews, branch aliases). Other
  Pages projects' *.pages.dev hostnames don't match the source and are unaffected.
  No record in the worldcities.ca zone changes.
  Why it's needed: the Access app (Gate 4) protects worldcities.ca only. Without this,
  worldcities.pages.dev/<slug>/ and every <hash>.worldcities.pages.dev/<slug>/ would
  serve the trip with no login. (A _redirects file can't do this: it can't match hostnames.)
Do exactly (dashboard, account level):
  1. Bulk Redirects › Create Bulk Redirect List
       List name = worldcities_pages_dev
       Add a URL redirect:
         Source URL  = worldcities.pages.dev
         Target URL  = https://worldcities.ca
         Status      = 301
         Tick: Preserve query string · Subpath matching · Preserve path suffix ·
               Include subdomains
       Save the list.
  2. Create a Bulk Redirect Rule that uses the list worldcities_pages_dev, then deploy it.
  3. (optional backup) Workers & Pages › worldcities › Settings › General ›
     Enable access policy. This creates an Access app on *.worldcities.pages.dev:
     it covers every <hash> URL (production's included) and branch aliases. It does
     NOT cover bare worldcities.pages.dev or worldcities.ca, so steps 1-2 are still
     required.
Expect: the rule is listed as deployed/enabled.
Verify (all must pass):
  curl -sI https://worldcities.pages.dev/ | grep -iE "^(HTTP|location)"
    -> 301, location: https://worldcities.ca/
  curl -sI "https://worldcities.pages.dev/any/path?x=1" | grep -iE "^(HTTP|location)"
    -> 301, location: https://worldcities.ca/any/path?x=1
  curl -sI https://<hash>.worldcities.pages.dev/ | grep -iE "^(HTTP|location)"
    (the <hash> URL from Gate 2's output) -> 301, location: https://worldcities.ca/
Rollback card: trigger = redirect loop, or worldcities.ca itself stops serving ·
  WHY THIS IS NOT JUST "REMOVE THE RULE": every old deployment keeps the files it was
  uploaded with, and stays reachable at its own https://<hash>.worldcities.pages.dev.
  After any Gate 5 upload, those files include trip pages. The redirect is the only
  thing keeping them private. Removing it first would make every old trip public.
  Action, in this order (run by Rob):
  1. Run Gate 2's placeholder-only deploy (new mktemp folder, --branch main). The
     production deployment now holds no trip. Note its deployment id or <hash>.
  2. Take trip content off every other hostname, with ONE of:
     a. Delete every deployment except step 1's:
          dashboard: Workers & Pages › worldcities › Deployments › (each one) › … › Delete
          or CLI:    npx wrangler pages deployment list --project-name worldcities
                     npx wrangler pages deployment delete <deployment-id> --project-name worldcities
        (one delete per id. Checked locally against wrangler 4.134.0 --help only;
         nothing was run. If a delete refuses because the deployment "has an active
         alias", stop and paste the output. Never delete step 1's deployment.)
        Then: the deployment list shows step 1's deployment only.
     b. OR Workers & Pages › worldcities › Settings › General › Enable access policy.
        This creates an Access app on *.worldcities.pages.dev (Rex): it covers every
        <hash> URL, production's included, and branch aliases. It does NOT cover bare
        worldcities.pages.dev or worldcities.ca. Step 1's placeholder-only deploy is
        what keeps bare worldcities.pages.dev clean. Step 4 checks both.
  3. Only now: Bulk Redirects › the worldcities_pages_dev rule › Disable (not Delete,
     so re-enabling it is the undo).
  4. Right away, for each live <slug> and each <hash> from the deployment list:
       curl -s https://worldcities.pages.dev/<slug>/ | grep -c "trip-data"          -> 0
       curl -s https://<hash>.worldcities.pages.dev/<slug>/ | grep -c "trip-data"   -> 0
     Any 1 = a trip page is public: re-enable the rule at once and paste the output.
  data-loss: none for trip data (rebuildable from trips/), but deleted deployments
  can't be restored (re-upload with Gate 5) · limit: none · rehearsed: no
  (dashboard-only; the wrangler subcommands were checked with --help only).
Paste back: the three curl results.
```

```
GATE 4: BILLING GATE. Cloudflare Access app on worldcities.ca/<slug> (one per trip)
Plan ref: brief step 4; Rex 2026-09-18
Class: billing (first time only) + DNS/zone (edge access policy)
Preconditions: Gate 3 and Gate 3b verify passed.
  FIRST TIME ONLY: Rob OKs adding a payment method. Zero Trust onboarding asks for one
  even on the Free plan ($0). Free plan = 50 seats. Every One-time PIN user who logs in
  takes a seat, and so does Rob. Seats come back through seat expiration: set it to 1 month.
Blast radius: applies only to the path worldcities.ca/<slug> and everything under it.
  The root placeholder stays public (intended). No other hostname in the zone is affected.
  One Access app per trip: never add a second trip's path to an existing app.
Do exactly (dashboard):
  First time only:
    dash.cloudflare.com › Zero Trust (complete onboarding, Free plan, payment method)
    Seat expiration = 1 month (menu location not in Rex's notes; if you can't find it,
      paste what you see and skip it for now. It only affects seat reuse, not access)
    Integrations › Identity providers › Add new identity provider › One-time PIN › Save
  Per trip:
    Access controls › Applications › Create new application › Self-hosted and private
      Application name = trip <slug>
      Add public hostname: subdomain = (blank) · domain = worldcities.ca · Path = <slug>
        (just the slug: no leading/trailing slash, no wildcard. A plain path covers
         /<slug>, /<slug>/ and everything under it; "<slug>/*" would miss /<slug>)
      Session duration = 1 week or shorter
      Policies › Create a new policy
        Policy name = trip-mates · Action = Allow
        Include › Emails = <each trip-mate's email, one per entry; include Rob's>
      Login methods: One-time PIN only · turn on "Apply instant authentication"
    Save.
Expect: the app is listed under Applications with path <slug>.
Verify (before any trip content is uploaded; every line must pass):
  for p in "<slug>" "<slug>/" "<slug>/index.html" "<slug>/zzz" "<SLUG-IN-UPPERCASE>/"; do
    curl -sI "https://worldcities.ca/$p" | grep -iE "^(HTTP|location)"; done
  -> each is a 302 whose location is <team>.cloudflareaccess.com, OR a 404 (the
     generated Not found page, no trip content). Never a 200.
Trip-mate note (send with the link): the login page emails a PIN from
  noreply@notify.cloudflare.com (check spam). PINs expire after 10 minutes. The page
  always says "code emailed", even for addresses not on the list.
Rollback card: trigger = trip-mates can't log in, or the wrong path is protected ·
  action = edit the policy/app. Do NOT delete the app while its trip page is uploaded
  (that makes it public); if the app must go, first rebuild without that trip and run
  Gate 5 (the slug disappears from the site), then delete the app · run by Rob ·
  data-loss: none · limit: none · rehearsed: no.
  Billing: the Free plan is $0; the payment method stays on file until Rob removes it.
Paste back: the five curl results (per trip).
```

```
GATE 5: Upload the full site (trip pages included)   Plan ref: brief step 2 (second half)
Class: deploy
Preconditions (every line):
  - Gate 3b verify passed (pages.dev hostnames redirect to worldcities.ca).
  - Fresh local build of ALL live trips in one run, exit 0, e.g.
      uv run tripsite/build.py trips/mexico-city-2026.md [trips/<other-live-trip>.md ...]
  - The build's last lines "dist now holds N trip(s): ..." (or `ls dist`) list only
    slugs that are meant to be live, and EVERY one of them has its own Access app whose
    Gate 4 verify passed. A slug in dist/ without an Access app would go live unprotected.
Blast radius: Pages project worldcities only. This upload REPLACES the whole site:
  any trip not in dist/ is taken down.
Do exactly (CLI, from the repo root):
  npx wrangler pages deploy dist --project-name worldcities --branch main
  (--branch main is required, or wrangler makes a preview deploy from branch "vscode")
  Upload the whole dist/ folder, not the index.html files. A trip whose metro geometry
  was too big to embed also has a dist/<slug>/metro.json beside its page, and the build
  prints a line saying so; without it the Metro lines checkbox does nothing. Mexico City
  does NOT produce one (its metro data is embedded), so today dist/<slug>/ holds only
  index.html. Check with: find dist -type f | sort
Expect: "Deployment complete".
Verify (per slug in dist/):
  # only for a slug whose build printed a metro.json line:
  curl -sI https://worldcities.ca/<slug>/metro.json | head -1   -> the Access 302, not a 404
  curl -sI https://worldcities.ca/<slug>/ | grep -iE "^(HTTP|location)"
    -> still the Access 302 to <team>.cloudflareaccess.com
  curl -sI https://worldcities.pages.dev/<slug>/ | grep -iE "^(HTTP|location)"
    -> 301, location: https://worldcities.ca/<slug>/
  in a private browser window: https://worldcities.ca/<slug>/ -> Access login -> enter an
    allowlisted email -> PIN -> trip page with map tiles
  and once:
  curl -s https://worldcities.ca/ | grep -c "<slug>"   -> 0 (root doesn't list trips)
  curl -sI https://worldcities.ca/ | grep -i x-robots-tag   -> noindex, nofollow
Rollback card: trigger = a trip page reachable without login on ANY hostname ·
  action = re-run Gate 2's placeholder-only deploy (with --branch main) immediately,
  then delete the leaking deployment (Workers & Pages › worldcities › Deployments › … ›
  Delete) · run by Rob · data-loss: none · limit: old deployments' <hash> URLs keep
  their content until deleted; Gate 3b redirects them to worldcities.ca, where Access
  applies · rehearsed: page served 200 locally from python http.server.
Paste back: the wrangler output, the build's "dist now holds" line, and the verify results.
```

```
GATE 6: Teardown after a trip   Plan ref: brief step 5
Class: deploy + DNS/zone
Preconditions: safety export. Keep trips/<trip>.md and copy dist/<slug>/ somewhere outside
  the repo (e.g. ~/Backups/trips/). The page can always be rebuilt from the trip file.
Blast radius: Pages project worldcities, the apex custom domain + CNAME, the Access
  app(s), and the Bulk Redirect rule.
Do exactly, case A (other trips are still live):
  1. Move trips/<trip>.md to trips/archive/. Rebuild the remaining live trips in one run
     (the build removes dist/<slug>/), then run Gate 5.
  2. Verify in a private browser window: https://worldcities.ca/<slug>/ -> Access login
     -> log in -> the page shows "Not found", not the trip. (curl can't check this yet:
     the Access app still answers with a 302.)
  3. Only then: Zero Trust › Access controls › Applications › trip <slug> › Delete. Then:
       curl -sI https://worldcities.ca/<slug>/ | head -1              -> HTTP/2 404
       curl -s https://worldcities.ca/<slug>/ | grep -c "trip-data"   -> 0
     A count of 1 means the trip is public: re-create the Access app (Gate 4) at once
     and paste the output. A 200 with a count of 0 means Pages isn't serving 404.html
     (not a leak): paste it.
  Leave the Gate 3b redirect in place. Old deployments still hold this trip at their
  <hash> URLs, and the redirect is what keeps them private. (Optional: delete those
  deployments too, as in Gate 3b rollback step 2a, but never the current production one.)
Do exactly, case B (last trip):
  1. Dashboard: Workers & Pages › worldcities › Settings › Delete project
     (removes every deployment, including old <hash> URLs that still hold trips)
     Check: Workers & Pages no longer lists worldcities. If the delete failed or was
     refused, STOP here and paste what you see. Don't do step 4.
  2. REQUIRED: Websites › worldcities.ca › DNS › Records: delete the apex CNAME
     worldcities.ca -> worldcities.pages.dev (don't assume the project deletion removed it)
  3. Zero Trust › Access controls › Applications › trip <slug> › Delete (each trip's app)
  4. LAST, and only if step 1's check passed: Bulk Redirects: delete the rule and list
     from Gate 3b. Removing the redirect while any deployment still exists would make
     its trips public (see the Gate 3b rollback card).
  5. (optional) Zero Trust identity provider One-time PIN: leave it or remove it
Expect: case A: the slug is gone and other trips still work. Case B: worldcities.ca
  no longer serves the site.
Verify: curl -sI https://worldcities.ca/<slug>/   -> never the trip page (404, or 302
          while an Access app exists)
        case B: curl -sI https://worldcities.pages.dev/   -> doesn't resolve / 404
        case B: zone export diffed against the Gate 1 export -> back to the original records
Rollback card: re-run Gates 2-5 (rebuild from trips/ or trips/archive/).
Paste back: verify results.
```

Which steps are CLI and which are dashboard:

| Gate | Where |
|---|---|
| 1 | dashboard, plus `dig` |
| 2 | CLI (`npx wrangler pages deploy … --branch main`) |
| 3 | dashboard |
| 3b | dashboard (account-level Bulk Redirects), once |
| 4 | dashboard; billing the first time; one app per trip |
| 5 | CLI (`npx wrangler pages deploy dist … --branch main`) |
| 6 | dashboard (case A also runs Gate 5) |
