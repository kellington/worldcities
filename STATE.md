# State

*Last updated: 2026-09-21 20:30 MDT*

## Summary

`worldcities.ca` has been migrated off AWS Route 53 onto Cloudflare and the zone is
**Active**. Zoho mail survived the cutover and has been verified once after it. The Pages
project is live serving only a neutral placeholder; every `*.pages.dev` hostname 301s to
`worldcities.ca`. **Nine gates have passed. One thing blocks the rest: a mail re-test that
cannot run before 2026-09-22 19:10 MDT**, 24 hours after the nameserver flip. After it,
Gates 3 → 4 → 5 put the Mexico City trip live for Rob and Lucie.

Nothing is half-applied. If work stopped here permanently, the only oddity is that
`worldcities.ca` resolves to nothing — the old S3 placeholder is gone by design.

## What's working

- **`tripsite/` v0** — `uv run tripsite/build.py trips/mexico-city-2026.md` exits 0.
  164 tests pass (7 expected failures = accepted limits, documented in `tripsite/README.md`).
- **Gate 2** — Pages project `worldcities`, production deploy, placeholder only.
  `grep -c "World Cities"` → 2 · `robots.txt: Disallow: /` · `x-robots-tag: noindex, nofollow`
  · `/no-such-page/` → real 404, not SPA mode. Deployment hash `2ca4e8dc`.
- **Gate 3b** — Bulk Redirect list `worldcities_pages_dev` (1 of 5 account lists). Verified:
  bare, `/any/path?x=1` with path *and* query preserved, the hash hostname, and the real leak
  vector `2ca4e8dc.worldcities.pages.dev/<slug>/` → 301 to `worldcities.ca/<slug>/`.
- **Gates 0a–0d, 1 — the migration.** Registry flipped 2026-09-21 19:10:10 MDT to
  `bella`/`gabriel.ns.cloudflare.com`. Cloudflare answers authoritatively. Zone Active.
  Zone holds exactly SOA + NS×2 + MX×3 — nothing else.
- **Mail.** Three Zoho MX unchanged across `1.1.1.1`, `8.8.8.8`, `9.9.9.9`, OpenDNS.
  Post-flip inbound test passed 56 min after the flip: 2 Received hops, accepted by
  `mx.zohomail.com`, sub-second.
- **Zero Trust** — onboarded, Free (2 of 50 seats), team **`worldcities-trips`**, One-time PIN
  added as the only identity provider, inactive-user removal at 3 months.
- **Backups** — `~/Backups/worldcities-dns/` holds the Route 53 original, the 0c import and
  the Gate 1 baseline, checksummed against `project/secrets/`.

## In progress

- **Gate 0e 24-hour re-test — the only blocker.** Earliest **2026-09-22 19:10 MDT**.
  Send Gmail → `rob@worldcities.ca`, save the `.eml` to a *new* filename, then check:
  `grep -ic '^Received:'` → 2 · a Zoho host (`mx*.zoho.com` **or** `mx*.zohomail.com`) ·
  no hop between Gmail and Zoho. Why it matters: last night's pass could have been served
  by a resolver still holding the AWS delegation; tomorrow's can only have gone via
  Cloudflare.
- **Then Gate 3** → attach the custom domain. **Gate 4** → Access app, path
  `mexico-city-2026-6b9638`, One-time PIN, session 1 month, allowlist
  `rob.kellington@gmail.com` + `lucie.beauchamp2020@gmail.com`. **Gate 5** → upload `dist/`.
- **Undecided and blocking Gate 5: `hotel_display`.** `trips/mexico-city-2026.md:23` says
  `exact`, and `dist/` is provably an exact-mode build — so **`exact` ships with no rebuild**.
  Either other value needs an edit plus a rebuild that post-dates it.

## Known issues

- **The split-resolver window is live.** At 19:40 on 2026-09-21, `1.1.1.1` and `9.9.9.9`
  still returned the old eight S3 A records; `8.8.8.8` and OpenDNS had switched. Expect
  disagreement for up to 24 h. **Do not run Gate 3's verify from a stale resolver** — it
  would report the old S3 page as a failure and the documented reaction is rolling back a
  correct change.
- **`worldcities.ca` resolves to nothing** (apex is NODATA — the name exists and carries MX).
  Correct until Gate 3. Don't read it as breakage.
- **Gate cards carry defects; running them is how they surface.** Five found today, all
  listed in DECISIONS.md. The remaining unrun gates should be assumed to carry more.
- **`www.worldcities.ca` is dark** and will stay so until Gate 0f. Must never CNAME to the
  Pages project — Gate 4's Access app covers `worldcities.ca` only, so `www/<slug>/` would
  serve the trip with no login.
- **No SPF/DKIM/DMARC on `worldcities.ca`** — pre-existing, out of scope, but real if Rob
  ever sends from that address rather than just receiving.
- **Orphaned Route 53 hosted zone for `skyideas.com`** (`Z08901851VA0TTXNMTFCZ`, 7 records) —
  Cloudflare is authoritative for that domain, so the zone does nothing but cost ~$0.50/mo.
  Out of scope; **do not touch it while working in the Route 53 console.**
- **Untested on real phone hardware** — map drag vs page scroll, small ↗ link targets.

## Environment / setup

Stable commands live in README.md and `tripsite/README.md`. Session-specific only:

```
branch: vscode  (main and vscode both at c919018; --branch main is REQUIRED on every
                 wrangler deploy or it makes a preview deploy from "vscode")
aws:    every route53 command needs --profile rob, else InvalidClientTokenId
zsh:    interactive_comments is off — pasted "#" lines error harmlessly.
        `setopt interactive_comments` per session, or paste command lines only
wrangler: unpinned via npx; 4.136.1 today. Expect the git-dirty warning, it's harmless
zone in scope:  Z0944732VRZ4NUBNE0FL  (worldcities.ca)
NEVER touch:    Z08901851VA0TTXNMTFCZ  (skyideas.com, orphan)
```

**Working-copy runbooks** (Alice's pages, derived from `tripsite/README.md`, which stays
authoritative — if they disagree, follow the README):

- Session A (done): https://claude.ai/artifact/G5WgzsnmSece74pRfhH7rn
- Session B/C: https://claude.ai/artifact/Cs5TrB4frM2o6FSjh7Zvy2

## Open questions

- **`hotel_display` for the live page.** Alice recommends `exact`: two people behind email
  OTP, revocable by removing an address, and an exact marker with address and Maps link is a
  materially more useful page on the ground. Rob hasn't decided.
- **Does "Enable access policy" exist now?** It was absent from the Pages project settings in
  Session A. Hypothesis was that it needs Zero Trust onboarded — Zero Trust now exists, so
  the check is cheap. Either answer is fine; Gate 3b already covers those hostnames.
- **Can a self-hosted Access app take a `*.pages.dev` hostname?** External advice says yes;
  Rex's research says a self-hosted app needs an active zone in the account. Unresolved, and
  deliberately declined for now — revisit only after Gate 5 passes.
- **When to delete the Route 53 hosted zone** (Gate 0g). Not before mail has been stable on
  Cloudflare for a couple of weeks. It is the rollback.

## Resolved this session

- Whether the trip site needs Cloudflare at all — yes, for login; S3 can serve static files
  but cannot authenticate, and would be http-only without CloudFront.
- Whether Rob is near a paid Cloudflare tier — no, 1–3 orders of magnitude inside every
  Free limit; nearest is Zero Trust seats at 2 of 50.
- Whether the Zoho mailbox is live — yes, `rob@worldcities.ca`, with a human behind it.
- Whether Bulk Redirects is a Free feature — yes, 5 lists / 15 rules / 10,000 redirects,
  account-wide, and the account had 0 of 5 used.
- What actually governs the cutover — the parent `.ca` delegation TTL of 86400, measured at a
  `.ca` TLD server. Not the MX TTL (already 300) and not the in-zone NS TTL.

---

*Updated at the end of every session by `/end-session`. This is the file the agent reads
first next session — if it's stale, everything downstream is wrong.*
