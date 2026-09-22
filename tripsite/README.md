# tripsite

Turns a trip profile (a Markdown file with YAML frontmatter) into a static, shareable trip
page: a Leaflet/OpenStreetMap map of your places plus toggleable popular places, a
day-by-day schedule, and an "About this trip" section.

CLI only. The output folder (`dist/` by default) *is* the export. No server, no UI.

A complete public example lives in [`examples/london-demo.md`](../examples/london-demo.md),
built into [`examples/site/`](../examples/site/).

## Usage

```bash
uv run tripsite/build.py trips/my-trip.md                  # build one trip into dist/
uv run tripsite/build.py trips/a.md trips/b.md             # build several in one run
uv run tripsite/build.py trips/my-trip.md --dry-run        # validate only
uv run tripsite/build.py trips/my-trip.md --out /tmp/site  # build somewhere other than dist/
uv run tripsite/build.py trips/my-trip.md --refresh-transit  # re-fetch airport/metro
```

The build is offline apart from one step: a trip that asks for an `airport:` or a
`map: {metro: ...}` layer fetches that data from Overpass **once** and caches it under
`cache/tripsite/`. Every later build reads the cache and makes no request at all.

Writes:

| File | What |
|---|---|
| `dist/<slug>/index.html` | one trip page per trip file (single file, trip data embedded as JSON) |
| `dist/<slug>/metro.json` | **only** when a trip's metro geometry is too big to embed (>400 KB of JSON); the page then loads it on demand |
| `dist/index.html` | neutral "World Cities" placeholder (no trip listing, so slugs don't leak) |
| `dist/404.html` | neutral "Not found" page (noindex, no slugs). Without a top-level `404.html`, Cloudflare Pages treats the site as a single-page app and serves `index.html` with status 200 for every missing path; with it, a missing path gets a real 404 |
| `dist/robots.txt` | `Disallow: /` |
| `dist/_headers` | Cloudflare Pages headers: `X-Robots-Tag: noindex, nofollow` on every path |

**The output folder holds exactly the trips passed on this run.** A Cloudflare Pages
direct upload is a full-site snapshot: whatever is in `dist/` becomes the whole
site, and anything missing from it is taken down. So:

- **Rebuild every live trip in the same run**, e.g.
  `uv run tripsite/build.py trips/lisbon-2027.md trips/kyoto-2027.md`.
  (`trips/*.md` works too, but only if `trips/` holds live trips alone. Move
  finished trips to `trips/archive/` or they'll be published again.)
- Any `<slug>/` folder that isn't in this run is **removed**, and the build
  prints the slugs left in the output folder. `--dry-run` shows what would be removed.
- The build only removes things it wrote itself. Every page it writes carries
  `<meta name="generator" content="tripsite">`, and a stale trip folder is removed
  only if it holds nothing but an `index.html` with that marker in its `<head>`
  (plus an optional `metro.json` and `.DS_Store`). The marker in the page body or
  inside an HTML comment doesn't count. A folder without the marker or without an
  `index.html`, any symlink, or any other file stops the build: it is listed and
  nothing is deleted or written. Symlinks are never followed, written through or
  deleted. Every output is written to a temp file and then renamed into place, so a
  hardlinked output is replaced, never written through.
- Use `--out` for anything you don't mean to publish, so `dist/` never picks it up.

`dist/`, `trips/` and `cache/` are gitignored: trip profiles hold private details and the
repo can be public.

Preview (opening the file via `file://` may not load OSM tiles, because it sends no Referer):

```bash
python -m http.server -d dist
# open http://localhost:8000/<slug>/
```

`http.server` doesn't reproduce Cloudflare Pages' 404 handling (it never serves
`404.html` for a missing path), so it can't check the 404 behaviour. Check that on
Pages after the first deploy (see Deploy below).

Invalid profiles fail with every problem listed (missing fields, bad dates,
end before start, unknown place ids, bad or unquoted times, unknown theme,
out-of-range coordinates, duplicate YAML keys, `NO`/`yes`/`on` read as
true/false, a malformed or unresolvable IATA code). Events outside `start..end`
are dropped with a warning. If any trip in a run fails, nothing is written.

Tests: `uv run python -m unittest discover -s tripsite -p 'test_*.py' -v`
(the 7 "expected failure" results are the known limits below, not open bugs)

## Trip profile format

Markdown with YAML frontmatter. The body below the frontmatter becomes "About this trip".
The body supports basic Markdown only: headings, paragraphs, lists, `code`,
**bold**, *italic*, and http(s) links. Wrapped paragraph lines are joined, but
bold, italic, `code` and links can't span a line break, and each list item must be
on one line (a wrapped continuation ends the list).

```yaml
---
trip:
  name: London 2027
  slug: london-2027-xxxx           # lowercase/digits/hyphens; add a random suffix of
                                   # your own. The slug is part of the page's URL, so
                                   # don't reuse or share one you don't want guessed
  start: 2027-04-10                # YYYY-MM-DD
  end: 2027-04-16
  timezone: Europe/London          # IANA name
  city: London
  country: United Kingdom          # quote yes/no-like words: "NO" (Norway)
  center: {lat: 51.507, lon: -0.115}
  zoom: 12                         # 1..19
  theme: midnight_blue             # any themes/<name>.json (page colours only)
  airport: LHR                     # optional; IATA code, looked up once and cached
privacy:
  hotel_display: approximate       # exact | approximate | hidden
  noindex: true                    # pages are always noindex regardless
map:                               # optional reference layers
  metro: off                       # on | off. Absent = no metro layer at all
locations:                         # our places, always on the map
  - {id: hotel, name: ..., category: stay, address: ..., lat: .., lon: .., notes: .., url: https://..}
  - {id: friends, name: ..., category: visit, private: true, address: ..., lat: .., lon: ..}
popular:                           # toggleable pins (checkbox per place + per category)
  - {id: british-museum, name: British Museum, category: museum, lat: .., lon: .., default_on: true, url: .., notes: ..}
events:
  - date: 2027-04-12
    time: "11:00"                  # optional; QUOTE it. A bare number like 930 is rejected
    kind: city                     # plan (ours) | city (happening in town)
    name: Changing of the Guard
    location: buckingham-palace    # a place id, or {lat, lon, label}; optional
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
warning naming it, and the warning says how to keep it.

With `keep: true` it is kept instead and rendered in its own section, **"Just outside
your dates"**, below the day-by-day list:

- sorted by date, each row showing its own date and weekday ("Sun 18 Apr"), plus the
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
"Open the British Museum website in a new tab".

A stay's `url` is **never published** unless `hotel_display: exact` — see below.

### Airport (`trip.airport`)

Optional. A trip's airport is a **reference point, never a place**: it is not in
`locations` or `popular`, it can never be a stay, it takes no part in the privacy
rules or the leak scan, and it does not change the initial view (still
`trip.center`/`trip.zoom`).

```yaml
trip:
  airport: LHR                                              # short form: just the code
  airport: {code: LHR, name: London Heathrow}               # override the name only
  airport: {code: LCY, name: London City, lat: 51.505, lon: 0.055}   # no lookup at all
  airport: [LHR, {code: LCY, name: London City, lat: .., lon: ..}]   # a trip using two
```

- The code is upper-cased for you (`lhr` works) and must be exactly three letters.
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
on the page with the lines hidden until asked for, which keeps the trip pins the focus.
Switching between them is a one-word edit; nothing is re-fetched.

- Fetched from Overpass as subway **route relations** (`type=route` + `route=subway`)
  inside a square about 60 km across centred on `trip.center`, with member geometry
  inline (`out geom`).
- The two running directions of a line share the same `ref`, so they are merged into one
  entry, and their shared way geometry is de-duplicated. Platform and stop members are
  ignored — this is track, not furniture.
- Each line is drawn in its **official OSM `colour` tag**; a line without a usable hex
  colour falls back to a readable palette colour. Lines sort by number, then letter.
- Geometry is simplified with Douglas-Peucker at a 15 m tolerance (endpoints always kept)
  and rounded to 5 decimals. For the London example that is 11 lines and 6,640 points,
  ~134 KB of JSON.
- **One "Metro lines" checkbox** turns the whole network on or off, with a compact
  colour-chip legend of the line numbers beside it (each chip's tooltip is the full line
  name). The lines are drawn in their own map pane *below* the pins and are
  non-interactive, so they never cover a marker or swallow a click. They are deliberately
  **excluded from "Show all places on map"** — a 60 km network would zoom the trip away.
- **Stations are not drawn.** They would need a second query and several hundred more
  points for something the base OSM tiles already label.
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

**Page weight.** The metro geometry is embedded in the page while it stays under 400 KB
of JSON. Above that the build writes it to `<slug>/metro.json` instead and the page
fetches it the first time the layer is switched on; the build prints which route it took,
and `metro.json` must then be uploaded with the page. The London example, with the
Underground embedded, is about 180 KB.

### Privacy behaviour (stays)

A place is a **stay** if its `category` is one of `stay`, `hotel`, `lodging`,
`airbnb`, `accommodation` or `hostel` (any case), **or** if it has `private: true`.
Stays belong under `locations`. A stay under `popular` fails the build with
"put stays under locations".

| `hotel_display` | On the page |
|---|---|
| `exact` | normal marker with name, address, notes, Google Maps link |
| `approximate` | a 400 m circle whose **centre is moved 150–250 m** from the stay, in a direction derived from a hash of the slug, id, name and exact coordinates. The stay is always inside the circle but never near its centre. Focusing it never zooms past 14. **id, name, address, notes, url and the real category are removed** from the page. It is labelled "Where we’re staying" for a stay category, or "Private place" for anything else marked `private: true` (e.g. `friends` above), and numbered if there are several of one kind ("Where we’re staying 1", "… 2"). |
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

#### Known limits

These are by design for pages that sit behind a login (see Deploy). The tests for
them in `test_qa_round2.py` are marked as expected failures.

- **M1, the circle is an oracle.** Its position is a fixed function of the slug
  and the stay's id, name and coordinates exactly as typed. Someone who guesses
  all of those (e.g. id `hotel`, the hotel's name, coordinates copied from Google
  Maps) can recompute the circle from the public code and confirm the guess.
  Changing the slug, or the stay's name or coordinates, moves the circle, and
  anyone who saw both versions can overlap them to narrow the stay to about a
  60 m radius.
- **M2, the leak scan can be dodged.** It matches text literally, so it misses
  the stay's name when it's split by formatting (`**Grand** Hotel`), written
  without accents or with decomposed accents, or has doubled spaces. It also
  misses the street when the address has no commas or starts with a building
  name. It is a backstop: keep the stay's details out of the body, events and
  other places yourself.
- **L7, 3-decimal coordinates pass the leak scan.** The scan only flags the
  stay's coordinates at 4 or more decimals. The stay's coordinates rounded to 3
  decimals (about 100 m) deliberately pass, so a nearby pin or a body mention at
  3 decimals is not caught.
- **Metro layer vs. the leak scan.** The coordinate check flags any number starting
  with the stay's latitude at 4 dp when a number starting with its longitude at 4 dp
  sits within 80 characters. Metro geometry is hundreds of 5-dp lat/lon pairs, so a
  **non-`exact`** stay within roughly 15 m of a drawn metro line can make the build
  fail with "private stay coordinates appear on the page". It's a false positive, but
  it fails safe. If it happens, set `map.metro` off for that trip.

Every page carries `noindex,nofollow` (meta tag and `X-Robots-Tag` header) and
`referrer: strict-origin-when-cross-origin`, so OSM and unpkg see only the
origin (`https://<your-domain>`), never the slug path.

Map markers use a fixed palette that stays visible on OSM tiles in every theme:
our places red, popular places blue, event spots teal (one marker, reused), the
approximate stay area a purple circle with a dashed dark outline, and the airport
an amber disc with a white plane (a different *shape*, not just a different
colour, so it reads as "not one of our pins"). Metro lines are the exception:
they keep their own official OSM colours. The theme only colours
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

## Deploy to Cloudflare Pages with Access

Without a login in front of it, a trip page is guarded only by its slug. This serves each
trip at `https://<your-domain>/<slug>/` behind Cloudflare Access (email one-time PIN).
`<your-domain>` must be an **active zone** in your Cloudflare account: Access can't protect
`*.pages.dev`. Placeholders: `<your-domain>`, `<project>` (Pages project), `<team>` (Zero
Trust team), `<slug>`, `<hash>` (a deployment's preview hostname), `<production-branch>`.

### The placeholder-only deploy

Publishes the neutral root and 404 pages and **no trip**. It's used for the first deploy,
to take the last trip down, and as the first response to a leak. (The build needs at least
one trip, so the four site files are copied from the committed example instead.)

```bash
PH="$(mktemp -d)"     # run from the repo root
cp examples/site/index.html examples/site/404.html examples/site/robots.txt examples/site/_headers "$PH"/
ls -A "$PH"    # exactly: 404.html  _headers  index.html  robots.txt
npx wrangler pages deploy "$PH" --project-name <project> --branch <production-branch>
```

### One-time setup (in this order, before any trip is uploaded)

1. **Pages project.**
   `npx wrangler pages project create <project> --production-branch <production-branch>`,
   then the placeholder-only deploy. Check that
   `curl -sI https://<project>.pages.dev/no-such-page/ | head -1` gives a 404. A 200 means
   `404.html` is missing and Pages is serving `index.html` for every path.
2. **Custom domain.** Workers & Pages › `<project>` › Custom domains › Set up a domain ›
   `<your-domain>`. This adds a proxied apex CNAME to `<project>.pages.dev`. Check that
   `curl -sI https://<your-domain>/ | head -1` gives a 200 before any content check. If the
   domain carries mail, export the zone before and after and compare the MX records:

   ```bash
   grep -v '^;' zone-before.txt | grep -iE '[[:space:]]MX[[:space:]]' | sort > mx-before.txt
   grep -v '^;' zone-after.txt  | grep -iE '[[:space:]]MX[[:space:]]' | sort > mx-after.txt
   diff mx-before.txt mx-after.txt; wc -l < mx-before.txt; wc -l < mx-after.txt
   ```

   There must be no diff output, and both counts must equal your number of MX records.
   `grep -v '^;'` drops the export's comment lines, which would otherwise inflate the count.
3. **Lock down `*.<project>.pages.dev`.** Access covers `<your-domain>` only, so without this
   `<project>.pages.dev/<slug>/` and every `<hash>.<project>.pages.dev/<slug>/` would serve
   the trip with no login. Every deployment keeps its own `<hash>` hostname and its files.
   - Bulk Redirects › Create Bulk Redirect List. Source URL `<project>.pages.dev`, target
     `https://<your-domain>`, status 301. Tick Preserve query string, Subpath matching,
     Preserve path suffix and Include subdomains.
   - Create a Bulk Redirect Rule that uses the list, and deploy it.
   - Verify: `curl -sI https://<hash>.<project>.pages.dev/<slug>/` gives a 301 to
     `https://<your-domain>/<slug>/`.
   - Never remove this redirect while any deployment still holds a trip page.
4. **Zero Trust.** Onboard on the Free plan. It asks for a payment method even at $0. A seat
   is per user, not per login. Then Integrations › Identity providers › add **One-time PIN**.
   Your login host is `<team>.cloudflareaccess.com`.

### Per trip: the Access app comes first

Before a trip's page is ever uploaded: Access controls › Applications › Create new
application › Self-hosted.

- **Public hostname:** domain `<your-domain>`, path `<slug>`. Just the slug, with no
  slashes and no wildcard. A plain path covers `/<slug>`, `/<slug>/` and everything under
  it; `<slug>/*` would miss `/<slug>`.
- **Session duration:** longer than the trip (e.g. 1 month), so nobody has to log in again
  mid-trip on a bad connection. The trade-off is that a lost, unlocked device keeps access
  that long. To cut someone off, remove their address **and** revoke their sessions.
- **Policy:** Allow, Include › Emails, **one entry per address**. Put your own address on
  it; the account owner is not let in automatically. Read the saved entries back. A typo
  doesn't error, because the login page says "code emailed" to every address.
- **Login methods:** One-time PIN only. Turn on instant authentication.

Verify before uploading:

```bash
for p in "<slug>" "<slug>/" "<slug>/index.html" "<slug>/zzz" "<SLUG-IN-UPPERCASE>/"; do
  curl -sI "https://<your-domain>/$p" | grep -iE "^(HTTP|location)"; done
```

Every line must be a **302 to `<team>.cloudflareaccess.com`**; a 200 never passes. **A 404
proves nothing**: before the upload the slug 404s whether or not Access is attached. Still
404 after a minute or two? Reopen the app, save it again, and re-run.

Tell trip-mates: the PIN comes from `noreply@notify.cloudflare.com` (check spam) and
expires in 10 minutes. The page says "code emailed" even for addresses not on the list.

### Publish

```bash
uv run tripsite/build.py trips/<every-live-trip>.md ...   # ALL live trips, one run
find dist -type f | sort       # exactly the site files + one folder per intended slug
npx wrangler pages deploy dist --project-name <project> --branch <production-branch>
```

- Every slug in `dist/` must already have a passing Access app. A slug without one goes live
  unprotected. Look out for stray files too (`.DS_Store`): whatever is in `dist/` gets
  published.
- Decide `hotel_display` **before** publishing, and rebuild after changing it.
- `--branch`: wrangler otherwise uses your current git branch, and if that isn't the
  production branch the upload becomes a *preview* deployment. `<your-domain>` then keeps
  serving the old site.
- Verify:
  - `curl -sI https://<your-domain>/<slug>/` still gives the 302 to Access. If the build
    wrote a `metro.json`, check that `/<slug>/metro.json` gives the same 302.
  - `curl -sI https://<project>.pages.dev/<slug>/` and the new `<hash>` hostname give a 301
    to `<your-domain>`.
  - `curl -sI https://<your-domain>/ | head -1` gives a 200 **first** (an empty response
    greps as 0 too), then `curl -s https://<your-domain>/ | grep -c <slug>` gives 0.
  - `curl -sI https://<your-domain>/ | grep -i x-robots-tag` gives `noindex, nofollow`.
- Then log in yourself in a private window, before telling anyone the link exists.

### Take a trip down

- **Other trips are still live:** move its profile out of the live set, rebuild the
  remaining trips in one run, and deploy. In a private window, logging in to `/<slug>/`
  should now show "Not found". **Only then** delete its Access app; deleting the app first
  makes the page public. Afterwards `/<slug>/` gives a 404.
- **It's the last trip:** run the placeholder-only deploy, check the same way, then delete
  the Access app.
- Keep the Bulk Redirect: old deployments still hold the trip at their `<hash>` URLs.
- **To remove everything**, in order: delete the Pages project (every deployment goes with
  it; confirm it's gone), the apex CNAME, each Access app, and the Bulk Redirect **last**.

### If a trip is reachable without a login

1. Run the placeholder-only deploy immediately.
2. List the deployments, then delete every one that holds a trip page, except the current
   production deployment:

   ```bash
   npx wrangler pages deployment list --project-name <project>
   npx wrangler pages deployment delete <deployment-id> --project-name <project>
   ```

   An aliased deployment is refused without `--force`: read the refusal first, and never force the production one.
3. Verify: each remaining `<hash>.<project>.pages.dev/<slug>/` gives a 301 to `<your-domain>`,
   and, logged out, `curl -s https://<your-domain>/<slug>/ | grep -c trip-data` gives 0.
4. Find the cause (missing Access app, wrong path, redirect off) before redeploying trips.

### Gotchas

- Every upload replaces the whole site. A live trip missing from the run is taken down.
- Don't point `www` at the Pages project unless Access covers it too. Redirect it to the
  apex instead.
- Never deploy the `examples/site/` folder itself. It holds the demo trip and would replace
  the live site.
