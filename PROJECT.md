# worldcities

> Two CLI tools in one repo: a map-poster generator, and `tripsite/`, which builds a
> private static trip website from a trip profile.

## Why this exists

The posters came first — a personal fork of
[originalankur/maptoposter](https://github.com/originalankur/maptoposter), run occasionally
to produce a print-quality city map.

`tripsite/` is the newer and now the active half. Planning a trip with other people means
scattering a hotel address, a list of places, and a day-by-day schedule across group chats
where nobody can find any of it again. A single link that shows *our* places on a map, the
popular places we might add, and what's happening on each day of the trip solves that — and
it should be shareable with the people on the trip without being visible to the internet.

## Who it's for

- **Primary user:** Rob — runs the CLI, owns the trip profile, publishes the site.
- **Secondary users:** the people on the trip. They only ever see a URL and a login prompt.
  For Mexico City 2026 that is Rob and Lucie Beauchamp.

## Success criteria

- [x] A trip profile in `trips/` builds to a self-contained static site with one command
- [x] The build refuses to leak a private stay's name, street, postcode or precise coords
      when `hotel_display` is not `exact` (enforced by a leak scan that fails the build)
- [ ] The Mexico City 2026 site is live at `https://worldcities.ca/<slug>/`
- [ ] A trip-mate can open it with an emailed code — no account, no password
- [ ] The site is not reachable without logging in, on *any* hostname it is served from
- [ ] Nothing in the repo or the public internet reveals a trip slug

## Non-goals

- **Not a product.** No users beyond the people on a given trip, no signup, no billing.
- **No server, no runtime.** The output is static files. Trip data is embedded at build
  time; the only network calls a visitor's browser makes are for map tiles.
- **No CMS or admin UI.** The trip profile is a Markdown file edited by hand.
- **Not a poster/tripsite merge.** They share a repo and nothing else.
- **No standardisation with other SKYideas/Rob projects.**

## Constraints

- **Personal use, free tier.** Cloudflare Free throughout — Pages, one Bulk Redirect,
  Zero Trust Free (50 seats, 2 in use). Zero Trust required a $0 billing activation with a
  card on file; that is Cloudflare's documented behaviour, not a paid plan.
- **The repo is public.** So `trips/` and `project/secrets/` are gitignored, and the trip
  slug carries a random suffix because an earlier slug leaked into public commits.
- **Privacy is a build-time guarantee, not a convention.** The leak scan is the mechanism.
- **`worldcities.ca` carries live email** — a Zoho mailbox at `rob@worldcities.ca`. Any DNS
  work on that zone treats mail as the thing being protected.
- **Every Pages upload replaces the whole site.** All live trips must be rebuilt in one run
  before any deploy.
- **Trip dates are a hard freeze window.** No DNS or deploy work between 2026-10-23 and
  2026-10-30.

---

*This file changes rarely. If you find yourself editing it often, something is wrong —
either the scope is actually shifting (record that in DECISIONS.md) or you're putting the
wrong content here.*
