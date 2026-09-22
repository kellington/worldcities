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

## Deploy (Rob runs these)

**Status 2026-09-21, late evening: Session A COMPLETE and Session B's CUTOVER IS DONE.
Gates 2, 3b, 0a, 0b, 0c and 0d PASSED — see the "What has actually been run" table below.
`worldcities.ca` is delegated to Cloudflare at the `.ca` registry as of 19:10:10 local and
mail survived. Session B has exactly two items left: the POST-FLIP 0e run and the 24-hour
re-test (earliest 2026-09-22 19:10 local). Everything else is still unrun.**

**THIS FILE IS THE AUTHORITATIVE SOURCE for every gate card, command and stop condition.**
Alice also publishes working-copy runbook pages (Session A, done; Session B) derived from
these cards, carrying the same commands and the same stop conditions, and each names this
README as authoritative. Nothing in them overrides a card here. **If a command in this file
changes, the published page is the thing that went stale — flag it to Alice to republish;
never reconcile the two by editing a card to match a page.** If a page and a card disagree
mid-session, stop and follow the card.

**PASTING COMMAND BLOCKS INTO AN INTERACTIVE SHELL (zsh, this machine's default).**
zsh does not treat `#` as a comment on an interactive command line unless you ask it to, so
a pasted block containing `# …` lines errors with `zsh: command not found: #` on every one of
them. **Harmless — it changes nothing and skips nothing — but it is noise in a cutover
runbook, and noise is a real cost when you are reading output for a stop condition.** Two
ways to deal with it, either is fine:
  - run this once per terminal session, before pasting anything:  `setopt interactive_comments`
  - or paste the command lines only, leaving the `# …` lines behind.
Blocks written or corrected after 2026-09-21 (0c's diff procedure) are comment-free and use
a variable-assignment style (`CF=…`, then `"$CF"`) so they paste cleanly with no setopt and
no editing. Older blocks — 0a, Gate 2, Gate 3, Gate 5 — still carry inline `#` notes; the
`setopt` line above is the one-step fix for all of them.

Target: Cloudflare Pages project `worldcities`, served on `worldcities.ca`,
each trip at `https://worldcities.ca/<slug>/`, behind Cloudflare Access (email one-time PIN).

**Order matters.** A trip page is uploaded only *after* Access protects its
path (Gate 4) **and** the `*.pages.dev` hostnames redirect to `worldcities.ca`
(Gate 3b). Until then, only the placeholder `index.html`, `404.html`,
`robots.txt` and `_headers` go up.

**Every upload replaces the whole site.** Build all live trips in one run
before every Gate 5 upload (see Usage).

Dashboard labels and Cloudflare behaviour below come from Rex's research
(2026-09-18, extended 2026-09-21). Gage hasn't checked them against the live
dashboard. If a label doesn't match, stop and paste what you see; don't guess.
That is not a formality: Session A already hit one — Gate 3b step 3's "Enable access
policy" control is not in the dashboard under that name (see the amendment there).
**The Hover registrar UI in Gate 0d was the least verified surface in this whole file** —
Gage has never seen it and Rex's notes didn't cover it. [RESOLVED 2026-09-21] **0d was run
and passed anyway**, which is the design working: the card was written to be label-independent
("what you are looking for", not a path to match), and Rob confirmed the result at Hover by
reading the two nameservers back character by character rather than trusting a screen label.
Keep that pattern for the next unverified vendor UI — describe the target state and verify by
reading it back, don't encode a path.

---

### [AMENDED 2026-09-21] Read this before any gate

Rob's decisions of 2026-09-21 changed the shape of this deploy. Every change below is
marked **[AMENDED 2026-09-21]** where it appears in a card.

1. `worldcities.ca` is on **Route 53 today, not Cloudflare**. Gate 1 assumed it was
   already an active Cloudflare zone; it is not. **GATE 0 (new, below) migrates it**,
   and it is a hard prerequisite for Gates 1, 3, 4, 5 and 6: a self-hosted Access
   application requires an **active zone in the account**, and `*.pages.dev` is not one
   (Rex, 2026-09-21). No zone → no Access → no trip page may go up.
2. **The S3 site is dropped.** The apex and `www` Route 53 alias records are *not*
   recreated on Cloudflare (Rob, 2026-09-21: the bucket holds only a 2020 placeholder —
   confirmed live today, `Server: AmazonS3`, `Last-Modified: Tue, 14 Jul 2020`).
3. **What this migration actually risks is live email, not the website.** Three Zoho MX
   records are the only thing in that zone anyone depends on. Every card in Gate 0 is
   written around keeping them answering.
4. **The trip runs 2026-10-23 → 2026-10-30 — 32 days out.** Nothing here is urgent. The
   mail gate (0e) is *expected* to take more than a day. Do not compress it.
5. Partial (CNAME-only) zone setup is Business plan and above, so a **full nameserver
   migration is the only Free route** (Rex, 2026-09-21).

Measurements Gage took on 2026-09-21 (read-only `dig`, authoritative servers, not a
cache). These are the load readings the Gate 0 cards are built on:

| Reading | Value | Why it matters |
|---|---|---|
| `dig +noall +answer MX worldcities.ca @ns-356.awsdns-44.com` | 3 records, **TTL 300** | mail TTL is *already* 5 min; nothing to lower |
| `dig +noall +authority NS worldcities.ca @c.ca-servers.ca` | 4× AWS NS, **TTL 86400** | **the binding constraint: rollback is a 24-hour instrument** |
| `dig +short DS worldcities.ca` | *empty* | no DNSSEC → no DS to remove, no SERVFAIL trap at the flip |
| `dig +short CAA worldcities.ca` | *empty* | nothing blocks Cloudflare issuing a certificate |
| `dig TXT` on apex, `_dmarc`, `zoho._domainkey` @ authoritative NS | *all empty* | **no SPF, no DKIM, no DMARC exists today** — don't expect `spf=pass` in 0e |
| `dig A worldcities.ca / www @ authoritative NS` | 8 S3 IPs each, TTL 5 | the records being deliberately dropped |
| `curl -s http://worldcities.ca/` | 204-byte 2020 page, contains `Amazon S3` once | gives Gate 3 a real "old site is gone" check |

Version notes, so the output isn't a surprise:

- `npx wrangler` is **unpinned**. It resolved to **4.136.1** here on 2026-09-21
  (`npx wrangler --version`, run locally). A different patch/minor number in Rob's
  output is not a failure. A **major** change (5.x) is: stop and paste it.
- `wrangler pages deploy` prints a warning that the working directory is a git repo with
  uncommitted changes. **Expected and harmless here** — this branch (`vscode`) carries
  uncommitted diary/ideas files, `dist/` is build output and `trips/` is gitignored;
  wrangler uploads the folder it is handed, not git state. (Gage has run no deploy; this
  is wrangler's documented behaviour, not a pasted observation.)

---

### [NEW 2026-09-21, post-flip] The measured post-flip state — read this before Gate 1 or Gate 3

The table above is the *pre-flip* load reading. These are the readings Gage took **after**
the cutover, at **19:40 MDT on 2026-09-21 — 30 minutes after the 19:10:10 flip.** They are
`dig`/`curl` output from this machine, not a paste and not a plan. Two of them change what
the Gate 3 card should say, so read this before running anything in Session C.

| Reading | Value | What it means |
|---|---|---|
| `dig +noall +authority NS worldcities.ca @c.ca-servers.ca` | the two `*.ns.cloudflare.com` names, TTL 86400 | the registry has flipped; this is the authoritative answer |
| `dig NS worldcities.ca @bella.ns.cloudflare.com` | `flags: qr aa` | Cloudflare is answering **authoritatively**, not as a pending zone |
| `dig worldcities.ca A @bella.ns.cloudflare.com` | **NOERROR, ANSWER: 0** (NODATA) | apex has no A record — correct, and see the NODATA note below |
| `dig www.worldcities.ca A @bella.ns.cloudflare.com` and `@gabriel` | **NXDOMAIN** | `www` does not exist in the Cloudflare zone at all — correct, until 0f |
| `dig +short MX worldcities.ca` @ four resolvers | all three Zoho MX, everywhere | mail is fine |
| `dig +short DS worldcities.ca` | empty | unchanged |
| `grep -v '^;'` counts on `cf-import-2026-09-21.txt` | **3** and **0** | re-run today; the corrected greps still hold |
| **`dig +noall +answer worldcities.ca A @1.1.1.1`** | **8 S3 A records, TTL 5** | **the delegation cache has NOT cleared** |
| **`dig +noall +answer www.worldcities.ca A @1.1.1.1` and `@9.9.9.9`** | **8 S3 A records, TTL 5** | same — these resolvers are still asking Route 53 |
| `dig +noall +answer www.worldcities.ca A @8.8.8.8` | *empty* | Google has already switched to Cloudflare |
| `curl -sI http://worldcities.ca/` from this machine | **no response at all** (does not resolve) | this machine's resolver has switched; the apex is dark here |

**FINDING 1 — THE DELEGATION IS STILL SPLIT RIGHT NOW, AND IT IS MEASURED, NOT PREDICTED.**
"The apex resolves to nothing" is true **authoritatively at Cloudflare** and true on
resolvers that have switched (this machine, `8.8.8.8`). It is **not** true of the public
internet: at 19:40 MDT, `1.1.1.1` and `9.9.9.9` were still handing out the eight S3 IPs for
both the apex and `www`, because they are still following the cached AWS delegation with its
86400 s TTL. **So the old 2020 S3 page still loads for part of the internet, and will keep
loading for up to 24 h — be willing to be surprised to 48 h.** That is not breakage; it is
exactly the window 0b's "24-hour instrument" note described, now visible instead of
theoretical. It is also the strongest argument for the Session C sequencing below. Two
consequences, both landing on Gate 3: FINDING 2 and FINDING 3.

**NODATA vs NXDOMAIN — do not misread either one.** The apex answers **NOERROR with zero
answers** (NODATA): the *name* `worldcities.ca` exists, because it carries SOA and three MX;
it just has no `A`. `www` answers **NXDOMAIN**: that name doesn't exist at all. Anyone who
expects NXDOMAIN at the apex and sees NOERROR must **not** read that as "an A record is
still there" — read `ANSWER: 0`, not the status code. And a `dig +short A` on the apex
printing nothing is the **correct** pre-Gate-3 state. Nobody should open an investigation
into an empty apex: that is the designed state between 0d and Gate 3, it is what Rob's
2026-09-21 decision to drop the S3 site chose, and mail is unaffected because delivery
follows MX and never the apex A record.

**FINDING 2 — GATE 3'S "OLD S3 PAGE IS GONE" CHECK PASSES ON A COMPLETELY BROKEN SITE.**
Measured on this machine at 19:40: `curl -s https://worldcities.ca/ | grep -c "Amazon S3"`
returned **0** — the value the card calls a pass — **because the fetch returned nothing at
all.** An empty body scores 0 on every content grep. So that line proves nothing by itself
and must only be read **after** `curl -sI … | head -1` has shown `HTTP/2 200`. Gate 3's
verify is reordered accordingly below. Same defect class as 0e's literal-hostname bug, in the
opposite direction: 0e **failed a healthy state**, this one **passes a dead one.**

**FINDING 3 — RUN GATE 3 FROM A RESOLVER THAT HAS SWITCHED, OR IT WILL FALSELY FAIL.**
If Gate 3's curls run while the local resolver is still on the cached Route 53 delegation,
`https://worldcities.ca/` returns **the old S3 page**: `grep -c "Amazon S3"` → 1 and
`grep -c "World Cities"` → 0. Both are documented Gate 3 failures, and Gate 3's documented
reaction to a failure is its rollback card — remove the custom domain, delete the apex CNAME.
**That would tear down a perfectly correct Gate 3 because of a DNS cache.** Cost profile
identical to the 0e defect: an unnecessary reversal of a correct change. The fix is in Gate
3's verify — **check authoritatively with `dig … @bella.ns.cloudflare.com` first, and only
trust a curl once `dig +short A worldcities.ca @1.1.1.1` stops returning eight S3 IPs.**

---

### [SESSIONS A AND B(cutover) COMPLETE 2026-09-21] What has actually been run

This table is the record of runs, not of intentions. A gate is only listed as PASSED here
because Rob ran it and pasted the output back.

| Gate | Result | Evidence (as pasted back 2026-09-21) |
|---|---|---|
| **2** — Pages project, placeholder only | **PASSED 2026-09-21** | Deployment URL `https://2ca4e8dc.worldcities.pages.dev`. `grep -c "World Cities"` → **2** (the amended expectation was right; the original `1` would have read as a false failure). `robots.txt` → `Disallow: /`. `x-robots-tag` → `noindex, nofollow`. `/no-such-page/` → **HTTP/2 404**, so Pages is not in SPA mode. Bare `worldcities.pages.dev` served the placeholder, which proves this is the **production** deployment and not a `vscode` preview. Slug-leak probe on root → 0. |
| **3b** — Bulk Redirect `*.pages.dev` → `worldcities.ca` | **PASSED 2026-09-21** (step 3 deferred, see the card) | List `worldcities_pages_dev` + rule created and deployed. Account was at **0 of 5 lists used** — no sibling list from `skyideas.com` or `minus1over12.com` to work around, so the shared-quota warning was correct but moot. bare → `301 location: https://worldcities.ca/`; `/any/path?x=1` → `301 location: https://worldcities.ca/any/path?x=1` (path **and** query preserved); `2ca4e8dc.worldcities.pages.dev/` → `301 → https://worldcities.ca/`, and it returned **200 before** the rule (baseline taken first, so the 301 is proven, not assumed); `2ca4e8dc.worldcities.pages.dev/mexico-city-2026-6b9638/` → `301 → https://worldcities.ca/mexico-city-2026-6b9638/` — **that is the hash-preview leak path closed**. `worldcities.ca` still 200 from S3 over http: no redirect loop. |
| **0a** — Route 53 authoritative export | **PASSED 2026-09-21** | Hosted zone `/hostedzone/Z0944732VRZ4NUBNE0FL`, `worldcities.ca.`, PrivateZone false, **5 record sets** (A 2, MX 1, NS 1, SOA 1). `NextToken` → `no-more-pages` (not truncated). Files `project/secrets/worldcities.ca-rrsets-2026-09-21.json` / `.txt`, copied to `~/Backups/worldcities-dns/`, SHA-256 identical in both places (`8dab9423…` JSON, `f5f5d7d5…` txt). `dig +noall +answer MX worldcities.ca @ns-356.awsdns-44.com` agrees with the export. **No TXT of any kind — confirmed, not inferred.** |
| **0b** — MX TTL | **PASSED 2026-09-21 — read, no action.** TTL already 300; there was never anything to run. |
| **0e baseline** — inbound mail, pre-flip (Session B) | **PASSED 2026-09-21.** Gmail → `rob@worldcities.ca`, sub-second. Raw message on file at `/Users/rob/Downloads/Show-original.eml` (6389 bytes). **2 `Received:` hops, no relay between sender and Zoho, receiving MTA `mx.zohomail.com`**; `Authentication-Results` / `Received-SPF: pass` / `X-ZohoMail-DKIM: pass` corroborate. Travelled **Route 53's** MX (delegation still AWS) — the correct "before" picture. **A2's pass criterion was wrong and was corrected first:** it demanded a literal `mx*.zoho.com`, which this healthy delivery does not contain, and post-flip that false FAIL is the documented trigger for the 0d rollback. See 0e's DEFECT note. |
| **0c** — zone on Cloudflare, records diffed (Session B) | **PASSED 2026-09-21.** Zone `worldcities.ca` created, status **PENDING** (delegation still AWS). Records exactly **SOA · NS ×2 · MX ×3** — no A, no www, no TXT; the step-3 apex/www deletions were done. Export at `project/secrets/cf-import-2026-09-21.txt`. Nameservers assigned: **`bella.ns.cloudflare.com` · `gabriel.ns.cloudflare.com`** (same pair as skyideas.com — normal account reuse). MX TTL exports as `1` = Cloudflare's "Auto"; served value 300, confirmed by dig. **Pre-flip dig green from BOTH nameservers** (10 mx / 20 mx2 / 50 mx3 at TTL 300) while `@1.1.1.1` returned the identical set from Route 53 — **both providers now serve the same three MX**, which is the condition 0d's rollback depends on. `dig +short DS` still empty. The card's own count greps returned a **false** 4 and 1 (comment lines, not records) and have been corrected to 3 and 0. |
| **0d** — THE CUTOVER: nameservers changed at Hover (Session B) | **PASSED 2026-09-21, flip confirmed at the registry 19:10:10 local.** Rob changed the nameservers at Hover and read them back at Hover afterwards character by character: **`bella.ns.cloudflare.com` and `gabriel.ns.cloudflare.com`, exactly two entries, nothing else** — no leftover AWS name, no third slot, so the mixed-delegation failure mode the card warns about did not happen. Registry confirms: `dig +noall +authority NS worldcities.ca @c.ca-servers.ca` → the two Cloudflare names. Cloudflare answers **authoritatively** (`flags: qr aa`). **Mail survived, verified on four independent resolvers** — `1.1.1.1`, `8.8.8.8`, `9.9.9.9`, `208.67.222.222` — each returning all three `10 mx.zoho.com` / `20 mx2.zoho.com` / `50 mx3.zoho.com`. Alice ran a background poller on a 2-minute interval from the flip until the registry landed; it watched MX health on every tick and **never fired its mail alert**. 0c's identical-MX-on-both-sides design is what made that true. Apex `A` → empty, so the 2020 S3 placeholder is gone from the apex (as designed, until Gate 3). `dig +short DS` still empty. Route 53 zone `Z0944732VRZ4NUBNE0FL` still serves all four AWS nameservers and all three MX — **the rollback is intact**. Pre-flight was 9 of 9 before the flip. **STILL OUTSTANDING ON 0e: the post-flip run (not yet sent) and the 24-hour re-test.** |

**Pre-flight items 8 and 9, answered by Rob in his own words on 2026-09-21 and recorded
here because they were judgement calls, not commands:** Rob **rarely receives mail at
`worldcities.ca` and is fine for 72 hours**. That is a wider margin than item 9 asked for
(48 h) and it is the reason the 24-hour delegation window was acceptable on the day. If a
future card on this domain needs the same judgement, this is the answer to re-confirm, not
to assume.

**The authoritative record inventory, verbatim from
`project/secrets/worldcities.ca-rrsets-2026-09-21.txt`.** Every checklist below is written
against these five lines and nothing else:

```
worldcities.ca.	A	-	ALIAS->s3-website-us-west-2.amazonaws.com.
worldcities.ca.	MX	300	10 mx.zoho.com. ; 20 mx2.zoho.com. ; 50 mx3.zoho.com.
worldcities.ca.	NS	300	ns-1337.awsdns-39.org. ; ns-1752.awsdns-27.co.uk. ; ns-356.awsdns-44.com. ; ns-614.awsdns-12.net.
worldcities.ca.	SOA	900	ns-1337.awsdns-39.org. awsdns-hostmaster.amazon.com. 1 7200 900 1209600 86400
www.worldcities.ca.	A	-	ALIAS->s3-website-us-west-2.amazonaws.com.
```

**Two corrections Session A forced, both folded into the cards below:**

1. **`aws` needs `--profile rob`.** Without it the CLI returns `InvalidClientTokenId`.
   Gage's 0a card omitted it. Every `aws` command in this file now carries it.
2. **Gate 3b step 3's control ("Workers & Pages › … › Settings › General › Enable access
   policy") could not be found in the dashboard.** Rob looked; it is not there. See the
   amendment in the 3b card — do not go hunting for that label again until after Gate 4.

**[READ THIS BEFORE ANY AWS COMMAND IN SESSION B] There are TWO Route 53 hosted zones on
this account. Only one is in scope.**

```
IN SCOPE, the only zone this project touches:
    Z0944732VRZ4NUBNE0FL    worldcities.ca.    5 records
DO NOT TOUCH, not in scope today or in any Session B step:
    Z08901851VA0TTXNMTFCZ   skyideas.com.      7 records
```

`skyideas.com` is delegated to **Cloudflare** (`dig +short NS skyideas.com` →
`bella.ns.cloudflare.com` / `gabriel.ns.cloudflare.com`), so that Route 53 zone is an
orphan: it answers for nobody and costs roughly $0.50/month. Cleaning it up is a separate
job with its own gate card, **not a Session B step**. It matters here only because Rob will
have the Route 53 console open with both zones listed, and **the two zone IDs differ only
after the first few characters** (`Z09447…` vs `Z08901…`). Read the whole id, or better,
copy it from this file. A wrong-zone action in a console is a realistic mis-click, and in
the skyideas zone it would be destructive for no reason at all.

---

```
GATE 0a [NEW 2026-09-21] [** PASSED 2026-09-21 — the export in project/secrets/ is
authoritative and complete. Re-run this card only if the files are lost, or as the S7
safety export before 0g. **]: Authoritative export of the Route 53 hosted zone
Plan ref: Gate 0 step 1 · staged-migration stage S1
Class: remote-data (AWS, read-only)
RESULT 2026-09-21 (Rob ran it; this is pasted output, not a plan):
  zone  /hostedzone/Z0944732VRZ4NUBNE0FL   worldcities.ca.   PrivateZone false   5 records
  NextToken -> no-more-pages        (the export is NOT truncated)
  counts    5 record sets: A 2 · MX 1 · NS 1 · SOA 1
  files     project/secrets/worldcities.ca-rrsets-2026-09-21.json  (+ .txt)
            ~/Backups/worldcities-dns/worldcities.ca-rrsets-2026-09-21.json  (+ .txt)
  SHA-256   8dab9423…  (.json)   f5f5d7d5…  (.txt)   — identical in both locations
  dig at the authoritative server agrees with the export, MX and TTL.
  **No TXT of any kind. Confirmed from the full export, not inferred from a dig.**
  This export SUPERSEDES the earlier `worldcities.ca-route53-2026-09-21.json` pair, which
  was trimmed (no IsTruncated/NextToken) and whose `.txt` was `--output text | sort`.
  Those files are still on disk; **use the `-rrsets-` pair, not the `-route53-` pair.**
**`--profile rob` IS REQUIRED.** Without it this account's CLI returns
  `InvalidClientTokenId` (observed 2026-09-21). Gage's original card omitted it; every
  `aws` line below now carries it. If you see `InvalidClientTokenId`, that is the missing
  profile, not a broken export.
**ONLY ONE ZONE IS IN SCOPE: Z0944732VRZ4NUBNE0FL.** `Z08901851VA0TTXNMTFCZ`
  (`skyideas.com.`, 7 records, an orphan delegated to Cloudflare) is on the same account
  and must not be read into a variable, changed or deleted by anything in this file. The
  ids differ only after the first few characters. See the Session A block above.
Preconditions: none beyond an AWS CLI that can see the account. Checked locally
  2026-09-21 on this machine: aws-cli/2.34.53, Python/3.14.5, /usr/local/bin/aws, and
  jq 1.8.2. Every flag used below was read out of `aws route53 <cmd> help` on this
  machine today — not from memory.
Blast radius: none. Every command is a read. Nothing in Route 53, Cloudflare, Hover or
  Zoho changes.
WHERE THE EXPORT LIVES [AMENDED 2026-09-21 — Rob's call, with the trade-off written down]
  Primary destination: **`project/secrets/`** inside this repo. Rob's reasoning: there is
  no `~/Backups` folder on this machine, and the export "only has context in this project
  anyway." Reasonable, and it is the path the cards below use.
  What that costs, stated so it is a choice and not an oversight:
    - `project/secrets/` is **gitignored** (`.gitignore` line 41, added by Alice; verified
      here with `git check-ignore -v project/secrets/` -> exit 0, and it no longer appears
      in `git status`). **That one line is load-bearing: this repo is public** (the same
      `.gitignore` says so for `trips/`). If anyone ever reworks `.gitignore`, re-check
      that this directory is still ignored *before* the next commit.
    - Ignored-but-in-tree means it is still inside the working tree, so **`git clean -fdx`
      deletes it** — `-x` is the operative flag, it is the one that removes ignored files.
      Plain `git clean -fd` spares it. Nothing else in normal use touches it.
    - It is therefore not "outside the blast radius" in the strict S1 sense: a single
      mistyped clean takes the repo and the backup together.
  SECOND COPY — DONE, 2026-09-21. **Four files, two pairs. Know which pair is which.**
    AUTHORITATIVE (use this one — complete, untruncated, one line per record):
      primary:     project/secrets/worldcities.ca-rrsets-2026-09-21.json  (+ .txt)
      out-of-tree: ~/Backups/worldcities-dns/worldcities.ca-rrsets-2026-09-21.json (+ .txt)
      SHA-256      8dab9423…  (.json)      f5f5d7d5…  (.txt)
                   identical in both locations, checked 2026-09-21.
    SUPERSEDED (the first, trimmed attempt — keep or delete, but do not check anything
    against it):
      project/secrets/worldcities.ca-route53-2026-09-21.json (+ .txt), same files copied
      to ~/Backups/worldcities-dns/. SHA-1 dac0c0a2… / a38d8922….
  `~/Backups/worldcities-dns/` was created 2026-09-21; it did not exist before. Both
  locations were listed here on 2026-09-21 and the `-rrsets-` files match byte-for-byte in
  size (1854 JSON, 430 txt) as well as by SHA-256.
  (40 hex digits = SHA-1, 64 = SHA-256. Step 4 below uses `shasum -a 256`; either is fine,
   just compare like with like.)
  The out-of-tree copy is the one that survives `git clean -fdx`, so it — not the primary —
  is what makes this a real S1 backup. `project/secrets/` stays primary per Rob's
  preference, and every path in the cards below is the in-repo one.
  ONE LINE FOR EVERY LATER EXPORT (0a re-runs, 0c's cf-import, Gate 1's cf-zone, and the
  S7 safety export in 0g): **write it to `project/secrets/`, then copy it to
  `~/Backups/worldcities-dns/` and checksum both.** Same reasoning as above, not repeated.
About a BIND-format export: **Gage cannot confirm one exists.** The AWS CLI on this
  machine has no BIND/zone-file export — `aws route53 help` lists no export or zone-file
  subcommand, only the API operations. Whether the Route 53 *console* offers "export zone
  file" on the hosted-zone page, Gage has not verified and will not guess. If you see such
  a button, use it for an extra copy and say so; the JSON below is the authoritative
  artifact either way.
Do exactly (CLI, one terminal session):
  cd /Users/rob/Documents/GitHub/Rob/worldcities
  mkdir -p project/secrets
  git check-ignore -v project/secrets/
    # must print a .gitignore line (today: .gitignore:41) and exit 0.
    # Nothing printed = the directory is NOT ignored. STOP: this repo is public.
  cd project/secrets
  export AWS_PAGER=""
  export AWS_PROFILE=rob        # REQUIRED on this account. Every aws line below also
                                # passes --profile rob explicitly, belt and braces.
  D=$(date +%Y-%m-%d)

  # 1 - find the hosted zone
  aws --profile rob route53 list-hosted-zones-by-name --dns-name worldcities.ca > "hosted-zones-$D.json"
  jq -r '.HostedZones[]
         | [.Id, .Name, (.Config.PrivateZone|tostring), (.ResourceRecordSetCount|tostring)]
         | @tsv' "hosted-zones-$D.json"
    # expect ONE line for worldcities.ca. with PrivateZone = false.
    #   2026-09-21 actual: /hostedzone/Z0944732VRZ4NUBNE0FL  worldcities.ca.  false  5
    # two lines (one private) -> use the false one.
    # no worldcities.ca line -> wrong account or profile: STOP and paste the output.
    # InvalidClientTokenId   -> the --profile is missing, not a broken zone.
    # This listing ALSO shows skyideas.com. / Z08901851VA0TTXNMTFCZ. That zone is NOT in
    # scope: do not select it, do not act on it. The select below filters by name so the
    # right one is picked for you — read the echo anyway.

  ZID=$(jq -r '.HostedZones[]
               | select(.Name=="worldcities.ca." and .Config.PrivateZone==false)
               | .Id' "hosted-zones-$D.json")
  echo "$ZID"      # MUST print exactly: /hostedzone/Z0944732VRZ4NUBNE0FL
                   # Anything else (especially /hostedzone/Z08901851VA0TTXNMTFCZ) -> STOP.
                   # Keep this shell open; later cards use $ZID.

  # 2 - the authoritative record export
  aws --profile rob route53 list-resource-record-sets --hosted-zone-id "$ZID" > "worldcities.ca-rrsets-$D.json"
  jq -r '.NextToken // "no-more-pages"' "worldcities.ca-rrsets-$D.json"
    # MUST print no-more-pages. Anything else = truncated export: STOP and paste it.
    # (the v2 CLI auto-paginates this operation; --max-items would CAP it, so it is NOT used)

  # 3 - the same thing as sorted text, for eyeballing and diffing
  jq -r '.ResourceRecordSets[]
         | [ .Name, .Type, ((.TTL // "-")|tostring),
             (if .AliasTarget then "ALIAS->" + .AliasTarget.DNSName
              else ((.ResourceRecords // []) | map(.Value) | join(" ; ")) end) ]
         | @tsv' "worldcities.ca-rrsets-$D.json" | sort > "worldcities.ca-rrsets-$D.txt"

  # 4 - the counts every later stage is checked against
  jq '.ResourceRecordSets | length' "worldcities.ca-rrsets-$D.json"
  jq -r '.ResourceRecordSets[].Type' "worldcities.ca-rrsets-$D.json" | sort | uniq -c
  ls -l  "worldcities.ca-rrsets-$D".*
  shasum -a 256 "worldcities.ca-rrsets-$D".*
Expect [now a hard number, measured 2026-09-21, not an estimate]: **5 record sets**, with
  the histogram **A 2 · MX 1 · NS 1 · SOA 1**. A re-run that returns anything else means
  the zone changed since 2026-09-21: STOP and hand the diff to Gage via Alice before any
  further gate. (Record SETS, not values: the one MX set holds three values, the one NS set
  holds four.)
Verify: the export agrees with what Gage measured from the authoritative server today:
  dig +noall +answer MX worldcities.ca @ns-356.awsdns-44.com
  -> 10 mx.zoho.com. / 20 mx2.zoho.com. / 50 mx3.zoho.com., TTL 300
  If the export's MX set differs from that dig in value, priority or TTL, STOP.
Rollback card: N/A — read-only, nothing to roll back. (If the files are lost, re-run it.)
Paste back: the hosted-zone line, the record count, the type histogram, the
  no-more-pages line, and the full worldcities.ca-rrsets-<date>.txt (redact any line you
  consider private and say you did). Gage needs the .txt to write 0c's record checklist.

[CLOSED 2026-09-21 — the earlier "not a verbatim API response" caveat no longer applies]
  The first export attempt (`worldcities.ca-route53-2026-09-21.json`) was trimmed: it had
  only `ResourceRecordSets`, no `IsTruncated`/`MaxItems`/`NextToken`, and its `.txt` was
  `--output text | sort`, which sorts record VALUES away from the record sets they belong
  to. It was probably complete; "probably" is exactly what step 2's `no-more-pages` check
  exists to replace.
  **Rob re-ran the card properly. `worldcities.ca-rrsets-2026-09-21.json` printed
  `no-more-pages` and 5 record sets, and its `.txt` is the one-line-per-record jq form
  from step 3.** That pair is authoritative; the `-route53-` pair is superseded.
  Still true, and still the one line to protect: `project/secrets/` is gitignored
  (`.gitignore` line 41 — verified again 2026-09-21), so it will not reach a public
  commit, but it IS in the working tree, so `git clean -fdx` would delete it. The
  `~/Backups/worldcities-dns/` copy is what makes this a real S1 backup.
  0c's checklist below is written against those five record sets, verbatim.
```

```
GATE 0b [NEW 2026-09-21] [** PASSED 2026-09-21 — read, no action taken, none needed. **]:
MX TTL — ALREADY SATISFIED. Nothing to run, nothing to wait for.
Plan ref: Gate 0 step 2
Class: none — this card exists only to record a measurement and kill a step.

**There is no TTL-lowering step and no wait.** The Zoho MX TTL is already 300 s. Two
independent sources say so: the authoritative 0a export
(`worldcities.ca-rrsets-2026-09-21.txt`: `worldcities.ca. MX 300 …`) and Gage's
dig straight at the authoritative server on 2026-09-21:
    dig +noall +answer MX worldcities.ca @ns-356.awsdns-44.com   -> TTL 300
Do not wait on something already done. Move to 0c.

WHAT ACTUALLY GOVERNS THE CUTOVER — read this once, it is the reason every Gate 0
rollback card says "24 hours":
  The number that matters is NOT the in-zone NS TTL (300, and irrelevant once the
  delegation moves) and NOT the MX TTL (300). It is the **parent `.ca` delegation TTL**,
  served by the registry, which Gage measured directly rather than inferred:
    dig +noall +authority NS worldcities.ca @c.ca-servers.ca
    -> worldcities.ca. 86400 IN NS ns-356.awsdns-44.com.  (+ the other three)
  **86400 s = 24 hours**, as answered by a `.ca` TLD server today. CIRA sets it; it cannot
  be lowered from Route 53, Cloudflare or Hover.
  Confidence and the conservative expectation: the 86400 is measured, not guessed, but it
  is measured *today* and a registry can change its own policy. Resolvers also cap, extend
  and ignore TTLs, and Hover's push to the registry adds its own unmeasurable delay.
  **So plan on 24 h and be willing to be surprised up to 48 h. Do not plan on less.**
  Consequences, stated plainly:
    - after the flip, a resolver holding the cached AWS delegation keeps asking Route 53
      for up to that long;
    - after a ROLLBACK, a resolver holding the cached Cloudflare delegation keeps asking
      Cloudflare for just as long.
    "Point the nameservers back" is a 24-hour instrument, not a five-minute one.
  Therefore the thing that protects mail is not a TTL at all. It is:
    **both nameserver sets serving identical, correct MX for the whole window.**
  Route 53 keeps its copy (0g: do not delete the zone), Cloudflare gets the same three MX
  before the flip (0c). Then it does not matter which side a resolver asks, and the 24 h
  stops being dangerous and becomes merely slow.
If a fresh export ever disagrees with the 300 above: STOP and hand it back to Gage via
  Alice. Changing an MX record set is an UPSERT that replaces the WHOLE set — a value
  missing from the change batch is a deleted mail route. That is not a step to improvise
  at the keyboard, and with the TTL already at 300 there is no reason to run it at all.
Paste back: nothing. Note "0b: MX TTL already 300, no action" and move on.
```

---

### [SPENT 2026-09-21 — 9 of 9 confirmed, then 0d ran] SESSION B PRE-FLIGHT (historical record + template)

Session B is 0c → 0e(baseline) → **0d (the cutover)** → 0e(post-flip). 0d is the only
irreversible-feeling step in the whole project, and its rollback takes up to 24 hours.
This is the list to read out loud first. Every line is a yes/no with evidence beside it;
**one "no" means Session B stops at 0c and 0d waits for another day.** Nothing here costs
more than a few minutes, and the whole point is that none of it is being recalled from
memory at the moment it matters.

**WHERE SESSION B STANDS, 2026-09-21 (late evening): THIS CHECKLIST IS SPENT. All nine items
were confirmed and 0d — the cutover — was RUN and PASSED at 19:10:10 local.** Items 8 and 9
were answered by Rob in his own words: he **rarely receives mail at `worldcities.ca` and is
fine for 72 hours.** This list is kept as the record of what was confirmed before the flip,
and as the template for the next domain; **it is not a to-do list any more.** Nothing in
Session C re-runs it — Session C has its own short pre-flight, at the bottom of this file.

**What is left of Session B is two items, and neither is on this checklist:**
  1. the **POST-FLIP 0e run** (inbound to `rob@worldcities.ca`, headers read) — not yet sent;
  2. the **24-hour re-test**, earliest **2026-09-22 19:10 local**.
Do not re-confirm items 1-7 "to be safe". They were confirmed, the flip happened, and the
state they described is now history; the current state is in the post-flip readings table
above.

| # | Confirm | How you know | If no |
|---|---|---|---|
| 1 | **The 0a export is in hand and intact** | `ls -l project/secrets/worldcities.ca-rrsets-2026-09-21.*` and `ls -l ~/Backups/worldcities-dns/` both list the pair; `shasum -a 256` on both locations still gives `8dab9423…` / `f5f5d7d5…` | Re-run Gate 0a (with `--profile rob`) before anything else. Do not flip nameservers without a current export. |
| 2 | **The zone in scope is the right one** | `Z0944732VRZ4NUBNE0FL` = worldcities.ca. `Z08901851VA0TTXNMTFCZ` = skyideas.com, **not in scope** | Stop. Re-read the Session A block above. |
| 3 | **SATISFIED 2026-09-21. Cloudflare shows exactly 3 records, all MX** | 0c's corrected count check — **comments stripped first**: `grep -v '^;' "$CF" \| grep -ciE "[[:space:]]MX[[:space:]]"` → `3`, and the A/AAAA/CNAME/TXT/CAA/SRV grep → `0`. Record lines are SOA, NS ×2, MX ×3. **Without `grep -v '^;'` these return 4 and 1 on a perfectly correct zone — see the INCIDENT note in 0c** | Fix the record list in 0c. Do not flip. But first re-read the incident note: check the grep before you touch the zone. |
| 4 | **SATISFIED 2026-09-21. Cloudflare's own nameservers already answer the three Zoho MX** | 0c's pre-flip dig, run against **both** names: `@bella.ns.cloudflare.com` and `@gabriel.ns.cloudflare.com` each returned 10 mx / 20 mx2 / 50 mx3 at TTL 300, while `@1.1.1.1` returned the identical set from Route 53. **Both providers serve the same three MX** | Do not flip. This dig is the single best pre-cutover evidence available and it is free. |
| 5 | **SATISFIED 2026-09-21. Both nameserver sets are written down, in this file, verbatim** | AWS (rollback target): `ns-356.awsdns-44.com` · `ns-1337.awsdns-39.org` · `ns-1752.awsdns-27.co.uk` · `ns-614.awsdns-12.net`. Cloudflare (flip target): **`bella.ns.cloudflare.com` · `gabriel.ns.cloudflare.com`** — read off this zone's own page and its own export. Same pair as skyideas.com, which is normal account reuse, not a mistake | Record them in 0c first. A rollback that needs a lookup is not a rollback. |
| 6 | **PASSED 2026-09-21. An INBOUND mail baseline to `rob@worldcities.ca` is on file, pre-flip** | 0e CASE A step A2, labelled "baseline, pre-flip": Gmail → rob@worldcities.ca, sub-second delivery, raw message exported to `/Users/rob/Downloads/Show-original.eml` (6389 bytes). **Exactly 2 `Received:` hops, no relay between sender and Zoho**, receiving MTA `mx.zohomail.com`; `Authentication-Results: mx.zohomail.com`, `Received-SPF: pass`, `X-ZohoMail-DKIM: pass` corroborate. It necessarily travelled **Route 53's** MX — the delegation still pointed at AWS — which is exactly the "before" picture the post-flip run is compared against. **Sending FROM the mailbox would not have counted** — outbound doesn't use MX (0e's THE TRAP) | Do not flip. Without an inbound baseline, any post-flip mail problem is unattributable. |
| 7 | **`dig +short DS worldcities.ca` is still empty** | Confirmed empty 2026-09-21 (0c). Run it again on the day of the flip anyway — it is one command | A DS record appearing changes the plan: STOP, hand to Gage via Alice. |
| 8 | **The 24-hour window is understood and acceptable** | Rollback is a 24-hour instrument (`.ca` delegation TTL 86400, measured). Plan for 24 h, be willing to be surprised to 48 h | Pick a different day. |
| 9 | **Nothing that needs `rob@worldcities.ca` is expected in the next 48 h** | **This is a real human mailbox that Rob uses, so answer it properly, not as a formality:** no password reset or account-verification mail routed to that address, no parcel/booking/airline confirmation, no 2FA-by-email, no reply expected to anything sent from it recently, nothing time-critical for 48 h. And today is not between 2026-10-23 and 2026-10-30 | Pick a different day. Inbound mail to this address is the only thing in this migration's blast radius, and it is the one thing that cannot be re-run later. |

Note on #6 and #9 [UPDATED 2026-09-21, the mailbox question is answered]: they are the same
worry from two ends. The migration's risk is not the website — the website is a 2020
placeholder being deliberately dropped. **It is inbound mail to `rob@worldcities.ca`, a live
Zoho mailbox Rob confirmed on 2026-09-21.** So neither item is a formality, and the "no
mailbox in use, prove it at the SMTP level instead" escape hatch (0e CASE B) **does not
apply here** — a real inbound delivery test is possible, so it is required.

---

```
GATE 0c [NEW 2026-09-21] [** PASSED 2026-09-21 — zone created, records correct, pre-flip dig
green. The card's own count check was wrong and has been corrected; the zone never was. **]:
Add worldcities.ca to Cloudflare and diff the import against the Route 53 export, record by
record        Plan ref: Gate 0 step 3
Class: DNS/zone (creates a PENDING zone; nothing is live until 0d)
RESULT 2026-09-21 (Rob ran the dashboard steps; Alice ran the digs; pasted output):
  Zone `worldcities.ca` exists on Cloudflare, status **PENDING** (as intended — the .ca
    delegation still points at AWS, so nothing observable has changed).
  Records, exactly: **SOA · NS ×2 · MX ×3.** No A, no www, no TXT. The step-3 deletion of
    the imported apex and www records was done. Export saved as
    `project/secrets/cf-import-2026-09-21.txt` (36 lines, of which 6 are records).
  **Cloudflare nameservers assigned: `bella.ns.cloudflare.com` · `gabriel.ns.cloudflare.com`**
    — these are the two names to enter at Hover in 0d. Read from this zone's own page and
    confirmed in its own export (they appear in its SOA and NS lines). See the amended note
    in step 6: this is the SAME pair as `skyideas.com`, and that is normal, not a mistake.
  **MX TTL exports as `1`. That is Cloudflare's encoding of "Auto", not a one-second TTL.**
    The served value is 300, confirmed by dig. Do not "fix" it, and do not read the `1` in
    `cf-import-2026-09-21.txt` as a drift from the Route 53 TTL of 300.
  **Pre-flip dig PASSED from BOTH Cloudflare nameservers** — the strongest pre-cutover
    evidence available, and now on file:
      dig … MX worldcities.ca @bella.ns.cloudflare.com    -> 10 mx.zoho.com / 20 mx2 / 50 mx3, TTL 300
      dig … MX worldcities.ca @gabriel.ns.cloudflare.com  -> the identical set, TTL 300
      dig +short MX worldcities.ca @1.1.1.1               -> the identical set, still from Route 53
      dig +short NS worldcities.ca                        -> still the four AWS names
    **So both providers now serve the same three MX.** That is the exact condition 0d's
    rollback card depends on — it is now established fact rather than a plan, and it is what
    makes the 24-hour delegation window merely slow instead of dangerous.
  `dig +short DS worldcities.ca` -> still empty. Pre-flight item 7 satisfied as of today.
  Count check: Rob's run of the ORIGINAL greps returned 4 and 1 — **both false positives
    from the export's own comment lines, not records.** Diagnosed and reproduced; the
    corrected greps return 3 and 0. See the INCIDENT note in the diff procedure below.
Preconditions: 0a and 0b **PASSED 2026-09-21** — the 5-record export is on disk and
  checksummed in two places, and the MX TTL needs nothing. Run the Session B pre-flight
  items 1, 2 and 7 before this card. **Do not change nameservers in this card.** Everything
  here is reversible with zero user impact precisely because the .ca delegation still
  points at AWS while you do it. This is the last card in Gate 0 that is free.
Blast radius: creates a new zone object in the Cloudflare account. Sibling zones in that
  account — `skyideas.com` and `minus1over12.com` — are SEPARATE zones: adding a third
  zone does not read, change or re-scan them, and Cloudflare's Free plan has no documented
  zone cap (Rex, 2026-09-21). The one genuinely shared budget in this whole deploy is
  account-level Bulk Redirects (Gate 3b / 0f), not zones — and as of 2026-09-21 that budget
  was measured at **0 of 5 lists used** before Gate 3b took one, so there is plenty of room.
  No live DNS answer changes here.
Do exactly (dashboard):
  1. dash.cloudflare.com › Add a domain (older UI: "Add site") › worldcities.ca
     › select the **Free** plan › Continue.
     Cloudflare runs a "quick scan" of existing DNS records. Rex, 2026-09-21, quoting
     Cloudflare's own docs: **"the quick scan is not guaranteed to find all existing DNS
     records"**, with email records called out specially. Treat the scan as a draft.
     Cloudflare will now show you two nameservers and ask you to change them. **Do not.**
     Leave the zone pending and continue here.
  2. DNS › Records: work through the checklist below against the 0a export.
  3. DELETE the imported apex `A` and `www A` records if the scan created them (the eight
     S3 IPs). Rob's 2026-09-21 decision: the S3 site is dropped and these are not
     recreated. Consequence, stated: between the 0d flip and Gate 3, `worldcities.ca` will
     not resolve at all — the 2020 placeholder disappears. That is intended. **Email is
     unaffected: mail routing depends on MX, not on the apex A record.**
  4. Leave every MX TTL on Auto (300) through the mail gate. Raise it later if you want.
     [NOTE 2026-09-21] **A BIND export writes Auto as TTL `1`.** `cf-import-2026-09-21.txt`
     shows `worldcities.ca. 1 IN MX 10 mx.zoho.com.` and that is correct — it is Cloudflare's
     encoding of Auto, not a one-second TTL, and it does not contradict the Route 53 TTL of
     300. The served value is 300, confirmed by dig against both Cloudflare nameservers. **Do
     not "fix" the 1.**
  5. DNS › Records › Import and Export › **Export** -> save it beside the Route 53
     export, as project/secrets/cf-import-<date>.txt  (gitignored; see 0a's
     "WHERE THE EXPORT LIVES" for why that directory and what it costs)
  6. **Record the two Cloudflare nameservers, in writing, now.** Overview page (right-hand
     side, "Cloudflare nameservers"). Copy both names into the diary entry for this session
     AND paste them back to Alice. They are account-specific, they are what you type into
     Hover in 0d, and they are half of pre-flight item 5.
     DONE 2026-09-21 — read from this zone's own Overview page and confirmed in its own
     export (its SOA and NS lines):
         Cloudflare NS 1: **bella.ns.cloudflare.com**
         Cloudflare NS 2: **gabriel.ns.cloudflare.com**
     [AMENDED 2026-09-21 — the original wording of this note was misleading and would have
      had Rob distrusting a correct value.] These are **the same pair as `skyideas.com`**.
      That is **normal and expected**: a Cloudflare account commonly reuses one nameserver
      pair across its zones, so an identical pair is not evidence of a mistake and is not a
      sign you read the wrong domain's page. The earlier phrasing — "this zone may well be
      assigned a different pair" — was true in general and unhelpful here.
      What actually matters, and the rule that stands: **the names must be read from THIS
      zone's own Overview page or its own export, not typed from memory or copied off another
      domain.** They were, on 2026-09-21. Matching skyideas' pair afterwards is a coincidence
      of account assignment, not a verification failure — and equally, it is not a substitute
      for reading them off this zone.
RECORD CHECKLIST [REWRITTEN 2026-09-21 against the verified 5-record export — no
arithmetic, no dig-derived estimates, no "should be about"]
  Source of truth: `project/secrets/worldcities.ca-rrsets-2026-09-21.txt`, 5 record sets,
  `no-more-pages`, reproduced verbatim in the Session A block above. Every line of that
  export is accounted for below. **There is no sixth record and no TXT — that is measured,
  not assumed.**
  **The entire migration payload is three MX values.**
  CARRY — 1 record set, 3 values, and nothing else:
    MX ×3   10 mx.zoho.com. · 20 mx2.zoho.com. · 50 mx3.zoho.com.   (export TTL 300)
            All three, exact hostnames, exact priorities. Cloudflare lists each value as
            its own row, so **three rows in DNS › Records**. TTL Auto (= 300) is correct;
            leave it there through the mail gate.
            **DNS-only — no proxy.** (In Cloudflare that is automatic: the orange cloud
            exists only on A, AAAA and CNAME, and MX has no proxy toggle at all. The trap
            that is real is an MX pointing at an in-zone hostname whose A record is
            proxied; Zoho's three targets are external, so it cannot bite here. Keep it
            that way. If the UI *does* show a proxy toggle on an MX row, that contradicts
            what Gage expects: stop and paste a screenshot.)
            THIS IS THE WHOLE JOB.
  DROP (deliberately) — 2 record sets:
    worldcities.ca.      A  ALIAS -> s3-website-us-west-2.amazonaws.com.
    www.worldcities.ca.  A  ALIAS -> s3-website-us-west-2.amazonaws.com.
            Rob's decision, 2026-09-21: the S3 site is dropped (it holds a 2020
            placeholder). Cloudflare's scan cannot import a Route 53 ALIAS as such — it
            will either skip these or resolve them to the eight S3 IPs and create plain A
            records. **Whatever it created at the apex and at `www`, delete it** (step 3).
            After 0d, `worldcities.ca` resolves to nothing until Gate 3, and `www` to
            nothing until 0f. Both are intended. **Mail is unaffected: delivery follows
            MX, never the apex A record.**
  NEVER RECREATE — 2 record sets:
    worldcities.ca.  NS   (the four awsdns names) — Cloudflare supplies its own two.
    worldcities.ca.  SOA  (TTL 900)               — Cloudflare supplies its own.
            Typing either of these into Cloudflare by hand would be actively harmful.
            Cloudflare does not let you, and you should not want to.
  CONFIRMED ABSENT — verified from the complete export, not inferred from public DNS:
    TXT     **none, of any kind.** No SPF at the apex, no DKIM (`zoho._domainkey`), no
            DMARC (`_dmarc`), no Zoho domain-verification record. The export contains zero
            TXT record sets and it is not truncated (`no-more-pages`). Zoho here is
            **inbound MX only**. So: nothing to carry, and the old "the scan may have
            missed an email record" contingency is, for this zone, an empty set.
    CNAME   none.   SRV none.   AAAA none.   CAA none.
    CAA     do not add one — a CAA naming only Amazon's CA would block Cloudflare issuing
            the certificate Gate 3 needs.
    DNSSEC  no DS at the `.ca` parent (`dig +short DS worldcities.ca` empty), so there is
            nothing to remove and no flip-with-stale-DS outage to fear. **Re-run that dig
            immediately before 0d** (pre-flight item 7); if it ever returns a value, STOP —
            that changes the plan.
  ARITHMETIC, done once, so nobody redoes it at the keyboard:
    5 sets exported  −  2 dropped (apex A, www A)  −  2 never recreated (NS, SOA)
                     =  1 set carried  =  **3 MX rows in Cloudflare. Exactly 3. Nothing else.**
  If the export you are holding is not the 5-record one above, STOP and hand it to Gage via
  Alice. The export is the inventory; Cloudflare's scan is a draft.
NOT A GATE, BUT WORTH KNOWING [2026-09-21]: with no SPF, DKIM or DMARC published, any mail
  **sent** from worldcities.ca today is unauthenticated, and receivers are free to junk or
  reject it. That is the *pre-existing* state — this migration neither causes it nor makes
  it worse, and fixing it is explicitly out of scope today. But if Rob ever starts sending
  from this address rather than just receiving, it is a real gap and deserves its own job.
Diff procedure [CORRECTED 2026-09-21 after this card produced a FALSE FAIL on a correct
zone — read the incident note below before you run it]. No `aws` call is needed here: the
Route 53 side is the file already on disk from 0a.

**`grep -v '^;'` IS NOT OPTIONAL.** A Cloudflare BIND export is mostly **comments** — a
25-line boilerplate header plus a `;; <TYPE> Records` section header before each group. Six
record lines in a 36-line file. Every count below therefore strips comment lines FIRST.
Paste this block as a whole; it has no `#` comments in it, so it survives a paste into an
interactive zsh (see the note after this card):

  cd /Users/rob/Documents/GitHub/Rob/worldcities/project/secrets
  R53=worldcities.ca-rrsets-2026-09-21.txt
  CF=cf-import-2026-09-21.txt

  awk -F'\t' '$2=="MX" || $2=="TXT" || $2=="CNAME"' "$R53"
  grep -v '^;' "$CF" | grep -vE '^[[:space:]]*$'
  grep -v '^;' "$CF" | grep -iE "[[:space:]](MX|TXT|CNAME)[[:space:]]"
  grep -v '^;' "$CF" | grep -ciE "[[:space:]]MX[[:space:]]"
  grep -v '^;' "$CF" | grep -ciE "[[:space:]](A|AAAA|CNAME|TXT|CAA|SRV)[[:space:]]"

What each line must return:
  1. R53 side: **exactly ONE line**, the MX set with its three Zoho values at TTL 300.
     Zero TXT and zero CNAME lines is the CORRECT result here, not a missing file.
  2. Every record in the Cloudflare zone, comments stripped: **6 lines — SOA, NS ×2,
     MX ×3.** Read them. This is the check that actually tells you what is in the zone.
  3. The mail lines: **three MX**, naming mx / mx2 / mx3.zoho.com at 10 / 20 / 50.
  4. **3**
  5. **0**
  3 and 0. Not 2, not 4, and nothing that is not an MX.
  Also count the rows in DNS › Records by eye: three, all MX.
  A 4th MX *record* line means a duplicate was added on top of an imported one — delete the
  duplicate, do not "fix" priorities. A non-zero on line 5 means the apex/www A records (or
  something the scan invented) are still there: step 3 isn't finished.

INCIDENT, 2026-09-21 — why the comment filter is mandatory. Gage's original version of this
check omitted `grep -v '^;'` and Rob's run returned **4 and 1** on a zone that was completely
correct. Both were false positives from the file's own prose, diagnosed against the real
`project/secrets/cf-import-2026-09-21.txt` and reproduced by Gage:
  - the 4th "MX" was line 33, the section header comment **`;; MX Records`**;
  - the 1 was line 6 of Cloudflare's boilerplate, **`;; purposes ONLY and MUST be edited
    before use on a production`** — the patterns run with `-i`, so `[[:space:]]A[[:space:]]`
    matched the English word "**a**" in "on **a** production".
The old card correctly predicted that a BIND export carries SOA and NS *record* lines and
that neither pattern would match them. That was right as far as it went and still missed the
point: the file is overwhelmingly comments, and the section headers and prose were not
accounted for. **A check that fails on a correct zone is worse than no check**, because the
next reader's instinct is to "fix" a zone that was right all along, in a card whose next step
is a 24-hour-rollback cutover. The record state was correct the whole time.
Expect: the zone sits in "Pending Nameserver Update"; the record list matches the
  checklist; the exported BIND file's **record** lines (comments stripped) are exactly SOA,
  NS ×2 and MX ×3 — six lines, three of them MX.
  Actual 2026-09-21: exactly that. PASSED.
Verify (pre-flip, without touching the delegation): ask Cloudflare's own nameservers, which
  serve the zone even before the registrar points at them. Ask **both** — you are about to
  hand both names to Hover, and one of them answering is not the same as both answering:
  dig +noall +answer MX worldcities.ca @bella.ns.cloudflare.com
  dig +noall +answer MX worldcities.ca @gabriel.ns.cloudflare.com
  -> the three Zoho MX, answered by Cloudflare, BEFORE any delegation change.
  This is the strongest pre-flip evidence available and it is worth waiting for.
  RESULT 2026-09-21: **both returned 10 mx.zoho.com / 20 mx2.zoho.com / 50 mx3.zoho.com at
  TTL 300**, while `@1.1.1.1` returned the identical set from Route 53 and `dig +short NS`
  still showed the four AWS names. Cloudflare answered normally for a PENDING zone — no
  REFUSED, no SERVFAIL. **Both providers serve the same three MX: the precondition 0d's
  rollback depends on is now measured, not assumed.**
  (If Cloudflare's NS answer ever REFUSED or SERVFAIL for a pending zone, that is behaviour
   Gage has not verified — paste it, do NOT treat it as a record-set failure, and fall
   back to eyeballing the record lines of cf-import-<date>.txt.)
Rollback card: trigger = the record checklist can't be satisfied, or the pre-flip dig
  doesn't return all three MX · action = Websites › worldcities.ca › (Overview, bottom)
  Remove site from Cloudflare. The delegation still points at AWS, so nothing that anyone
  can observe changes · run by Rob · data-loss window: **none — this is the last card in
  Gate 0 with a zero-impact rollback** · mechanism limit: none · rehearsed: no
  (dashboard-only).
Paste back: the two-nameserver assignment from the Overview page, the MX/TXT/CNAME lines
  from both sides, your expected-vs-actual record count, and the pre-flip dig from BOTH
  Cloudflare nameservers. **If a count doesn't match, paste the grep output AND the
  comment-stripped record listing (`grep -v '^;' "$CF" | grep -vE '^[[:space:]]*$'`) before
  changing anything in the zone** — on 2026-09-21 the mismatch was in the check, not in the
  records, and the listing is what settles it in one look.
  DONE 2026-09-21 — all of the above pasted back and recorded in the RESULT block at the top
  of this card. Nothing outstanding in 0c.
```

```
GATE 0d [NEW 2026-09-21] [** PASSED 2026-09-21 — THE CUTOVER IS DONE. Flip confirmed at the
.ca registry 19:10:10 local. Mail survived. Do NOT re-run this card; its only remaining use
is the ROLLBACK block at the bottom, which stays live until 0g. **]: Change the nameservers
at Hover        Plan ref: Gate 0 step 4
Class: DNS/zone — **THIS IS THE CUTOVER. The rollback card below is written before it,
  not after.**
RESULT 2026-09-21 (Rob ran it at Hover; Alice ran the polling; this is pasted output, not a
plan):
  **Flip time: 19:10:10 local, 2026-09-21** — the moment the registry answer changed. That is
    the timestamp the 0e 24-hour re-test counts from, so the re-test is earliest
    **2026-09-22 19:10 local.**
  At Hover, after saving, Rob read the nameserver list back **character by character**:
        bella.ns.cloudflare.com
        gabriel.ns.cloudflare.com
    **Exactly two entries, nothing else.** No leftover AWS name, no padded third slot — so
    the mixed-delegation failure mode this card warns about (half the internet asking AWS,
    half asking Cloudflare, flip unverifiable, rollback unclear) did **not** happen.
  Registry, which bypasses every cache:
        dig +noall +authority NS worldcities.ca @c.ca-servers.ca
        -> bella.ns.cloudflare.com.
           gabriel.ns.cloudflare.com.
    Alice watched this with a background poller on a **2-minute interval from the flip until
    it landed** — so the 19:10:10 time is an observation, not an estimate.
  Cloudflare is answering **authoritatively** (`flags: qr aa`), not as a pending zone.
  **MAIL SURVIVED — verified on FOUR independent resolvers**, each returning all three:
        @1.1.1.1  @8.8.8.8  @9.9.9.9  @208.67.222.222
        -> 10 mx.zoho.com. / 20 mx2.zoho.com. / 50 mx3.zoho.com.
    The poller also checked MX health on **every 2-minute tick** from the flip onward and
    **never fired its mail alert.** 0c's "identical MX on both sides" design is the reason:
    whichever side a resolver asked during the split window, it got the same three Zoho
    servers. That was the whole point of the design and it did exactly its job.
  `dig +short A worldcities.ca` -> **empty.** The apex resolves to nothing and the 2020 S3
    page is gone from it. **As designed, until Gate 3.** See the post-flip readings table
    above for the NODATA-vs-NXDOMAIN note and for the fact that some public resolvers were
    still serving the old S3 IPs 30 minutes later — that is the delegation cache, not a fault.
  `dig +short DS worldcities.ca` -> still empty.
  **Route 53 zone `Z0944732VRZ4NUBNE0FL` still serves all four AWS nameservers and all three
    MX — the rollback below is INTACT and stays intact until 0g's five conditions are met.**
  Pre-flight: **9 of 9 confirmed before the flip.** Items 8 and 9 answered by Rob: he rarely
    receives mail at this domain and is fine for 72 hours.
  **NOT DONE YET, and it gates Session C: the POST-FLIP 0e run and the 24-hour re-test.**
Preconditions (every line, evidence pasted) — ALL SATISFIED 2026-09-21 before the flip:
  - **The nine-item Session B pre-flight above, all nine confirmed.** That list exists for
    this card. Do not open Hover with an item outstanding.
  - 0a, 0b and **0c all PASSED 2026-09-21**: zone created and PENDING, records exactly
    SOA + NS ×2 + MX ×3, and 0c's pre-flip dig returned all three Zoho MX **from both of
    Cloudflare's own nameservers** while Route 53 still served the identical set.
  - 0c step 6 done: the two Cloudflare nameservers to enter at Hover are
    **`bella.ns.cloudflare.com`** and **`gabriel.ns.cloudflare.com`**, read off this zone's
    own Overview page and confirmed in its own export. (Same pair as skyideas.com — normal
    account reuse, not a mistake; see 0c step 6.)
  - `dig +short DS worldcities.ca` re-run today and still empty.
  - **INBOUND mail baseline taken BEFORE the flip**, so a later failure can't be blamed on
    something that was already broken. Run 0e CASE A now, unchanged, and record the result
    as "baseline, pre-flip". Do not proceed on a failed baseline.
    **It must be step A2: a message sent from a non-Zoho account TO `rob@worldcities.ca`,
    arriving, with a `Received:` line naming a **Zoho-operated inbound host** (`mx*.zoho.com`
    OR `mx*.zohomail.com` — observed 2026-09-21: `mx.zohomail.com`) and **no hop between the
    sender and it.** A message sent *from* the mailbox is not a baseline — outbound does not
    use MX and would keep working even if this migration broke inbound completely (0e, "THE
    TRAP").
    **DONE — PASSED 2026-09-21**, 2 hops, `mx.zohomail.com`, evidence on file at
    `/Users/rob/Downloads/Show-original.eml`. It travelled Route 53's MX, which is the point
    of a baseline.
  - Trip window check: today is not between 2026-10-23 and 2026-10-30.
Blast radius: the entire `worldcities.ca` zone, for every resolver on the internet, for
  up to 24 h in each direction. Mail is in that blast radius. The websites at
  `skyideas.com` and `minus1over12.com` are different zones with different delegations
  and are untouched. Nothing about Zoho's mailbox, its contents, or its account changes —
  only which nameserver tells the world where to deliver.
Do exactly (registrar).
  **EVERY HOVER LABEL BELOW IS UNVERIFIED. Gage has never seen the Hover dashboard and is
  not guessing at it.** Treat the words as a description of what you are looking for, not
  as a path to match character-for-character. Hover redesigns, and a 2026 label may differ
  from any label written here or in Rex's notes.
  WHAT YOU ARE LOOKING FOR (in plain terms, label-independent):
    the one screen for **worldcities.ca specifically** — not an account-wide setting —
    that lists the **four current `*.awsdns-*` nameserver hostnames** and lets you replace
    them. On most registrars it lives under the domain's own detail page, in a section
    called something like Nameservers / DNS / Name servers / Advanced DNS, with an Edit or
    Change control.
  LIKELY PATH (unverified, expect drift): hover.com › sign in › Your domains ›
    worldcities.ca › Nameservers (or "Domain details › Nameservers") › Edit.
  THE TEST THAT THE SCREEN IS THE RIGHT ONE — this is what makes label drift harmless:
    **before you change anything, the screen must already show all four awdns names:**
      ns-356.awsdns-44.com · ns-1337.awsdns-39.org · ns-1752.awsdns-27.co.uk ·
      ns-614.awsdns-12.net
    If it shows Hover's own nameservers, fewer than four entries, a different set, or a
    DNS **record** editor (A/MX/CNAME rows) rather than a nameserver list, **you are on the
    wrong screen or the zone is not what we think it is. STOP and paste what you see.**
    Changing the wrong thing here is the one mistake in this project that takes 24 hours to
    undo.
  THEN: remove all four AWS entries › enter the TWO Cloudflare nameservers **exactly as
    shown on this zone's Cloudflare Overview page and recorded in 0c step 6** › Save.
    As recorded on 2026-09-21, those two are:
        bella.ns.cloudflare.com
        gabriel.ns.cloudflare.com
    Re-read them off the Overview page before typing them anyway — that page is the source,
    this file is a transcript of it.
  Notes on the shapes registrars use, so none of them is a surprise:
    - If offered a choice like "Hover's nameservers" vs "Custom nameservers", choose
      **custom**. Hover's own nameservers are not Cloudflare's.
    - If the form has more than two slots, fill the first two and leave the rest EMPTY.
      Do not pad with an AWS name "just in case": a mixed delegation means half the
      internet asks AWS and half asks Cloudflare, which is exactly the ambiguity 0c's
      identical-MX-on-both-sides design is meant to make harmless — but it also makes the
      flip unverifiable and the rollback unclear. Two names, both Cloudflare.
    - If Hover demands a confirmation email, an OTP, or shows a "changes may take up to
      48 hours" warning: normal, proceed, and note the time.
    - If Hover REFUSES the change (domain lock, expired card, pending transfer): STOP and
      paste the message. Do not unlock anything you don't understand today.
  (The two Cloudflare names are account-specific: copy them from this zone's own page, never
   from memory. [AMENDED 2026-09-21] This zone was assigned `bella` / `gabriel`, **the same
   pair as `skyideas.com`** — an account commonly reuses one pair across its zones, so an
   identical pair is normal and is NOT a sign you are looking at the wrong domain. The
   earlier note here implied a different pair should be expected; that was misleading.)
Then (Cloudflare): the zone's Overview › "Check nameservers now" / "Continue".
Expect: status moves Pending -> **Active**, and Cloudflare emails
  "worldcities.ca is now active on Cloudflare". Minutes to a few hours; the .ca parent
  updates on Hover's schedule, not ours.
Verify — ask the .ca registry directly, which bypasses every cache:
  dig +noall +authority NS worldcities.ca @c.ca-servers.ca
    -> the two *.ns.cloudflare.com names (TTL 86400)
  dig +short MX worldcities.ca @1.1.1.1
    -> the three Zoho MX, unchanged   <- THE ONE THAT MATTERS
  dig +short MX worldcities.ca @8.8.8.8
    -> same
  dig +short NS worldcities.ca
    -> may still answer AWS for up to 24 h. NOT a failure: that is the delegation TTL.
       The @c.ca-servers.ca answer is the authoritative one.
Rollback card (written before the cutover, and **STILL LIVE** — the cutover having passed
does not retire it. It remains the documented reaction to a failed post-flip 0e or a failed
24-hour re-test, and it stays available for exactly as long as 0g leaves the Route 53 zone
alone. Confirmed intact 2026-09-21 after the flip: that zone still serves all four AWS
nameservers and all three Zoho MX):
  Trigger: the 0e mail gate fails (no inbound within 15 min, or a bounce), OR
    `dig +noall +authority NS worldcities.ca @c.ca-servers.ca` shows nameservers that are
    neither the four AWS names nor the two Cloudflare names.
  Action, code/schema/data/DNS layers: DNS only. At Hover, set the domain's nameservers
    back to these four, exactly — **all four, spelling and TLD as written; note that they
    are on four DIFFERENT top-level domains (.com, .org, .co.uk, .net), which is normal for
    Route 53 and the most likely thing to be mistyped:**

        ns-356.awsdns-44.com
        ns-1337.awsdns-39.org
        ns-1752.awsdns-27.co.uk
        ns-614.awsdns-12.net

    Source: the `NS` record set in `project/secrets/worldcities.ca-rrsets-2026-09-21.txt`
    (authoritative 0a export, 2026-09-21), cross-checked against
    `dig +noall +authority NS worldcities.ca @c.ca-servers.ca` the same day. **They are
    written out here so a rollback at a bad moment needs no lookup, no AWS console, no
    `--profile rob`, and no working DNS for worldcities.ca.** If you ever want to re-derive
    them: `awk -F'\t' '$2=="NS"' project/secrets/worldcities.ca-rrsets-2026-09-21.txt`.
    The Route 53 hosted zone (`Z0944732VRZ4NUBNE0FL`) is still intact and still serving
    these four names — that is what makes this rollback work, and it is why 0g forbids
    deleting it. **Do not touch `Z08901851VA0TTXNMTFCZ` (skyideas.com).**
  Who runs it: Rob. Gage runs nothing remote.
  Data-loss window: **no mail is lost while Route 53 and Cloudflare both serve the same
    three Zoho MX** — either answer routes to the same Zoho servers, and neither DNS
    provider ever holds a message. Loss only becomes possible if Cloudflare's MX were
    wrong: senders then queue and retry (typically 24-72 h) and most mail still lands once
    fixed, but a sender with a short queue lifetime bounces. 0c's checklist is what makes
    that case unreachable.
  Mechanism limit: **24 h** — the .ca delegation TTL, measured today at 86400 s. A
    rollback is not instant in either direction. Plan the window accordingly; this is the
    reason the trip is 32 days out and this is happening now rather than in October.
  Rehearsed locally: no. A registrar delegation cannot be rehearsed locally; the
    rehearsal that IS possible is 0c's pre-flip dig against Cloudflare's nameservers, and
    it is a precondition above.
Paste back: the four dig outputs, the Cloudflare status, and the time of the flip
  (0e's 24-hour re-test is counted from it).
  **DONE 2026-09-21 — all pasted back and recorded in the RESULT block at the top of this
  card. Flip time 19:10:10 local. Nothing outstanding in 0d itself.**
```

```
GATE 0e [NEW 2026-09-21] [SETTLED 2026-09-21 — the mailbox question is answered. **THIS IS
CASE A.** No choice to make; run CASE A]: MAIL GATE — prove inbound mail before anything
else proceeds
Plan ref: Gate 0 step 5
Class: remote-data (verification only; nothing in this card changes a record)

    MAILBOX UNDER TEST:   rob@worldcities.ca
    Status: **live Zoho mailbox with a human behind it.** Confirmed by Rob, 2026-09-21,
      with evidence: a message sent 2026-09-21 5:24 PM from
      `Rob Kellington <rob@worldcities.ca>` to `rob.kellington@gmail.com`,
      subject "Test from rob@worldcities.ca - Zoho mail".
    => **RUN CASE A. Do not run CASE B on this domain.**

    **BASELINE RUN: PASSED 2026-09-21 (pre-flip).** Gmail (`rob.kellington@gmail.com`) →
      `rob@worldcities.ca`, delivered sub-second, raw message exported via Zoho's
      "Show original" to `/Users/rob/Downloads/Show-original.eml` (6389 bytes, greppable).
        hop count (`grep -ic '^Received:'`) = **2**, and nothing between sender and Zoho:
          Received: from mail-oa2-f32.google.com (… [74.125.231.96]) by **mx.zohomail.com**
                    with SMTPS id … Mon, 21 Sep 2026 17:41:50 -0700
          Received: by mail-oa2-f32.google.com with SMTP id … for <rob@worldcities.ca>; …
        corroborating: `Authentication-Results: mx.zohomail.com;` ·
          `Received-SPF: pass (zohomail.com: … 74.125.231.96 …)` ·
          `X-ZohoMail-DKIM: pass (identity @gmail.com)`
      **This baseline necessarily travelled ROUTE 53's MX** — the live .ca delegation still
      pointed at the four AWS nameservers when it was sent. That is precisely the "before"
      picture the post-flip run is compared against: same test, same mailbox, different
      nameserver answering. Pre-flight item 6: satisfied.
      **Still outstanding: the post-flip run and the 24-hour re-test (step 6).** The baseline
      passing is not the gate passing.
    **POST-FLIP STATUS, 2026-09-21 evening: the flip HAS happened — 0d PASSED, registry
      confirmed 19:10:10 local — and the post-flip 0e run has NOT been sent yet.** So this
      card is now the single most overdue thing in the project, and it is the one gate whose
      delay costs something: until it runs, nobody knows from a real delivery that inbound
      mail works on Cloudflare. The DNS layer is already strong evidence (three Zoho MX
      answering on four resolvers, and a 2-minute poller that never alerted from the flip
      onward), but **DNS resolving is not a message arriving** — that is this card's entire
      reason for existing, and it is why step 1 alone has never been the gate.
      **Run the post-flip A2 now. Label it "post-flip".** Then the 24-hour re-test, earliest
      **2026-09-22 19:10 local** (24 h after the recorded flip time).
    CASE B below is retained as REFERENCE ONLY, for some future domain that genuinely has
      no mailbox. On worldcities.ca it is not a fallback, not a shortcut, and not an option
      if CASE A is inconvenient: there is a real mailbox, so a real inbound delivery test is
      both possible and required. Nobody should be able to read their way into CASE B here.

**THE TRAP — read this before you decide the mail "works". [ADDED 2026-09-21]**
  Rob's confirming test was **OUTBOUND**: he sent FROM rob@worldcities.ca. That is genuinely
  useful — it proves the mailbox exists and a person can use it — but note carefully what it
  does and does not establish:
    - **Outbound mail does not depend on MX records at all.** It leaves through Zoho's SMTP
      servers. It would keep working perfectly **even if every MX record on this domain were
      deleted.**
    - **MX governs INBOUND only.** Inbound is the only thing this migration can break.
    - So "I sent an email from it and it worked" — the most natural way to check, and the
      most likely misreading of a passing result — **proves nothing about the thing at risk
      here.** A successful send after the flip is not evidence the flip went well.
  Therefore: **step A2 (inbound, from a non-Zoho sender, with a `Received:` line naming
  a Zoho-operated receiving host, and no relay in between) IS the gate.** Everything else in
  this card is supporting detail.
  A3 (outbound) is now known to work already, 2026-09-21, so it is kept as a courtesy
  check only — and it **cannot fail because of this migration**, so a pass there earns
  nothing and a fail there means something else entirely (Zoho account, password, client).

Preconditions: run the whole thing ONCE as a pre-flip baseline (0d precondition) and again
  after the flip, plus the 24-hour re-test in step 6. **No other gate runs between 0d and a
  passing POST-FLIP 0e.** That sentence is unchanged and it is absolute: the post-flip run is
  a hard block on Gates 1, 3, 0f, 4 and 5.

**[AMENDED 2026-09-21, post-flip — SEQUENCING RULING. Alice asked Gage to rule on his own
card, so here is the ruling, with the reasoning, and it is deliberately not a simple yes.]**
  The question: does the **24-hour re-test** block Gates 1, 3, 4 and 5, or is it "required but
  not a blocker"? Step 6 below said "only then does Gate 1 unblock", which reads as a hard
  block on everything. **Alice's reading — required but not blocking — was half right, and
  the half that is wrong is the expensive half.** Split the answer per gate:
    - **Gate 1 — UNBLOCKED NOW, after a passing post-flip 0e. This is a deliberate amendment
      to step 6, not a reinterpretation of it.** Why: Gate 1 is **read-only**. It reads a
      dashboard status and exports a zone. It has no rollback card because it changes nothing,
      its evidence does not decay, and running it early cannot produce a wrong action — at
      worst it produces a status line Rob looks at again later. Step 6's "only then does Gate
      1 unblock" was written when Gate 1 was the first *action* after the flip and the
      conservative default was free. It is not free any more: Gate 1's export is Gate 3's
      baseline, and having it in hand early costs nothing and removes a dependency from the
      critical path. **Post-flip 0e still comes first** — that is not relaxed.
    - **Gates 3, 0f, 4 and 5 — STILL BLOCKED on the 24-hour re-test, and now for a MEASURED
      reason rather than a doctrinal one.** This is where Gage disagrees with Alice, and the
      reason is FINDING 1 and FINDING 3 in the post-flip readings table above: at 19:40 MDT,
      30 minutes after the flip, `1.1.1.1` and `9.9.9.9` were **still serving the eight old S3
      IPs** for the apex from the cached AWS delegation. Run Gate 3 into that and its verify
      curls fetch **the old 2020 S3 page**, scoring `grep -c "Amazon S3"` → 1 and
      `grep -c "World Cities"` → 0 — two documented Gate 3 failures whose documented reaction
      is Gate 3's rollback. **A DNS cache would trigger the teardown of a correct change.**
      That is the same shape of mistake as the 0e literal-hostname defect, which is the
      highest-consequence error found in these cards, and it is avoidable by waiting out a
      window that is 24 h long in a project with 32 days of slack.
      Gate 5 has a second, independent reason to wait: its verify includes a private-browser
      login at `https://worldcities.ca/<slug>/`, and a browser on a resolver still pointed at
      Route 53 will not reach Cloudflare Access at all. **Gate 5 is also the step that makes a
      trip page reachable by other people** — the last place to accept an unreliable check.
  **So: post-flip 0e → Gate 1 may run → 24-hour re-test → then Gates 3, 0f, 4, 5.** The
  practical cost of this ruling is a single evening, and the trip is 32 days out. Nothing here
  is urgent; Gate 3 being reversed for no reason would be.
Blast radius: none — sending and reading two emails to and from a mailbox Rob owns.
  Nothing is configured, nothing is changed, no record is touched.

STEP 0 — TOKEN (both cases)
  Pick one token per run and put it in every subject:   MXTEST-$(date +%Y%m%d-%H%M)
  Label every run explicitly: "baseline / pre-flip", "post-flip", "24h re-test".

STEP 1 — RESOLUTION (both cases; this is the only step that is the same in both)
     dig +short MX worldcities.ca @1.1.1.1
     dig +short MX worldcities.ca @8.8.8.8
     dig +short MX worldcities.ca @<one of the two Cloudflare NS for this zone, from 0c>
  All three -> `10 mx.zoho.com.` / `20 mx2.zoho.com.` / `50 mx3.zoho.com.`
  Anything else, in any of the three -> STOP and run the 0d rollback card.
  What this proves: the DNS layer, which is the layer this migration actually changes.
  What it does not prove: that a message gets delivered. Hence steps 2+.

=== CASE A — rob@worldcities.ca is live. THIS IS THE CASE THAT APPLIES. The real gate. ===
  A2. INBOUND (the test that actually matters — the only step that can detect an MX problem)
      From a NON-Zoho account on another provider send **to rob@worldcities.ca**, subject =
      the token. `rob.kellington@gmail.com` is the obvious sender and is the reverse
      direction of the message Rob already sent on 2026-09-21, which makes it easy to
      compare the two.
      PASS requires ALL THREE [CRITERION (ii) REWRITTEN 2026-09-21 — the earlier version
      would have FAILED a perfectly healthy delivery; see the DEFECT note below]:
        (i)   it arrives within 5 minutes; and
        (ii)  a `Received:` line names a **Zoho-operated inbound host**; and
        (iii) **no hop sits between the sender and that Zoho host.**

      (ii) WHAT COUNTS AS A ZOHO-OPERATED INBOUND HOST
        Accept **`mx*.zoho.com` OR `mx*.zohomail.com`**, and read it as "a receiving MTA
        operated by Zoho under one of Zoho's own domains" — **not as a match against three
        literal strings.** Zoho may greet under other hostnames in its own domains, and it
        is free to change them without telling anyone.
        **Observed real value, 2026-09-21: `mx.zohomail.com`.**
        Why the MX record and the header don't match, stated so nobody treats it as a fault:
        the **MX records** point at `mx.zoho.com` / `mx2` / `mx3`, but the MTA that accepts
        the message stamps the `Received:` line with **its own** greeting name, here
        `mx.zohomail.com` — Zoho's service domain. **A sender connects to one name and gets
        stamped by another; SMTP does not require those to be the same name.** That is
        normal, not a redirect, not a misconfiguration, and not evidence of an MX problem.
        A host in a **non-Zoho** domain in that position IS worth stopping for: paste it.

      (iii) THE HOP TEST — the stronger of the two, and the primary test if the mailbox
      forwards or is an alias
        Count the `Received:` lines and read them **bottom-up** (oldest at the bottom). The
        question is simply: **does anything sit between the sender and the first Zoho host?**
        An intermediate relay shows up as an extra hop **no matter what any host calls
        itself**, which is why this test is stronger than hostname matching.
        2026-09-21 baseline, exactly two hops and nothing in between:
          Received: from mail-oa2-f32.google.com … by mx.zohomail.com with SMTPS …
          Received: by mail-oa2-f32.google.com with SMTP … for <rob@worldcities.ca>;
        (bottom = Gmail handing off internally; top = Gmail → Zoho. Sender, then Zoho. No
         third party.)
        **A mailbox that forwards to Gmail adds hops ON TOP** — that is expected and is not a
        failure. Read bottom-up and ask the question about the BOTTOM of the chain, where the
        sender is, not the top.

      HOW TO CHECK IT MECHANICALLY, rather than by eye
        Zoho's "Show original" **saves a `.eml` file**, so the whole thing is greppable. That
        is how the 2026-09-21 baseline was captured (`/Users/rob/Downloads/Show-original.eml`,
        6389 bytes) and it is the recommended method — export the file, then:
          grep -ic '^Received:' <file>
          grep -i  '^Received:' <file>
          grep -iE 'zoho(mail)?\.com' <file>
        First line = the hop count (**2** on the baseline). Second = the chain, to read
        bottom-up. Third = every Zoho-operated host mentioned anywhere in the message.
      Where to find the headers if you'd rather click:
        Zoho Mail: open the message › More options (⋯) › "Show original" (some versions:
          "View headers"). Labels unverified by Gage — if neither is there, look for
          anything that shows the raw message source.
        If the mailbox forwards to Gmail: Gmail › open it › ⋮ › "Show original".

      SUPPORTING HEADERS — corroboration, NOT the gate
        `Authentication-Results: mx.zohomail.com;`, `Received-SPF: pass (zohomail.com: …)`
        and `X-ZohoMail-DKIM: pass (identity @gmail.com)` all appeared on the baseline. A
        Zoho host naming itself in these is useful **when the `Received:` chain is ambiguous**
        — e.g. a forwarder that rewrites headers. They are supporting evidence only: do not
        pass a run on them alone, and do not fail a run for their absence.

      **Why (ii) and (iii) and not just (i):** arrival alone proves a message reached Rob;
      it does not prove which path it took. (ii) and (iii) are what prove it came in through
      the MX this migration moved.
      Not there in 5 min: check the spam folder once, then treat it as a FAIL, re-read
      step 1's output, and do not proceed to any other gate.

      **THE DEFECT THIS REPLACES — read it, because the cost was not noise.**
      Until 2026-09-21 this card required a `Received:` line naming literally
      `mx.zoho.com`, `mx2.zoho.com` or `mx3.zoho.com`, and emphasised "the hostname, not just
      'zoho'". The real header names **`mx.zohomail.com`** — that string appears nowhere in
      the old criterion. **Read literally, the old card FAILED a healthy, sub-second
      delivery.** Pre-flip that is free. **Post-flip, a 0e failure is the documented trigger
      for the 0d rollback** — so a correct migration would have been reverted on a false
      negative, and undoing that revert is another wait of up to 24 h on the .ca delegation
      TTL. That is the highest-consequence error found in these cards: every other one cost
      noise or a wasted step; this one cost an unnecessary cutover reversal. The lesson kept:
      **a pass criterion written as a literal string match against a vendor's hostname is a
      liability. Say what you are looking for, give the observed value as an example, and
      prefer a structural test (the hop count) over a name match.**
  A3. OUTBOUND — a courtesy check, NOT the gate. [AMENDED 2026-09-21]
      Reply from rob@worldcities.ca to the same external address, token in the subject.
      PASS = it arrives, and its headers show a Zoho sending host.
      **Already known to work: Rob sent from this mailbox successfully on 2026-09-21, before
      any migration step.** Outbound does not depend on MX, so this step CANNOT fail because
      of this migration. Run it if you like the symmetry; a pass here is not evidence about
      the flip, and a fail here points at Zoho, a password or a mail client — not at DNS.
      Never report A3 as the mail gate passing.
  A4. SECOND NETWORK (recommended, not required)
      Repeat A2 from a different provider (Outlook/iCloud/work). Different providers hold
      different resolver caches, so two passes from two networks is much stronger evidence
      than one pass run twice.
  A5. NO NEW ERRORS
      Zoho admin/mail console: no bounce or delivery-failure notifications dated after the
      flip.

=== CASE B — REFERENCE ONLY. DOES NOT APPLY TO worldcities.ca. ===
  **Not for this migration.** worldcities.ca has a live mailbox (rob@worldcities.ca,
  confirmed 2026-09-21), so CASE A is possible and CASE A is required. This section is kept
  for a future domain that genuinely has no mailbox in use — or for the one situation below
  where it becomes relevant here: if CASE A's A2 message never arrives, B2's bounce probe is
  a useful *diagnostic* for working out how far the mail got. It is still not a pass.
  Say plainly what this case can and cannot establish:
    CAN prove: the domain's mail path resolves to Zoho and **Zoho's MX servers accept the
      SMTP connection for this domain and answer for it** — i.e. everything this migration
      touched is intact, end to end, up to the point of mailbox delivery.
    CANNOT prove: that a message lands in a mailbox, that anyone can read it, or that
      outbound sending works. **If mail delivery matters to anyone, CASE B does not prove
      it and must not be written up as if it did.**
  B2. BOUNCE PROBE — the substitute that carries real information
      From a NON-Zoho account (Gmail is fine) send to an address on the domain that is
      certainly not a mailbox:
          mxtest-<token>@worldcities.ca
      Expect a bounce / NDR back in your own inbox, usually within a minute or two.
      Open the NDR and read the raw text (Gmail: ⋮ › Show original). PASS = it names a
      **Zoho host** as the rejecting server, in a line shaped like one of:
          Remote-MTA: dns; mx.zoho.com          (or mx2 / mx3)
          ... said: 550 5.1.1 <...> Recipient address rejected ...
          Reporting-MTA / the "Final-Recipient" block naming a zoho.com host
      **A bounce is the PASS here, not the failure.** It means: your sender resolved
      worldcities.ca's MX, connected to a Zoho server, and Zoho answered authoritatively
      for the domain. That is the whole DNS path this migration changed.
      FAIL, and what each failure means:
        - No reply at all after 15 minutes -> the message may be queued; wait, re-check,
          then treat as a fail. Nothing accepted it and nothing rejected it.
        - The NDR names a NON-Zoho host, or says "no such domain" / "Domain not found" /
          "DNS error" -> the MX are not being seen. STOP, run the 0d rollback card.
        - The message is ACCEPTED (no bounce) -> a catch-all exists and mail is going
          somewhere. That is information: find out where, because it means the domain IS
          receiving and this is really CASE A.
  B3. SMTP-LEVEL CHECK (optional, and know what it is worth)
          nc -vz mx.zoho.com 25
          openssl s_client -starttls smtp -crlf -connect mx.zoho.com:25   (Ctrl-C to exit)
      A banner from a Zoho host proves the target is up and reachable **from this machine**.
      It says nothing about worldcities.ca — it is the same answer for any domain pointed at
      Zoho. Two caveats: many home and mobile ISPs block outbound port 25 entirely, so a
      timeout here is probably the ISP, not Zoho; and this is a plain TCP connection to a
      public mail server, nothing more. Use it only to explain a B2 failure, never as the
      gate itself.
  B4. WRITE THE LIMITATION DOWN
      In the paste-back, in these words or close to them: "0e run as CASE B: no mailbox in
      live use was identified. The MX path to Zoho is proven by DNS resolution (step 1) and
      an authoritative rejection from <mx host> (step B2). **Actual mailbox delivery was
      not tested and is not claimed.**"
  B5. THE OPTION WORTH CONSIDERING INSTEAD
      On a domain with no mailbox, the honest fix is not a better probe: it is to stand up
      (or confirm) one real mailbox or catch-all and run CASE A. That is a separate, small
      job with its own card — **not something to improvise mid-session**.
      **On worldcities.ca this is already done: rob@worldcities.ca exists and is in use
      (confirmed 2026-09-21), so CASE A applies and the mail risk in this migration is real,
      not theoretical.** That is the opposite of the "nobody uses mail here" outcome this
      section was originally written to accommodate.

STEP 6 — THE 24-HOUR RE-TEST. REQUIRED.
  Repeat step 1 and **A2** (inbound to rob@worldcities.ca, headers read) **at least 24 h
  after the flip time recorded in 0d**. Until then, the resolver that answered may still have
  been following the cached AWS delegation, so a pass proves nothing about Cloudflare. **Only
  after this second pass is the migration proven.**
  **The flip time is recorded: 19:10:10 local, 2026-09-21. So this step is earliest
  2026-09-22 19:10 local.** Not "tomorrow morning" — the clock is the registry's, not the
  calendar's.
  That the cached delegation is a real effect and not a precaution is now **measured**: 30
  minutes after the flip, `1.1.1.1` and `9.9.9.9` were still answering the apex from Route 53
  while Cloudflare answered authoritatively. See FINDING 1 above. This step is what confirms
  that window has closed.
  [AMENDED 2026-09-21] The old wording, "and only then does Gate 1 unblock", is superseded by
  the SEQUENCING RULING in this card's Preconditions: **Gate 1 (read-only) may run after a
  passing post-flip 0e; Gates 3, 0f, 4 and 5 wait for this step.**
  Re-sending from the mailbox instead of to it does not satisfy this step — see THE TRAP.

Expect: on SPF/DKIM/DMARC — the 0a export contains **no TXT records at all** (verified from
  the complete, untruncated export, 2026-09-21), so none of SPF, DKIM or DMARC exists on
  this domain today. Do NOT expect `spf=pass` in any header; `spf=none` or `spf=neutral` is
  the correct, unchanged result, and a bounce/NDR may mention a missing SPF — also normal.
  A `spf=fail` means something was ADDED that wasn't there: stop and paste it.
  (Adding SPF/DKIM/DMARC for Zoho is worth doing — later, as its own job with its own gate
  card. It is not part of this migration and must not be smuggled into it.)
Verify: step 1 passes from all three resolvers; **A2 passes all three of its criteria
  (arrival, a Zoho-operated receiving host, no hop in between)**; A5 clean; and step 6 passes
  ≥24 h later. A3 is not part of the verdict.
Rollback card: trigger = step 1 returns anything but the three Zoho MX, OR A2 fails — meaning
  **no inbound within 5 min, or a relay appears between the sender and Zoho, or the receiving
  host is in a NON-Zoho domain.** A Zoho host under a different Zoho hostname than the MX
  record (e.g. `mx.zohomail.com`) is **NOT a failure and NOT a rollback trigger** — see A2's
  DEFECT note; that mistake would revert a healthy migration ·
  action = run the 0d rollback card (nameservers back to the four AWS names at Hover,
  spelled out there) · run by Rob · data-loss window: as stated in 0d — none while Route 53
  and Cloudflare both serve the same three MX · mechanism limit: 24 h (.ca delegation TTL,
  measured) · rehearsed: yes — the identical procedure was run as a pre-flip baseline and
  its result is on file. **If the baseline itself failed, the flip does not happen.**
Paste back, per run: the three dig outputs; the A2 arrival time; **the hop count
  (`grep -ic '^Received:'`) and the full `Received:` chain** from the message that arrived
  **at** rob@worldcities.ca. Redact addresses as you like, but **keep every host name in the
  `Received:` lines visible** — the chain, not one string, is the evidence, and a paste-back
  without it is not a passing run. Add the `Authentication-Results` / `Received-SPF` /
  `X-ZohoMail-DKIM` lines if they help. (If B2 was used as a diagnostic after a failed A2,
  paste its remote-MTA/SMTP-reply lines too, labelled as a diagnostic, not as a pass.)
  Label each run baseline / post-flip / 24h re-test.
```

```
GATE 0f [NEW 2026-09-21]: Decide what `www.worldcities.ca` does
Plan ref: Gate 0 step 6 · run AFTER Gate 3 and alongside Gate 3b, never before 0e passes
Class: DNS/zone
Preconditions: 0e passed including the 24-hour re-test; Gate 3 done (apex serves the
  placeholder); Gate 3b's Bulk Redirect list exists.
Gage's recommendation: **option (a), redirect www to the apex.**
  (a) REDIRECT www -> apex (recommended). One origin, one Access app, nothing new to
      protect. A trip-mate who types "www." still lands on the protected site.
      Cost: one more entry in the account-level Bulk Redirect list. The account budget is
      5 lists / 15 rules / **10,000 redirects**, shared with skyideas.com and
      minus1over12.com (Rex, 2026-09-21) — an entry costs a redirect, not a rule, so this
      is negligible.
  (b) CNAME www to the Pages project (a second custom domain). www would serve the same
      files — and that is the problem: **the Gate 4 Access app covers `worldcities.ca`
      only, so `www.worldcities.ca/<slug>/` would serve the trip page with no login.**
      It is only safe with a second Access app per trip on www: double the Gate 4 work,
      double the chance of missing one, for zero user-visible benefit. Not recommended.
  (c) LEAVE www DARK (today's state after Gate 0: NXDOMAIN). Zero risk, worst UX — someone
      who types www gets a browser DNS error with no hint that the site exists. Acceptable
      fallback if (a) hits a limit; also the correct choice if you'd rather not touch the
      zone again before the trip.
Blast radius: adds ONE name (`www`) to the worldcities.ca zone and ONE entry to an
  account-level redirect list that skyideas.com and minus1over12.com also draw on. No
  existing record changes; **no MX is touched** (the verify below proves it).
Do exactly, option (a) (dashboard):
  1. DNS › Records › Add record:
       Type = AAAA · Name = www · IPv6 = 100:: · Proxy status = **Proxied (orange)** ·
       TTL = Auto
     (`100::` is the IPv6 discard prefix. The record exists only so traffic reaches
      Cloudflare's edge, where the redirect runs. **Grey-cloud here would send visitors
      into a black hole** — the orange cloud is the whole point.)
  2. Bulk Redirects › the list from Gate 3b › Add URL redirect:
       Source = www.worldcities.ca · Target = https://worldcities.ca · Status = 301
       Tick: Preserve query string · Subpath matching · Preserve path suffix
       Do NOT tick "Include subdomains".
Expect: the record shows Proxied; the list shows two entries.
Verify:
  curl -sI https://www.worldcities.ca/ | grep -iE "^(HTTP|location)"
    -> 301, location: https://worldcities.ca/
  curl -sI "https://www.worldcities.ca/x/y?q=1" | grep -iE "^(HTTP|location)"
    -> 301, location: https://worldcities.ca/x/y?q=1
  dig +short MX worldcities.ca @1.1.1.1
    -> still the three Zoho MX. Adding www must not touch mail; check it anyway.
  (A TLS error on www right after adding it usually means Universal SSL hasn't issued yet.
   Wait and re-check before concluding anything. Universal SSL covers the apex and one
   level of subdomain, so www is in scope.)
Rollback card: trigger = a redirect loop, or www serving content instead of redirecting ·
  action = delete the redirect ENTRY first, then the www AAAA record (that order: removing
  the record first leaves an entry pointing at a name that no longer reaches the edge) ·
  run by Rob · data-loss: none · limit: none (proxied record, no meaningful TTL wait) ·
  rehearsed: no.
Paste back: the two curl results, the MX dig, and which option you chose.
```

```
GATE 0g [NEW 2026-09-21]: The Route 53 hosted zone is the rollback — when it may be deleted
Plan ref: Gate 0 step 7
Class: remote-data (destructive — deliberately NOT written as a runnable card here)
**Do not delete the Route 53 hosted zone at 0d, at 0e, or in this session.** While it
exists and holds the correct MX, the 0d rollback works. Delete it and the rollback
becomes "recreate a zone, get NEW nameserver names, re-enter them at Hover, wait out the
24 h delegation TTL" — which is why the 0a export matters more than the zone does.
Every one of these must be true before deletion is even discussed:
  1. 0e passed twice, the second run ≥24 h after the flip.
  2. Mail has worked on Cloudflare continuously for **at least 14 days** (Alice/Rob,
     2026-09-21) with no bounce reports.
  3. It is not the trip window: **do no DNS work between 2026-10-23 and 2026-10-30.**
  4. A final export of BOTH sides is archived outside the repo (S7: re-run 0a with a new
     date — **`aws --profile rob`** — and re-export the Cloudflare zone).
  4b. The zone id in the deletion command is read character by character and is
     **`Z0944732VRZ4NUBNE0FL`**. `Z08901851VA0TTXNMTFCZ` is skyideas.com and is a different
     job; deleting the wrong one here is unrecoverable.
  5. `dig +noall +authority NS worldcities.ca @c.ca-servers.ca` shows only the two
     Cloudflare nameservers.
  Earliest date that satisfies 1 and 2, if the flip happens 2026-09-22: about 2026-10-06.
  Condition 3 then pushes the sensible date past the trip. **Recommendation: leave it
  until November.** Route 53 bills per hosted zone per month (small; Gage did not verify
  the current rate — read the AWS bill). Six weeks of that is a cheap rollback.
Note for whoever writes that card: `delete-hosted-zone` refuses while any record set
  other than the default SOA and NS exists, so the MX and anything else must be removed
  with `change-resource-record-sets` first — a second irreversible step, needing its own
  S7 safety export immediately before it. (AWS's documented behaviour; Gage did not verify
  it against a live zone.) It is left unwritten here on purpose: it should not be
  convenient.
Rollback card: **none exists.** Deleting a hosted zone is irreversible and releases its
  nameserver names. That is the entire argument for waiting.
```

---

```
GATE 1 [REWRITTEN 2026-09-21, post-flip — this card was written to confirm a state that has
since been MEASURED. Most of it is now evidence to point at, not work to do.]: Establish the
post-migration baseline for worldcities.ca
Plan ref: brief step 1
Class: DNS/zone (read-only)

**WHAT IS ALREADY ESTABLISHED. Do not re-verify any of this — it was measured after the
flip, on 2026-09-21, and the readings are in the post-flip table near the top of this Deploy
section. Re-running them adds no information; it only adds the chance of misreading one.**
  - **Registry delegation:** `dig +noall +authority NS worldcities.ca @c.ca-servers.ca` →
    `bella.ns.cloudflare.com` + `gabriel.ns.cloudflare.com`, TTL 86400. Flipped 19:10:10
    local, watched onto the wire by a 2-minute poller. Cache-independent: this is the registry.
  - **Cloudflare is authoritative:** `dig NS worldcities.ca @bella.ns.cloudflare.com` →
    `flags: qr aa`. Not a pending zone; it is answering for the domain.
  - **Mail is intact on four independent resolvers:** `1.1.1.1`, `8.8.8.8`, `9.9.9.9`,
    `208.67.222.222`, each returning all three `10 mx.zoho.com` / `20 mx2.zoho.com` /
    `50 mx3.zoho.com`. Plus a 2-minute MX poll from the flip onward that never alerted.
  - **The apex is empty:** `dig +short A worldcities.ca` → nothing; authoritatively NOERROR
    with `ANSWER: 0` (NODATA, because the name exists and carries MX + SOA). **`www` is
    NXDOMAIN at Cloudflare.** Both are the designed state until Gate 3 / 0f respectively.
  - **No DNSSEC:** `dig +short DS worldcities.ca` → empty, unchanged since before the flip.
  - **The zone's record inventory:** SOA · NS ×2 · MX ×3, six record lines, nothing else.
    From `project/secrets/cf-import-2026-09-21.txt` (0c), and Gage re-ran the corrected
    counts on it post-flip: **3** MX and **0** A/AAAA/CNAME/TXT/CAA/SRV.
  The only caveat, and it is important rather than pedantic: **a public recursive resolver may
  still answer the apex and `www` from the cached Route 53 delegation for up to 24 h** — two
  of the four were still doing so 30 minutes after the flip. See FINDING 1. That is why Gates
  3/0f/4/5 wait for the 24-hour re-test even though this card does not.

**WHAT ROB STILL HAS TO DO. Two things, both in the dashboard, and only one of them is a
check — the other produces an artifact that Gate 3 cannot run without.**
Preconditions:
  - **A PASSING POST-FLIP 0e run.** Hard block, not relaxed. (The 24-hour re-test is NOT a
    precondition of *this* card — see the SEQUENCING RULING in 0e. This card is read-only,
    its evidence does not decay, and running it early takes a dependency off the critical
    path. It IS a precondition of Gate 3.)
  - The pre-migration export remains the Route 53 one from 0a
    (`project/secrets/worldcities.ca-rrsets-2026-09-21.json` — 5 record sets, `no-more-pages`;
    **not** the superseded `-route53-` pair beside it).
Blast radius: **none. Every step is a read or an export.** No record changes, no setting
  changes, nothing billed. Sibling zones `skyideas.com` and `minus1over12.com` are separate
  zones and are not read or touched here; this card does not go near the one genuinely shared
  object in this deploy (the account-level Bulk Redirect list from 3b / 0f).
Do exactly (dashboard):
  1. dash.cloudflare.com › Websites (Domains) › worldcities.ca
     **Read the zone status. It must say "Active".**
     This is the one fact in this card that Gage cannot measure from outside — `dig` proves
     Cloudflare is answering authoritatively (it is), but "Active" is Cloudflare's own
     internal acknowledgement that the delegation check passed, and **Gate 4 requires an
     active zone in the account.** So this is not a formality: it is the specific
     precondition that unblocks Access.
     If it still says "Pending Nameserver Update": click "Check nameservers now" and give it
     a few minutes. The registry has flipped, so this should clear. If it is still pending
     after ~30 min with the registry showing Cloudflare, **stop and paste both** — that
     combination is something Gage has not seen and will not guess at.
  2. DNS › Records › Import and Export › **Export** → save as
       project/secrets/cf-zone-<date>.txt
     then copy it to ~/Backups/worldcities-dns/ and checksum both (0a's standing rule for
     every export in this project; `project/secrets/` is gitignored — `.gitignore:41`,
     re-verified 2026-09-21 — but it lives in the working tree, so `git clean -fdx` would
     take it).
     **This export is the whole point of the card.** Gate 3's verify diffs the MX lines
     before-and-after against it to prove that attaching a website did not move a mail
     record. Without this file that check cannot be run, and Gate 3 loses its only
     mail-safety evidence. `cf-import-2026-09-21.txt` from 0c is a pre-flip export of the
     same zone and would *probably* serve — but "probably" is not what a mail-safety
     baseline should be, and taking a fresh one costs one click.
Expect: status **Active**; a BIND file whose record lines are SOA · NS ×2 · MX ×3.
Verify (local, on the file you just saved — no network):
    cd /Users/rob/Documents/GitHub/Rob/worldcities/project/secrets
    CF=cf-zone-<date>.txt
    grep -v '^;' "$CF" | grep -vE '^[[:space:]]*$'
    grep -v '^;' "$CF" | grep -ciE "[[:space:]]MX[[:space:]]"
    grep -v '^;' "$CF" | grep -ciE "[[:space:]](A|AAAA|CNAME|TXT|CAA|SRV)[[:space:]]"
  → six record lines (SOA, NS ×2, MX ×3), then **3**, then **0**.
  **`grep -v '^;'` is not optional** — this is the 0c incident: a Cloudflare BIND export is
  mostly comments, and without the filter these return a false 4 (the `;; MX Records` section
  header) and a false 1 (the word "a" in the boilerplate "…before use on a production").
  Gage re-ran exactly these three lines against the existing 0c export on 2026-09-21 and got
  six lines, 3 and 0. The MX TTL exports as `1` = Cloudflare's "Auto"; the served value is
  300. **Do not "fix" the 1.**
  A non-zero on the last count before Gate 3 means something exists at the apex or `www` that
  should not: **stop and send it to Gage via Alice** rather than deleting it — Gate 3's blast
  radius below is written on the premise that the apex is empty.
Rollback card: **N/A — read-only.** Nothing to roll back, which is precisely why this card
  does not need to wait for the 24-hour re-test.
Paste back: the zone status (the literal word on screen), and the three grep outputs. Say
  where the export landed and confirm the second copy + checksums.
```

```
GATE 2 [** PASSED 2026-09-21 **]: Create Pages project "worldcities" with the placeholder
only (direct upload)
Plan ref: brief step 2
Class: deploy
RESULT 2026-09-21 (Rob ran it; pasted output):
  deployment URL   https://2ca4e8dc.worldcities.pages.dev   <- 3b's <hash>, keep it
  grep -c "World Cities"  -> 2          (the amended expectation; `1` would have been a
                                         false failure against the original card)
  robots.txt -> Disallow: /   ·   x-robots-tag -> noindex, nofollow
  /no-such-page/ -> HTTP/2 404          (so Pages is NOT in SPA mode — 404.html uploaded)
  bare worldcities.pages.dev served the placeholder, which proves this is the PRODUCTION
    deployment, not a `vscode` preview. Slug-leak probe on the root -> 0.
  **Re-run this card as-is** for the Gate 3b / Gate 5 rollback ("placeholder-only deploy"),
  with a fresh `mktemp -d` folder each time.
Preconditions: local build output (see "Verified locally" in Gage's report);
  uv run tripsite/build.py trips/mexico-city-2026.md exits 0.
  [AMENDED 2026-09-21] **No DNS dependency: this gate can run today, before Gate 0.**
  It creates a *.pages.dev hostname only and touches no zone.
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
Verify: curl -s https://worldcities.pages.dev/ | grep -c "World Cities"   -> 2
          [AMENDED 2026-09-21] was "-> 1", which was wrong. The placeholder carries the
          string on TWO lines (<title> and <h1>). Verified locally 2026-09-21:
            grep -c "World Cities" dist/index.html   -> 2
            grep -n "World Cities" dist/index.html   -> line 10 <title>, line 17 <h1>
          A 1 here means you are NOT looking at this placeholder.
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
GATE 3 [SHARPENED 2026-09-21, post-flip — the blast radius was written when the apex was
unknown. It is now known precisely, and the verify had two defects that the measured state
exposed.]: Attach custom domain worldcities.ca to the Pages project   Plan ref: brief step 3
Class: DNS/zone
Preconditions:
  - **Post-flip 0e PASSED, and the 24-HOUR RE-TEST PASSED.** Both. This gate is on the far
    side of the re-test — see the SEQUENCING RULING in 0e for why, and FINDING 3 for the
    measured reason. Earliest possible: **2026-09-22 19:10 local.**
  - Gate 1 done: zone status **Active**, and `cf-zone-<date>.txt` saved. **That export is
    this card's mail-safety baseline — without it the MX diff below cannot run.**
  - Gate 2 verify passed (2026-09-21).
  - **Before you click anything: confirm your own resolver has switched.**
      dig +short A worldcities.ca @1.1.1.1
    Eight S3 IPs means that resolver is still on the cached Route 53 delegation and **this
    card's verify will lie to you** (FINDING 3). Nothing printed = it has switched. Wait, or
    the verify below tells you to roll back a change that was correct.
Blast radius [REWRITTEN 2026-09-21 — now exact rather than cautious]:
  **This adds an apex CNAME to an empty apex. No sibling record is at risk, and that is
  measured, not hoped.** The complete contents of the `worldcities.ca` zone are **SOA · NS ×2
  · MX ×3 and nothing else** — six record lines, confirmed by the corrected counts on the
  post-flip export (3 MX, 0 A/AAAA/CNAME/TXT/CAA/SRV) and by authoritative digs: the apex
  returns NODATA for `A`, `www` returns NXDOMAIN. The Route 53 apex and `www` S3 aliases were
  deliberately not carried over (Rob's 2026-09-21 decision), so:
    - there is **no existing apex A/AAAA/CNAME for this step to overwrite** — it creates,
      it does not replace;
    - the **only** records that exist alongside it are SOA, NS and the three Zoho MX, and
      Cloudflare owns SOA and NS;
    - therefore the entire risk surface of this gate is **the three MX records**, and the one
      question worth asking afterwards is "did they move?" A website change must never move a
      mail record — the diff in Verify is what proves it didn't.
  Sibling zones `skyideas.com` and `minus1over12.com` are separate zones with separate
  delegations: not read, not changed. No account-level object is touched here (Bulk Redirects
  are 3b / 0f, not this card).
  **WHAT THE CORRECT PRE-GATE-3 STATE LOOKS LIKE — so nobody reads it as breakage.** Right
  now, and until this gate runs, `worldcities.ca` **serves no website at all.** Expect all of:
      dig +short A worldcities.ca                     -> nothing
      dig worldcities.ca A @bella.ns.cloudflare.com   -> NOERROR, ANSWER: 0   (NODATA)
      curl -sI https://worldcities.ca/                -> no response; connection fails
      a browser                                       -> a DNS/"can't reach" error
  **All four of those are correct.** The apex is *supposed* to be dark between 0d and this
  gate — the 2020 S3 placeholder was dropped on purpose and nothing has replaced it yet. Note
  particularly that the apex is **NODATA, not NXDOMAIN** (the name exists; it carries the MX),
  so do not go looking for a leftover record because the status said NOERROR — read
  `ANSWER: 0`. And **mail is entirely unaffected by all of this**: delivery follows MX, never
  the apex A record, which is what the four-resolver MX check after the flip demonstrated.
  The one thing that is NOT a clean signal: a resolver still on the cached AWS delegation will
  still serve the old S3 page (FINDING 1). So "I can still see the old site" is also not
  breakage — it is a stale cache, and it is the reason for the resolver check in the
  preconditions above.
  If a fresh Gate 1 export ever shows an apex or `www` A/AAAA/CNAME, **stop and send it to
  Gage via Alice** — that contradicts everything in this blast-radius statement and the
  statement is what makes this gate safe.
Do exactly (dashboard):
  Workers & Pages › worldcities › Custom domains › Set up a domain
  Domain = worldcities.ca › Continue › Activate domain
Expect: domain status goes from "Initializing" to "Active" (SSL can take a few minutes).
  DNS › Records shows a new proxied (orange-cloud) apex CNAME: worldcities.ca -> worldcities.pages.dev
Verify — **RUN THESE IN ORDER. The order is load-bearing; see the two defects below.**
  STEP V1 — authoritative, cache-proof, and the check that actually proves the gate:
        dig worldcities.ca CNAME @bella.ns.cloudflare.com
        dig worldcities.ca A     @bella.ns.cloudflare.com
          -> the apex now answers with the Pages target / proxied Cloudflare addresses
             instead of NODATA. Asking Cloudflare's own nameserver bypasses every cache, so
             **this is the one verify line that cannot be fooled by the delegation window.**
             Run it first and judge the gate on it.
  STEP V2 — is my resolver even looking at Cloudflare yet?
        dig +short A worldcities.ca @1.1.1.1
          -> NOT the eight S3 IPs. If it still is, **stop here**: every curl below will fetch
             the old S3 page and score as a failure. That is a stale cache, not a bad gate.
             Wait for the delegation cache and re-run. Do NOT roll back on it.
  STEP V3 — only now, the content checks, and **in this order**:
        curl -sI https://worldcities.ca/ | head -1                 -> HTTP/2 200
        curl -s  https://worldcities.ca/ | grep -c "World Cities"  -> 2
        curl -s  https://worldcities.ca/ | grep -c "Amazon S3"     -> 0
        curl -sI https://worldcities.ca/ | grep -ci "AmazonS3"     -> 0
          [AMENDED 2026-09-21] the "World Cities" count was "-> 1"; the placeholder carries
          the string on two lines (<title>, <h1>). Verified locally:
          grep -c "World Cities" dist/index.html -> 2.
          The S3 checks are real, not decorative: the live 2020 page fetched on 2026-09-21
          contained "Amazon S3" exactly once in its body and sent "Server: AmazonS3"; this
          project's placeholder contains neither (grep -c "Amazon S3" dist/index.html -> 0,
          verified locally). The old page says "WorldCities.ca" with no space, so it also
          scores 0 on the "World Cities" check — **the greps only identify the page when read
          together.**
  **DEFECT THIS ORDERING FIXES — measured 2026-09-21, 30 min after the flip.**
  `curl -s https://worldcities.ca/ | grep -c "Amazon S3"` returned **0** on this machine —
  the value written above as a PASS — **while the apex did not resolve at all and the fetch
  returned nothing.** An empty body scores 0 on every content grep, so that line is satisfied
  by a completely dead site. **It proves nothing unless `head -1` has already shown
  HTTP/2 200.** Hence V3's order: liveness first, then identity. This is the mirror image of
  the 0e literal-hostname defect — that one failed a healthy state, this one passes a dead
  one, and a false pass on a mail-adjacent cutover is the more expensive of the two.
  STEP V4 — **THE MAIL CHECK. Never skip it, and never skip it because "this is only a
  website change".** That is exactly the assumption it exists to disprove: the whole risk
  surface of this gate is the three MX records (see Blast radius), and a website change must
  not move a mail record. Keep this check on every future run of this card.
        cd /Users/rob/Documents/GitHub/Rob/worldcities/project/secrets
        re-export the zone from the dashboard as cf-zone-<today>.txt, then:
        grep -v '^;' cf-zone-<gate1-date>.txt | grep -iE "[[:space:]]MX[[:space:]]" | sort > mx-before.txt
        grep -v '^;' cf-zone-<today>.txt      | grep -iE "[[:space:]]MX[[:space:]]" | sort > mx-after.txt
        diff mx-before.txt mx-after.txt          -> NO OUTPUT
        dig +short MX worldcities.ca @1.1.1.1    -> the three Zoho MX
        dig +short MX worldcities.ca @8.8.8.8    -> the same three
          The `grep -v '^;'` is the 0c incident fix and it is **already applied here** — it
          keeps the `;; MX Records` section header out of both files. Without it both files
          gain a comment line, they still diff clean, and the count silently becomes 4: the
          check would keep "passing" while measuring the wrong thing. Each file must hold
          **exactly three record lines** — check that, not just the empty diff:
        wc -l < mx-before.txt ; wc -l < mx-after.txt     -> 3 and 3
          Any diff output, or a count that isn't 3 = mail records moved during a website
          change. **STOP and roll back**, and unlike a curl failure this one is not a caching
          artifact — an export is a read of the zone itself, not of a resolver's memory.
        Finally, the full zone diff: **only** the apex record for the Pages project was added.
Rollback card (written before the cutover step, not after):
  Trigger — **one of these two, and nothing else:**
    (1) **V4 fails** — an MX line moved, or `mx-before/after` isn't 3 lines. Unambiguous:
        an export reads the zone, not a cache.
    (2) the apex still does not serve after 30 min **AND V1 shows Cloudflare's own
        nameserver not returning the Pages target** — i.e. the zone really wasn't changed.
  **NOT a trigger, explicitly** [ADDED 2026-09-21, and this is the whole point of FINDING 3]:
    a failing curl, an "Amazon S3" hit, or a 0 on the "World Cities" count **while V2 shows
    your resolver still holding the eight S3 IPs.** That is the delegation cache, not this
    gate. Rolling back on it would tear down a correct change and cost another wait. If V1
    says Cloudflare is serving the Pages target, the gate worked — wait for the cache.
  Action (only if a real trigger fires): BOTH (1) Custom domains › worldcities.ca › Remove,
    AND (2) DNS › Records › delete the apex CNAME worldcities.ca -> worldcities.pages.dev;
    then restore any changed record from the Gate 1 export (`cf-zone-<date>.txt` — that file
    is the reason Gate 1 exists).
  Who runs it: Rob. · Data-loss window: none — nothing here holds data; the placeholder is
    rebuildable and no trip content is uploaded until Gate 5. Mail is not in this gate's
    data path at all, which V4 is what proves. · Mechanism limit: none — a proxied apex
    record is added and removed at the edge, with no meaningful TTL wait (unlike 0d, this is
    NOT a 24-hour instrument). · Rehearsed: no (dashboard-only step); the local half is
    rehearsed in that the placeholder served 200 from `python http.server`.
Paste back: V1's two digs, V2's dig, all four V3 curls, V4's diff + the two `wc -l` counts +
  both MX digs, and the new DNS record line.
```

```
GATE 3b [** PASSED 2026-09-21 — steps 1-2 done and verified; step 3 NOT AVAILABLE, deferred,
see the amendment in step 3 **]: Lock down *.pages.dev: redirect everything to worldcities.ca
Plan ref: Rex 2026-09-18
Set up once for the project, not per trip. Must pass before any Gate 5.
Class: DNS/zone (account-level edge redirect)
RESULT 2026-09-21 (Rob ran it; pasted output):
  List `worldcities_pages_dev` + rule created and **deployed**.
  The account was at **0 of 5 Bulk Redirect lists used** — there was no sibling list from
    skyideas.com or minus1over12.com to work around. The shared-quota warning below was
    correct as written, but turned out moot. It still applies to 0f, which adds a second
    entry to this same list.
  bare worldcities.pages.dev/           -> 301 location: https://worldcities.ca/
  worldcities.pages.dev/any/path?x=1    -> 301 location: https://worldcities.ca/any/path?x=1
                                           (path AND query preserved)
  2ca4e8dc.worldcities.pages.dev/       -> 301 location: https://worldcities.ca/
    and it returned **200 before the rule existed** — the baseline was taken first, so the
    301 is proven to be the rule's doing, not assumed.
  2ca4e8dc.worldcities.pages.dev/mexico-city-2026-6b9638/
                                        -> 301 -> https://worldcities.ca/mexico-city-2026-6b9638/
    **That is the hash-preview leak path closed** — the exact vector this card exists for.
  worldcities.ca still served 200 from S3 over http: no redirect loop.
  Also settled: the dashboard did NOT refuse to create the rule without an active zone in
    the account, so Rex's 2026-09-18 note held and 3b really has no DNS dependency.
Preconditions: [AMENDED 2026-09-21] **Gate 2 verify passed. That is all.**
  This was "Gate 3 verify passed"; it doesn't need to be. The redirect's SOURCE is
  `worldcities.pages.dev` (a Cloudflare-owned hostname that exists as soon as Gate 2
  runs) and its TARGET is a URL that does not have to resolve yet. The verify below
  checks the 301 and its `location:` header, not what the target serves.
  **So 3b has no DNS dependency and can run today, before Gate 0** — and it is worth
  running early, because it is the thing that keeps trip pages off *.pages.dev later.
  Gate 3 is still required before Gate 5, just not before this card.
  (If the dashboard refuses to create the rule without an active zone in the account,
   that contradicts Rex's 2026-09-18 note: stop, paste it, and run this after Gate 0
   instead. It costs nothing to find out now.)
Blast radius: an account-level Bulk Redirect whose source is the hostname
  worldcities.pages.dev and its subdomains (hash previews, branch aliases). Other
  Pages projects' *.pages.dev hostnames don't match the source and are unaffected.
  No record in the worldcities.ca zone changes.
  [AMENDED 2026-09-21] Bulk Redirects are an ACCOUNT-level object, so this is the one step
  in the whole deploy that reaches outside this project. The account budget is 5 lists /
  15 rules / 10,000 redirects, shared with **skyideas.com** and **minus1over12.com**
  (Rex, 2026-09-21). This card consumes 1 list, 1 rule and 1 redirect; Gate 0f adds a
  second redirect to the same list. Neither sibling's zone, records or site is read or
  changed — only the shared quota moves, by a rounding error. Before saving, glance at the
  existing lists: if a sibling already has one, leave it alone and create this one beside it.
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
  3. [AMENDED 2026-09-21 — **DO NOT GO LOOKING FOR THIS TODAY. It is not there.**]
     The optional backup was: Workers & Pages › worldcities › Settings › General ›
     "Enable access policy", which per Rex (2026-09-18) creates an Access app on
     *.worldcities.pages.dev covering every <hash> URL and branch alias.
     **Rob looked for it on 2026-09-21 and that control does not exist in the dashboard**
     under that label or anywhere obvious on that page. Do not hunt for it again and do not
     improvise a substitute.
     Alice's hypothesis, recorded as EXPLICITLY UNVERIFIED: the control may only appear once
     **Zero Trust is onboarded on the account**, which has not happened yet — that is Gate 4.
     Gage has not confirmed this and will not guess at Cloudflare's current UI; if it matters
     later, it goes to Rex as a question, not to a dashboard hunt.
     Why skipping it is fine: it was optional, and it covers **neither** bare
     `worldcities.pages.dev` **nor** `worldcities.ca`. Steps 1-2 — which are done and
     verified, including on the real `<hash>/<slug>/` leak path — are what actually close the
     hole. **DEFERRED: re-check this control after Gate 4.** If it appears then, turning it
     on is a free second layer; if it still isn't there, nothing is lost and the Gate 3b
     rollback uses option (a) instead of (b).
Expect: the rule is listed as deployed/enabled.
Verify (all must pass):
  curl -sI https://worldcities.pages.dev/ | grep -iE "^(HTTP|location)"
    -> 301, location: https://worldcities.ca/
  curl -sI "https://worldcities.pages.dev/any/path?x=1" | grep -iE "^(HTTP|location)"
    -> 301, location: https://worldcities.ca/any/path?x=1
  curl -sI https://<hash>.worldcities.pages.dev/ | grep -iE "^(HTTP|location)"
    (the <hash> URL from Gate 2's output; on 2026-09-21 that was 2ca4e8dc)
    -> 301, location: https://worldcities.ca/
  [ADDED 2026-09-21 — the probe that actually tests the leak vector, and it passed]
  curl -sI https://<hash>.worldcities.pages.dev/<slug>/ | grep -iE "^(HTTP|location)"
    -> 301, location: https://worldcities.ca/<slug>/
    A hash URL plus a real slug is how a trip page would leak. Re-run this line after
    EVERY Gate 5 upload, using that upload's new <hash>: a new deployment gets a new
    hostname, and the Bulk Redirect's "Include subdomains" is what covers it.
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
        [AMENDED 2026-09-21] **This control could not be found in the dashboard on
        2026-09-21** (see step 3 above). Until it is confirmed to exist — re-check after
        Gate 4 — treat option (a), deleting deployments, as the ONLY available path here.
        In a live leak, do not spend time looking for (b): run (a).
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
GATE 4 [ALLOWLIST FILLED IN 2026-09-21]: BILLING GATE. Cloudflare Access app on
worldcities.ca/<slug> (one per trip)
Plan ref: brief step 4; Rex 2026-09-18
Class: billing (first time only) + DNS/zone (edge access policy)
Preconditions:
  - Gate 3 and Gate 3b verify passed. (3b passed 2026-09-21; Gate 3 is still to run.)
  - The 24-hour re-test passed — Gate 4 sits behind Gate 3, which sits behind it.
  - **BILLING: Rob's explicit, in-session OK to put a payment method on file. NOT YET
    GIVEN as of 2026-09-21** — Alice has put the question to him and he has not answered.
    **This gate does not start without that answer.** A plan saying "Rob will approve
    billing" is not Rob approving billing today; this line stays until he says the words.
    What is being approved, stated plainly so the answer is informed:
      · Zero Trust onboarding asks for a **payment method even on the Free plan**, which is
        **$0/month** (Rex, 2026-09-21). Card on file at $0.
      · Free plan = **50 seats. 2 will be in use** (see the arithmetic below). There is no
        per-login charge and no metered component on this plan.
      · The card stays on file until Rob removes it. That is the actual cost of this gate:
        not money, but a stored payment method on an account that did not have one.
    If Rob declines: there is **no other way to put a private trip page on a custom domain**
    at this tier — the alternative is not a cheaper gate, it is a different project. Stop and
    hand it back to Alice rather than improvising an unprotected upload.
  - **SEAT ARITHMETIC, so nobody wonders whether two people will blow a limit:**
      50 seats on Free · **2 in use** (rob.kellington@gmail.com, Lucie's Gmail (project/secrets/access-allowlist.txt))
      · 48 spare.
    **A seat is per USER, not per login.** Rob logging in on a phone, a laptop and a borrowed
    tablet is **one seat**, not three; logging in again next week is still one seat. So the
    number that matters is the length of the allowlist, and it is 2. Seats are released by
    **seat expiration**, set to 1 month below — but with 2 of 50 used, seat expiration is
    housekeeping here, not a constraint. It would only start to matter at roughly 25× the
    current invite list.
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
      Session duration = **1 month**
        [AMENDED 2026-09-21 — was "1 week or shorter"; recorded so the choice is auditable]
        Why longer, not shorter: the trip runs 2026-10-23 -> 2026-10-30, eight days. A
        trip-mate who opens the link the day before flying would, on a 1-week cookie, be
        forced to re-authenticate mid-trip — by email, with a PIN that expires in 10
        minutes, possibly with no working data connection in Mexico City. That failure
        lands exactly when the page is most needed and there is nothing Rob can do about
        it from another country. 1 month spans "a week before" to "a week after" in one
        session.
        The trade-off, stated: a session that lives a month is a month of access from a
        device that is lost or stolen with the browser unlocked. The content is a trip
        itinerary, not credentials, so Gage reads that as the smaller risk of the two.
        [NOTE 2026-09-21] **How much that trade-off costs depends on the undecided
        `hotel_display` value** (a Gate 5 precondition): under `exact` a stolen unlocked
        device shows the stay's name, address and Maps link; under `approximate` it shows a
        400 m circle; under `hidden`, nothing. That does not change the recommendation of 1
        month — an eight-day trip on a one-week cookie forces a mid-trip re-auth by email PIN
        possibly with no data connection, which is the worse failure — but it is the honest
        statement of what a long session exposes, and Rob should read it alongside the
        `hotel_display` decision rather than separately.
        If a device IS lost: Zero Trust › Access controls › the app › the policy › remove that
        email, **and** revoke the user's sessions (Zero Trust › My Team / Users › the user ›
        Revoke). Both steps — removing the address does not by itself end a live session. That
        two-step mitigation is what this choice depends on; it is not "nothing can be done".
        Seat expiration (set once, above) is a separate setting and stays 1 month.
      Policies › Create a new policy
        Policy name = trip-mates · Action = Allow
        Include › Emails — **THE ACTUAL LIST, confirmed by Rob 2026-09-21. Exactly two
        addresses, ONE PER POLICY ENTRY (not one entry holding both, not a comma-separated
        string — Access matches an entry against the whole address):**

            rob.kellington@gmail.com
            Lucie's Gmail (project/secrets/access-allowlist.txt)

          That is the whole allowlist. **Two entries, nothing else, no domain-wide rule, no
          "anyone with a link".** Type them carefully: a typo here does not error, it silently
          creates an address that can never log in, and the login page says "code emailed" to
          everyone — including addresses that are not on the list — so a typo looks exactly
          like a working setup until someone can't get in. **Read both addresses back off the
          saved policy before telling anyone the link exists.**
          [AMENDED 2026-09-21] **Rob's own email MUST be on this list — and it is: entry 1.**
          It is easy to assume the account owner gets in automatically; he does not. Access
          evaluates this policy for everyone, Cloudflare account owner included. Leave Rob off
          and Rob is locked out of his own trip page, from the road, with the dashboard as the
          only fix. `rob.kellington@gmail.com` is also the address he will read a PIN on from
          a phone abroad, which is the property that actually matters at 2am in Mexico City.
          Prove it in the Verify step by logging in as Rob **first**.
          Adding or removing a trip-mate later is an edit to this policy — **that is also the
          revocation mechanism**: remove the address, and (if it matters urgently) revoke that
          user's live sessions at Zero Trust › My Team / Users › the user › Revoke. Removing an
          address alone does not kill an existing session; the session-duration note below is
          the other half of that story.
      Login methods: **One-time PIN only** · turn on **"Apply instant authentication"**
        One-time PIN only: no Google/GitHub/SAML provider is configured, so PIN is the only
        way in and there is no second path to audit. Instant auth on: with a single login
        method, it skips the "choose how to log in" screen — one less step for a trip-mate
        who is holding a phone in an airport.
    Save.
  **AFTER SAVING — the one deferred item from Session A, and this is the moment to check it.**
    Go to: Workers & Pages › worldcities › Settings › General, and look for
    **"Enable access policy"**.
    Background: per Rex (2026-09-18) that control creates an Access app on
    `*.worldcities.pages.dev`, covering every `<hash>` preview URL and branch alias. **Rob
    looked for it on 2026-09-21 (Gate 3b step 3) and it was NOT PRESENT in the dashboard** —
    not under that label, not anywhere obvious on that page. Alice's hypothesis, recorded then
    as EXPLICITLY UNVERIFIED, was that it may only appear once **Zero Trust is onboarded on the
    account** — which is what you have just done. **So this is the moment it would appear, and
    the only reason to look again.** Do not hunt for it at any other time.
    · **If it is there now:** turn it on. It is a **free extra layer on the `<hash>` preview
      hostnames** — belt and braces on top of Gate 3b's Bulk Redirect. It also restores option
      (b) in Gate 3b's rollback card, which currently has only option (a) available.
    · **If it still is not there:** **nothing changes and nothing is lost.** Gate 3b's Bulk
      Redirect already covers those hostnames, and that is not a theory — it was proven on
      2026-09-21 against the real leak path
      (`2ca4e8dc.worldcities.pages.dev/mexico-city-2026-6b9638/` → 301 →
      `https://worldcities.ca/<slug>/`, measured against a 200 baseline taken first). Record
      "still not present" and move on. **Do not improvise a substitute, and do not treat its
      absence as a blocker for Gate 5.** If it matters later it goes to Rex as a question, not
      to another dashboard hunt.
    Either way: **say which one you saw** in the paste-back. It settles a question that has
    been open since Session A.
Expect: the app is listed under Applications with path <slug>.
Verify (before any trip content is uploaded; every line must pass):
  for p in "<slug>" "<slug>/" "<slug>/index.html" "<slug>/zzz" "<SLUG-IN-UPPERCASE>/"; do
    curl -sI "https://worldcities.ca/$p" | grep -iE "^(HTTP|location)"; done
  -> each is a 302 whose location is <team>.cloudflareaccess.com, OR a 404 (the
     generated Not found page, no trip content). Never a 200.
  [AMENDED 2026-09-21] curl proves the path is protected; it cannot prove anyone can get
  IN. The allowlist itself is proved at Gate 5, in a private browser window, and **the
  first login attempted there must be Rob's own address** — if that PIN never arrives or
  the address is refused, stop before telling any trip-mate the link exists.
Trip-mate note (send with the link): the login page emails a PIN from
  noreply@notify.cloudflare.com (check spam). PINs expire after 10 minutes. The page
  always says "code emailed", even for addresses not on the list.
Rollback card: trigger = trip-mates can't log in, or the wrong path is protected ·
  action = edit the policy/app (for a login failure, **check the two allowlist entries
  character by character first** — a typo presents as "code emailed" and then silence).
  Do NOT delete the app while its trip page is uploaded (that makes it public); if the app
  must go, first rebuild without that trip and run Gate 5 (the slug disappears from the site),
  then delete the app · run by Rob · data-loss: none · limit: none · rehearsed: no.
  Billing: the Free plan is $0; the payment method stays on file until Rob removes it.
  **Note the ordering asymmetry, because it is the trap in this gate:** an Access app that is
  too *strict* is an inconvenience Rob fixes in the dashboard in a minute. An Access app that
  is missing, or attached to the wrong path, while a trip page is live is a **public page** —
  and nothing in Cloudflare tells you that happened. Gate 5's per-slug check is the only
  detector, which is why it runs on every upload.
Paste back: the five curl results (per trip), **both allowlist entries as they appear in the
  saved policy** (read back, not retyped from this file), the session-duration and
  seat-expiration values as saved, and **whether "Enable access policy" was present** in the
  Pages project settings after Zero Trust onboarding.
```

```
GATE 5: Upload the full site (trip pages included)   Plan ref: brief step 2 (second half)
Class: deploy
Preconditions (every line):
  - Gate 3b verify passed (pages.dev hostnames redirect to worldcities.ca). **PASSED
    2026-09-21.**
  - Gate 3 and Gate 4 verify passed — both still to run, both behind the 24-hour re-test.
  - Fresh local build of ALL live trips in one run, exit 0, e.g.
      uv run tripsite/build.py trips/mexico-city-2026.md [trips/<other-live-trip>.md ...]
  - The build's last lines "dist now holds N trip(s): ..." (or `ls dist`) list only
    slugs that are meant to be live, and EVERY one of them has its own Access app whose
    Gate 4 verify passed. A slug in dist/ without an Access app would go live unprotected.
  - **THE CURRENT `dist/` STATE, re-checked by Gage on 2026-09-21 (local, pasted):**
        find dist -type f | sort
        -> dist/404.html
           dist/_headers
           dist/index.html
           dist/mexico-city-2026-6b9638/index.html
           dist/robots.txt
    **Five files. Exactly one trip slug — `mexico-city-2026-6b9638` — and no `metro.json`.**
    All five timestamped 2026-09-21 12:07:25, and the built page is unambiguously an
    **`exact`-mode build**: the stay's name appears in the rendered HTML (2 occurrences), there
    is no "Where we're staying" label (the `approximate` marker text), and a Google Maps link
    is present. That is measured from the file, not inferred from the trip profile.
    Consequences for this gate:
      · **One slug means exactly ONE Access app is needed** before this upload — not two, and
        not zero. `mexico-city-2026-6b9638`.
      · **No other trip is at risk of going live by accident**, because this upload replaces
        the whole site with these five files and there is nothing else in `dist/`.
      · **No `metro.json`**, so the `metro.json` verify line below is N/A — see the amendment
        there. Its absence is correct for this trip, not a broken build.
      · If `hotel_display` changes, **this state is stale** and must be rebuilt (see the
        rebuild rule above). Re-run `find dist -type f | sort` after any rebuild and confirm
        the file list again — a rebuild that adds or drops a file changes what this upload
        publishes.
  - **HYGIENE: no `.DS_Store` (or anything else unexpected) in `dist/`.** `wrangler pages
    deploy` uploads the folder it is handed, file for file, so anything sitting in `dist/` gets
    published. This repo's root has a `.DS_Store` (macOS creates them on any folder a Finder
    window has visited), so this is a live possibility, not a theoretical one.
        find dist -type f | sort
      must return **exactly the five files listed above** and nothing else. A `.DS_Store`, an
      editor swapfile, or a stray export means **stop and clean `dist/` before uploading.**
      Read the whole list every time rather than trusting a count.
  - **OUTSTANDING DECISION — `hotel_display` for the live trip. STILL OPEN as of 2026-09-21.**
    This is a **Gate 5 precondition, not a build detail**: the value in `trips/<trip>.md`
    (`exact` | `approximate` | `hidden`) decides what the uploaded page reveals about where Rob
    is sleeping, and an upload is the moment it becomes other people's knowledge. See "Privacy
    behaviour (stays)" and the accepted limits M1/M2/L7 above for exactly what each value does
    and does not hide. **Do not run Gate 5 with this unresolved. Rob decides; Gage does not
    pick a default and neither does a recommendation.**
    **State of the decision, recorded so it is auditable:**
      · The file on disk says `hotel_display: exact` (line 23 of `trips/mexico-city-2026.md`,
        read 2026-09-21) — but that is **the current file value, not a decision.** It is what
        the last build happened to use.
      · Alice **recommended `exact`** to Rob on 2026-09-21, reasoning: a **two-person**
        allowlist behind email OTP, revocable by removing an address, makes the "the link
        travels beyond the allowlist" threat that `approximate` exists for largely moot, and
        an exact marker with address and Maps link is a materially more useful page on the
        ground. Gage's read: that reasoning is sound and the threat model it describes matches
        the Gate 4 allowlist actually being built (2 entries, not a domain rule).
      · **Rob has NOT decided.** Do not read the recommendation, or the file's current value,
        as the decision.
    **This card works whichever value he picks. What changes per value:**
      · **`exact`** → the page carries the stay's name, address, notes and a Google Maps link.
        **The current `dist/` already is this build** — see the build evidence below — so if
        Rob picks `exact`, **no rebuild is required** and the existing `dist/` is uploadable
        as-is. Worth knowing, because it is the one choice with no extra step.
      · **`approximate`** → 400 m circle, centre displaced 150–250 m, and id/name/address/
        notes/url/real-category stripped. **Requires an edit to `trips/mexico-city-2026.md`
        and a REBUILD.**
      · **`hidden`** → the stay is not on the page at all; events that pointed at it keep
        their text and lose the map link. **Also requires an edit and a REBUILD.**
    **THE REBUILD RULE — this is the part that is easy to get wrong.** If `hotel_display`
    changes, **the rebuild must POST-DATE the change to the trip file.** Uploading a `dist/`
    that predates the edit ships the old privacy mode while the file says otherwise, and
    nothing in the upload warns you. Check it mechanically rather than by memory:
        ls -lT trips/mexico-city-2026.md dist/mexico-city-2026-6b9638/index.html
      The `dist/` file's timestamp must be **later** than the trip file's. (Verified in the
      current state, 2026-09-21: trip file 11:51:15, built page 12:07:25 — the build
      post-dates the file, so today's `dist/` is consistent with today's `exact` setting.)
    And after any rebuild, **re-read the build's warnings before uploading** — under a
    non-`exact` value the build warns about leaks (the stay's name appearing in body text, a
    `popular` place within 100 m) and will hard-fail if its final safety-net scan finds the
    stay's name, street, postcode, url or coordinates in the rendered page. A warning is not a
    failure but it is the thing to read; the hard fail writes nothing at all.
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
  [AMENDED 2026-09-21] **For this trip that line is N/A — skip it.** Mexico City's metro
  geometry is ~21 KB, under the 400 KB threshold, so it is embedded in the page and no
  sibling file is produced. Verified locally 2026-09-21:
    find dist -type f | sort
    -> dist/404.html, dist/_headers, dist/index.html,
       dist/mexico-city-2026-6b9638/index.html, dist/robots.txt
  There is no dist/<slug>/metro.json, and **its absence is not a failure** — a 404 on that
  URL would be the correct answer for this trip, not a broken upload. Run the line only
  when a build actually prints the "wrote metro.json" message for that slug.
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
          [AMENDED 2026-09-21] "original" now means the POST-migration Gate 1 baseline:
          the three Zoho MX and nothing else at the apex. **Teardown removes a website. It
          never removes the zone, the nameserver delegation, or a mail record.** After any
          Gate 6 run: dig +short MX worldcities.ca @1.1.1.1 -> the three Zoho MX.
Rollback card: re-run Gates 2-5 (rebuild from trips/ or trips/archive/).
Paste back: verify results.
```

Which steps are CLI and which are dashboard:

| Gate | Where |
|---|---|
| 0a | CLI (`aws --profile rob route53 …`, read-only). **PASSED 2026-09-21** |
| 0b | nothing to run — TTL already 300. **PASSED 2026-09-21** |
| 0c | dashboard (add domain, fix records to exactly 3 MX, record both CF nameservers), plus `dig`. **PASSED 2026-09-21** |
| 0d | **registrar (Hover)**, plus Cloudflare dashboard and `dig`. **PASSED 2026-09-21, 19:10:10 local** |
| 0e | email client + `dig`; no dashboard. **CASE A: inbound to `rob@worldcities.ca`.** Baseline PASSED 2026-09-21; **post-flip run + 24 h re-test OUTSTANDING** |
| 0f | dashboard (DNS record + Bulk Redirect entry) |
| 0g | nothing to run — a waiting rule, and a card left deliberately unwritten |
| 1 | dashboard, plus `dig` |
| 2 | CLI (`npx wrangler pages deploy … --branch main`). **PASSED 2026-09-21** |
| 3 | dashboard |
| 3b | dashboard (account-level Bulk Redirects), once. **PASSED 2026-09-21** (step 3 deferred) |
| 4 | dashboard; billing the first time; one app per trip |
| 5 | CLI (`npx wrangler pages deploy dist … --branch main`) |
| 6 | dashboard (case A also runs Gate 5) |

---

## [AMENDED 2026-09-21] Running order across sessions

The old order (1 → 2 → 3 → 3b → 4 → 5) assumed a Cloudflare zone that doesn't exist yet.
Here is the order that holds now. The clock: **trip 2026-10-23 → 2026-10-30, 32 days
out.** Nothing below needs to happen tonight, and one step (0e) *must not* be rushed.

**Session A — COMPLETE 2026-09-21. All four gates PASSED.**

| Step | Result |
|---|---|
| **Gate 2** — create the Pages project, placeholder only | **PASSED.** `2ca4e8dc.worldcities.pages.dev`, production not preview, real 404s, `grep -c` → 2. |
| **Gate 3b** — Bulk Redirect `*.pages.dev` → `worldcities.ca` | **PASSED**, steps 1-2. 301s on bare, path+query, and `<hash>/<slug>/` — the leak vector, closed and proven against a 200 baseline. Step 3's "Enable access policy" control does not exist in the dashboard today; deferred to after Gate 4. |
| **Gate 0a** — Route 53 export | **PASSED.** `Z0944732VRZ4NUBNE0FL`, 5 record sets, `no-more-pages`, two checksummed copies. `--profile rob` required. No TXT of any kind. |
| **Gate 0b** — read the MX TTL gauge | **PASSED**, no action: TTL already 300. |

Session A also turned up an out-of-scope find: a second, **orphaned** Route 53 hosted zone
for `skyideas.com` (`Z08901851VA0TTXNMTFCZ`), superseded by Cloudflare and costing ~$0.50/mo
for nothing. Not touched, not in scope; see the warning block in the Deploy preamble, which
exists because both zones will be on screen during Session B.

**Session B — the migration. THE CUTOVER IS DONE. Two items left, both in 0e.**

| Step | Note |
|---|---|
| **pre-flight** — the nine-item checklist | **SPENT — 9 of 9 confirmed 2026-09-21 before the flip.** Items 8 and 9 answered by Rob: he rarely receives mail at this domain and is fine for 72 h. Not a to-do list any more; kept as the record and as the template for the next domain. |
| **Gate 0c** — add the zone to Cloudflare, diff against the 0a export | **DONE — PASSED 2026-09-21.** Zone PENDING; records exactly SOA + NS ×2 + MX ×3; nameservers `bella` / `gabriel.ns.cloudflare.com` recorded; pre-flip dig green from both. The card's count grep was wrong (false 4 and 1 from the export's comment lines) and is corrected — the zone was right all along. |
| **Gate 0e (baseline)** — the INBOUND mail test BEFORE the flip | **DONE — PASSED 2026-09-21.** Gmail → `rob@worldcities.ca`, sub-second, **2 `Received:` hops, receiving host `mx.zohomail.com`, no relay in between**; raw `.eml` on file. It travelled Route 53's MX, which is the "before" picture. A2's pass criterion was **corrected** first: it had demanded a literal `mx*.zoho.com` and would have failed this healthy delivery — post-flip that false FAIL would have triggered the 0d rollback. Read 0e's DEFECT note. |
| **Gate 0d** — change nameservers at Hover | **DONE — PASSED 2026-09-21, flip confirmed at the `.ca` registry 19:10:10 local.** Two nameserver entries at Hover, read back character by character, nothing else. Mail survived on four independent resolvers and a 2-minute poller never alerted. Apex now empty (designed). Route 53 zone untouched, so the rollback stays intact until 0g. |
| **Gate 0e (post-flip)** — the real mail gate | **OUTSTANDING — not sent yet. Nothing else runs until this passes.** Inbound to `rob@worldcities.ca`, headers read, labelled "post-flip". |
| **Gate 0e (24 h re-test)** — the second pass | **OUTSTANDING — earliest 2026-09-22 19:10 local** (24 h after the recorded flip time). Required. Gate 1 does not wait for it; Gates 3, 0f, 4, 5 do — see the SEQUENCING RULING in 0e. |

**Session C — after the post-flip 0e, and (for Gate 3 onward) after the 24-hour re-test**

**The sequencing, since this is the question that decides the whole session** (full reasoning
in 0e's SEQUENCING RULING; the measured basis is FINDING 1 and FINDING 3 above):

```
post-flip 0e  ──►  Gate 1  ──┐
   (hard block           (read-only,
    on everything)        may run now)
                              ├──►  24-hour re-test  ──►  Gate 3  ──►  Gate 4  ──►  Gate 5
                              │     (earliest             (apex      (Access,     (trip page
                              │      2026-09-22            CNAME)     billing)     goes live)
                              │      19:10 local)
                              └──►  Gate 0f (www) — any time after Gate 3; optional
```

| Step | Blocked on | Note |
|---|---|---|
| **Gate 0e (post-flip)** | nothing — **run it now** | The only thing standing between here and the rest of the project. DNS evidence is already strong; a delivered message is what this gate is for. |
| **Gate 1** — confirm Active, export the zone | post-flip 0e | Read-only. Two dashboard steps: read the status word, take the export. **Do not re-verify the delegation/MX/apex — already measured, see the post-flip readings table.** The export is Gate 3's mail-safety baseline and Gate 3 cannot run without it. |
| **Gate 0e (24 h re-test)** | the clock | Earliest 2026-09-22 19:10 local. |
| **Gate 3** — attach `worldcities.ca` to the Pages project | 24 h re-test + Gate 1 | Verify is now ordered V1→V4 and **must** be run in order: authoritative dig first, resolver check second, content curls third, MX diff fourth. A curl failure while your resolver still holds the S3 IPs is **not** a rollback trigger. |
| **Gate 4** — Zero Trust + one Access app | Gate 3 · **Rob's billing OK** | Allowlist is filled in: **two addresses**, `rob.kellington@gmail.com` + `Lucie's Gmail (project/secrets/access-allowlist.txt)`, one per entry. 2 of 50 seats. Billing OK **not yet given** — the gate does not start without it. Also: re-check "Enable access policy" right after onboarding. |
| **Gate 0f** — decide and implement `www` | Gate 3 | Recommendation: redirect to apex. Optional; skipping it costs only UX. `www` is currently NXDOMAIN at Cloudflare. |
| **Gate 5** — upload the real site | Gate 4 · **Rob's `hotel_display` decision** | The step that makes a trip page reachable by other people. One slug in `dist/`, so exactly one Access app must be passing. |

**SESSION C PRE-FLIGHT — confirm these before Gate 5 in particular.** Same spirit as Session
B's nine: every line is a yes/no with evidence beside it, and it exists because **Gate 5 is
the step that makes a trip page reachable by other people.** One "no" means Gate 5 waits.

| # | Confirm | How you know | If no |
|---|---|---|---|
| 1 | **Post-flip 0e PASSED** | A2's three criteria on a message labelled "post-flip": arrived <5 min, a Zoho-operated receiving host, no hop between sender and Zoho | Stop. Nothing in Session C runs. This is the 0d rollback trigger. |
| 2 | **The 24-hour re-test PASSED** | Step 1 + A2 re-run **after 2026-09-22 19:10 local** | Wait for the clock. Gate 1 may still run; Gates 3/0f/4/5 may not. |
| 3 | **Your resolver has switched off Route 53** | `dig +short A worldcities.ca @1.1.1.1` no longer returns eight S3 IPs | Wait. Running Gate 3's verify now produces a **false failure** whose documented reaction is a rollback (FINDING 3). |
| 4 | **Zone status is "Active"** | Gate 1, read off the dashboard | Gate 4 needs an active zone in the account. Click "Check nameservers now"; if still pending after ~30 min with the registry showing Cloudflare, stop and paste both. |
| 5 | **Gate 1's export is on disk, second copy + checksums done** | `cf-zone-<date>.txt` in `project/secrets/` and `~/Backups/worldcities-dns/` | Gate 3's MX diff has no baseline. Take the export first. |
| 6 | **Gate 3 V4 passed — the three MX did not move** | `diff mx-before mx-after` empty **and** both files exactly 3 lines | STOP and roll back Gate 3. This is the one Gate 3 failure that is never a caching artifact. |
| 7 | **`hotel_display` is DECIDED by Rob, in his own words** | Not the file's current value, not Alice's recommendation | **Do not upload.** This is the setting that decides what strangers-by-accident learn about where Rob sleeps. |
| 8 | **`dist/` was rebuilt AFTER any `hotel_display` change** | `ls -lT trips/mexico-city-2026.md dist/mexico-city-2026-6b9638/index.html` — the built page is **newer** | Rebuild. Otherwise you publish the old privacy mode while the file claims the new one, silently. |
| 9 | **`dist/` holds exactly the intended files and nothing else** | `find dist -type f \| sort` → the five known files; **no `.DS_Store`**, no swapfiles, no stray exports | Clean `dist/` first. Whatever is in the folder gets published. |
| 10 | **Every slug in `dist/` has a passing Gate 4** | One slug today (`mexico-city-2026-6b9638`) → exactly one Access app, its five-URL curl verify passing | **A slug in `dist/` without an Access app goes live unprotected.** This is the single highest-consequence line in this table. |
| 11 | **Rob's own address is on the allowlist, and proven by a real login** | `rob.kellington@gmail.com` is entry 1, and Rob logged in in a private window **first** | Fix before telling any trip-mate the link exists — otherwise Rob is locked out of his own page from the road. |
| 12 | **The `<hash>/<slug>/` redirect still holds for the NEW deployment** | Gate 3b's probe re-run with **this upload's** new `<hash>` | A new deployment gets a new hostname. Re-run it after **every** Gate 5, not once. |
| 13 | **Billing OK given by Rob, in session** | His explicit yes to a payment method on file at $0 | Gate 4 does not start. Hand back to Alice. |

**No longer blocked:** Gates 1, 3, 0f, 4, 5 and 6 were all blocked on Gate 0. Gate 0's
cutover is done — **0d PASSED 2026-09-21** — so the blocker is now narrower and specific: the
**post-flip 0e** for everything, plus the **24-hour re-test** for Gate 3 onward. Gate 4 was
always the load-bearing one: a self-hosted Access application needs an **active zone in the
account** and `*.pages.dev` is not one (Rex, 2026-09-21). The zone now exists and is
delegated; Gate 1 confirms Cloudflare agrees it is Active. **Until Gate 4 passes for a slug,
no trip content for that slug goes up.**

**Hard stops:**
- No DNS work between **2026-10-23 and 2026-10-30** (the trip). If the migration hasn't
  settled by ~2026-10-16, stop and re-plan rather than cutting over close to departure.
- The Route 53 hosted zone is **not deleted** until Gate 0g's five conditions are all
  true — realistically November.
