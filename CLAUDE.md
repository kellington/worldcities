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

**As of 2026-09-21 the trip-site half is under active work — a live deploy in progress.**
Start by reading, in this order:

1. **`STATE.md`** — where things actually are. If it's stale, everything downstream is wrong.
2. **`TASKS.md`** — what's next. **Now** is the blocking item.
3. **`tripsite/README.md`, Deploy section** — the authoritative gate cards for the deploy.
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
- **No trip page goes up before its Access app exists** (Gate 4 before Gate 5).
- **Zone in scope is `Z0944732VRZ4NUBNE0FL`.** Never touch `Z08901851VA0TTXNMTFCZ`
  (orphaned `skyideas.com` zone, different domain).
- **`worldcities.ca` carries live email** at `rob@worldcities.ca`. Mail is what DNS work
  protects; the website in the blast radius is a placeholder being dropped on purpose.
- **A gate's pass criterion that is a literal string match is suspect.** Running the gates
  found five defects, two of which would have produced a false verdict whose documented
  reaction was a rollback. See DECISIONS.md, 2026-09-21.

## Notes

- Personal use only
- No standardization with other SKYideas/Rob projects required
- Commits are infrequent
- The repo is **public**: `trips/` and `project/secrets/` are gitignored and must stay so
