# State

*Last updated: 2026-09-22 16:30 MDT*

## Summary

**The Mexico City trip is live** at `https://worldcities.ca/mexico-city-2026-6b9638/`, behind
Cloudflare Access (email PIN, allowlist Rob + Lucie). Rob has logged in and the page renders
with map tiles. Every other hostname — `worldcities.pages.dev`, both deployment hashes —
301s to `worldcities.ca`, where Access applies. The root serves the neutral placeholder.
Mail on `rob@worldcities.ca` is untouched by any of it (MX diff clean).

Gates 3, 4 and 5 ran **ahead of** the Gate 0e 24-hour mail re-test, on Rob's call — the
measured reason for the block was gone (see DECISIONS.md, 2026-09-22). The re-test itself
**is still owed**: earliest 2026-09-22 19:10 MDT. It is now a confirmation, not a blocker.

## What's working

- **Live trip page** — Gate 5 deploy `b36c4fc1`, wrangler 4.136.3, `--branch main`.
  `dist/` = exactly 5 files, fresh build 2026-09-22 16:11 (exit 0), post-dates the trip file
  (2026-09-21 11:51) → **`hotel_display: exact`**, Rob's decision this session.
  Verified: apex `/<slug>/` → 302 to `worldcities-trips.cloudflareaccess.com`;
  `worldcities.pages.dev/<slug>/`, `b36c4fc1.…/<slug>/`, `2ca4e8dc.…/<slug>/` → 301 to
  `worldcities.ca/<slug>/`; root lists no slug; `x-robots-tag: noindex, nofollow`;
  unauthenticated follow of the trip URL returns no trip content. **Rob's private-window
  login passed** (Chrome, `rob.kellington@gmail.com`).
- **Gate 4 — Access app** `trip mexico-city-2026-6b9638`, destination
  `worldcities.ca/mexico-city-2026-6b9638`, policy `trip-mates` (Allow; two separate email
  entries `rob.kellington@gmail.com`, `Lucie's Gmail (project/secrets/access-allowlist.txt)`, read back from the
  saved policy JSON), login method required = One-time PIN, session `730h`. All five verify
  paths (incl. uppercase) → 302 to the Access login.
- **Gate 3 — custom domain.** Apex = proxied CNAME `worldcities.ca → worldcities.pages.dev`
  (the only zone change). Authoritative `bella` returns Cloudflare A `104.21.94.173`,
  `172.67.138.210`. Curls: 200, "World Cities" ×2, "Amazon S3" 0, `AmazonS3` header 0.
  MX before/after diff empty, 3 and 3 lines; three Zoho MX from `1.1.1.1` and `8.8.8.8`.
  Export: `project/secrets/cf-zone-2026-09-22.txt`.
- **Resolvers** — as of 15:45, `1.1.1.1`, `8.8.8.8`, `9.9.9.9`, OpenDNS and Rob's ISP
  resolver all on the Cloudflare delegation. The split-resolver window is closed.
- **Public example** — fictional London demo, `examples/london-demo.md` built to
  `examples/site/` (never deploy that folder — it would replace the live site). README now
  covers trip sites; its dist/-writing command is labelled as replacing dist/. 165 tests.
- **Earlier and unchanged:** Gates 0a–0d, 1, 2, 3b; Zero Trust team `worldcities-trips`;
  DNS backups in `~/Backups/worldcities-dns/`; `tripsite/` tests (165 as of the London demo work).

## In progress

- **Gate 0e 24-hour re-test** — earliest **2026-09-22 19:10 MDT**. Gmail →
  `rob@worldcities.ca`, save "Show original" `.eml` to a *new* filename, then:
  `grep -ic '^Received:'` → 2 · a Zoho host (`mx*.zoho.com` or `mx*.zohomail.com`) · no hop
  between Gmail and Zoho. Low risk (Route 53 still serves identical MX), but required.
- **Lucie's link** — message drafted by Pearl (two-text version), copied by Rob. **Not yet
  confirmed sent, and Lucie has not yet logged in.** Her login is the only proof her
  allowlist entry has no typo.

## Known issues

- **Defect 6 (Gate 4 accepted a 404 pre-upload)** — fixed in the new generic deploy guide
  (302-only before upload) and in CLAUDE.md's rules.
- **`www.worldcities.ca` is dark** until the `www` decision. Must never CNAME to the Pages project —
  Access covers `worldcities.ca` only.
- **"Enable access policy" is still absent** from Pages › Settings after Zero Trust
  onboarding. Hypothesis ruled out; Gate 3b's redirect covers those hostnames regardless.
- **No SPF/DKIM/DMARC on `worldcities.ca`** — pre-existing, out of scope.
- **Orphaned Route 53 zone `skyideas.com`** (`Z08901851VA0TTXNMTFCZ`) — do not touch while
  working in Route 53.
- **Untested on real phone hardware** — map drag vs page scroll, small ↗ link targets.
  Now more pressing: the page is live and will be used on phones in Mexico City.

## Environment / setup

```
branch: vscode  (--branch main is REQUIRED on every wrangler pages deploy)
aws:    every route53 command needs --profile rob
wrangler: unpinned via npx; 4.136.3 today. Git-dirty warning is harmless
live deploy: b36c4fc1   (previous: 2ca4e8dc, placeholder only)
Access app:  trip mexico-city-2026-6b9638  · team worldcities-trips
zone in scope:  Z0944732VRZ4NUBNE0FL  (worldcities.ca)
NEVER touch:    Z08901851VA0TTXNMTFCZ  (skyideas.com, orphan)
```

Deploy docs: `tripsite/README.md` › "Deploy to Cloudflare Pages with Access" (generic);
worldcities-specific rules in CLAUDE.md. The cutover gate cards were removed 2026-09-22
(git history, commit `5a14908`); the Session B/C working-copy runbook artifact is retired.

## Open questions

- **PLAN.md is stale on docs** — lines 25 and 44 reference the removed gate cards
  (0a–0g, 1–6, Gate 6). Fix in the milestone-close rewrite.
- **PLAN.md milestone ("First live trip site") is effectively met** — remaining: the 0e
  re-test and Lucie's first login. Close the milestone and rewrite PLAN.md once both pass.
- **Can a self-hosted Access app take a `*.pages.dev` hostname?** Deferred until after
  Gate 5 — which has now passed, so it is revisitable. Low priority; 3b covers it.
- **When to delete the Route 53 hosted zone** (Gate 0g) — not before ~2026-10-05 (two weeks
  of stable mail on Cloudflare). It is the rollback.

## Resolved this session

- `hotel_display` → **`exact`** (Rob, 2026-09-22).
- Whether the 24-hour re-test must block Gates 3–5 — no, once every resolver measurably
  switched (DECISIONS.md, 2026-09-22).
- Whether "Enable access policy" appears after Zero Trust onboarding — it does not.

---

*Updated at the end of every session by `/end-session`. This is the file the agent reads
first next session — if it's stale, everything downstream is wrong.*
