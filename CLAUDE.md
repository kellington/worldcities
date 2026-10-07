# CLAUDE.md — worldcities

This file tells Claude Code how to operate in this repo.

## What this repo is

worldcities = map posters + trip sites.

- **Posters:** a clone of originalankur/maptoposter, customized for personal use. Run occasionally to generate a custom map poster. Still supported.
- **Trip sites:** `tripsite/` builds a static, shareable website for a trip (map, places, events) from a trip profile in gitignored `trips/`. Hosted on Cloudflare Pages at worldcities.ca.

No productization plans.

## How to use it

See README.md for usage instructions. This is a Python-based tool — run it locally when needed.

## Working in this repo

**As of 2026-09-22 the first trip (Mexico City) is live on worldcities.ca.**
Start by reading, in this order:

1. **`STATE.md`** — where things actually are. If it's stale, everything downstream is wrong.
2. **`TASKS.md`** — what's next. **Now** is the blocking item.
3. **`tripsite/README.md` › "Deploy to Cloudflare Pages with Access"** — the generic deploy
   guide (placeholders). worldcities-specific values live only in the rules below. The
   historical AWS→Cloudflare cutover gate cards were removed 2026-09-22; they're in git
   history (last present at commit `5a14908`).
   Rob runs every dashboard, `wrangler` and DNS step himself; verify each one before moving on.
4. `PLAN.md` / `PROJECT.md` / `DECISIONS.md` for milestone, scope and why things are as they are.

Protocol files (PROJECT/PLAN/STATE/TASKS/DECISIONS) are **Alice's to write** — team members
read them and report findings; they never edit them.

The poster half still has no active development. For poster work: check README.md, make the
minimal change, no ceremony needed.

### Deploy-specific rules that bite

- **`--branch main` is required on every `wrangler pages deploy`** — the repo sits on branch
  `vscode`, and without the flag wrangler makes a *preview* deploy.
- **Every `aws route53` command needs `--profile rob`**, or it returns `InvalidClientTokenId`.
- **Every Pages upload replaces the whole site.** Rebuild all live trips in one run first.
- **No trip page goes up before its Access app exists**, and the app is only proven by a
  **302** to `worldcities-trips.cloudflareaccess.com` — before upload a 404 proves nothing.
- **Zone in scope is `Z0944732VRZ4NUBNE0FL`.** Never touch `Z08901851VA0TTXNMTFCZ`
  (orphaned `skyideas.com` zone, different domain).
- **`worldcities.ca` carries live email** at `rob@worldcities.ca`. Any DNS change: diff the
  three Zoho MX before/after.
- **The zone has a second tenant: `https://retired-world.worldcities.ca`** — a Cloudflare
  Workers custom domain owned by the `Rob/retired-world` repo (live 2026-10-07 UTC). It's outside
  the worldcities Access app (which covers `worldcities.ca/<slug>` paths only) and outside the
  Pages project. Never delete, overwrite or wildcard over its record; after any DNS change,
  check `curl -sI https://retired-world.worldcities.ca/` still returns 200.
- **Never deploy `examples/site/`** — it's a full site of its own and would replace the live one.
- **Trip-mate emails never go in tracked files** (public repo) — allowlist is in
  `project/secrets/access-allowlist.txt`.
- **A gate's pass criterion that is a literal string match is suspect.** Running the gates
  found six defects, several of which would have produced a false verdict. See DECISIONS.md,
  2026-09-21 and 2026-09-22.

## Notes

- Personal use only
- No standardization with other SKYideas/Rob projects required
- Commits are infrequent
- The repo is **public**: `trips/` and `project/secrets/` are gitignored and must stay so

## Project status

Config for the global `/project-status` skill (`~/.claude/skills/project-status/`).
Metadata (group, profile, priority) comes from the workspace README table.

```yaml
extra_sources:
  - README.md
  - AGENTS.md
palette: { primary: "#1e293b", accent: "#0d9488" }
custom_sections: |
  - Two tools: poster CLI (fork of originalankur/maptoposter) and tripsite/ static trip sites (worldcities.ca); report each.
  - Poster quick reference + theme list from `ls themes/`; generated output = `ls posters/` count only.
  - Automation vision (AGENTS.md) vs what exists (`ls scripts/`) as two columns.
```

## Project Reference

**Posters** (full usage in README.md; themes: `ls themes/` or `--list-themes`):

```bash
uv run ./create_map_poster.py --city "Edmonton" --country "Canada"                     # default theme
uv run ./create_map_poster.py --city "Paris" --country "France" --theme noir --distance 10000
uv run ./create_map_poster.py --city "Tokyo" --country "Japan" --all-themes            # every theme
uv run ./create_map_poster.py --list-themes
uv run ./create_map_poster.py --city "Venice" --country "Italy" --theme blueprint -W 8.3 -H 11.7   # A4
uv run ./create_map_poster.py --city "Stanley Park" --country "Canada" -lat 49.3043 -long -123.1443 --theme forest
uv run ./create_map_poster.py --city "Tokyo" --country "Japan" --display-city "東京" --display-country "日本" --font-family "Noto Sans JP" --theme japanese_ink
```

Distance guide (default 18000m): 4000–6000m small/dense cities (Venice, Amsterdam) ·
8000–12000m medium cities / downtown (Paris, Barcelona) · 15000–20000m large metros (Tokyo, Mumbai).

Poster gotchas:
- Requires internet — Nominatim (geocoding) and OSMnx (roads) are hit every run; no offline mode.
- Large `--distance` is slow; use 150 DPI for quick previews.
- Ambiguous places may geocode wrong — override with `-lat` / `-long`.
- Nominatim rate limits — add delays when looping `--all-themes` over many cities.
- `posters/` is gitignored — regenerate when needed.

**Trip sites:** `tripsite/README.md` (build + "Deploy to Cloudflare Pages with Access");
worldcities-specific deploy rules are in "Deploy-specific rules that bite" above.
