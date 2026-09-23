# Tasks

**Now** is 1–2 items. **Next** is what the agent proposes at the start of a session.
**Later** is a holding pen, not a backlog.

## Now

- [ ] **Send Lucie the link and confirm she logs in.** Pearl's two-text draft is in Rob's
      clipboard / diary. Her successful login is the only proof her allowlist entry is right.

## Next

- [ ] **Test the live page on a real iPhone** — map drag vs page scroll, the small ↗ link
      targets. Never done on hardware, and the page will be used on phones in Mexico City.
- [ ] **Decide `www`** (was Gate 0f). Recommendation: redirect to apex. Never CNAME it to the
      Pages project.
- [ ] **Close the milestone** once Lucie's login passes — rewrite PLAN.md.

## Later

- [ ] Renderer: italic/bold/links spanning a line break and wrapped bullet lines don't render
      (`tripsite/build.py:1200` formats per line). Documented as a limit in
      `tripsite/README.md`; fix + tests would remove it (Gage). Found 2026-09-22.
- [ ] `--out Dist` (case variant) writes the real `dist/` on macOS but skips the Access
      warning — compare by inode, not path (`tripsite/build.py:2344`). Low.
- [ ] Keep `examples/site/` in sync with `build.py` — no test catches drift. Rebuild with
      `uv run tripsite/build.py examples/london-demo.md --out examples/site` after renderer changes.
- [ ] Revisit Access on `*.pages.dev` as a second lock — Gate 5 has passed, so this is now open.
- [ ] Gate 0g — delete the Route 53 hosted zone `Z0944732VRZ4NUBNE0FL`, not before
      ~2026-10-05 (two weeks of stable mail on Cloudflare). It is the rollback. Its old card
      (zone-ID checks) is at `git show 5a14908:tripsite/README.md`, lines 1614–1649.
- [ ] Clean up the orphaned `skyideas.com` Route 53 zone (`Z08901851VA0TTXNMTFCZ`, ~$0.50/mo).
      Separate job, separate domain.
- [ ] Second trip live alongside the first — the upload replaces the whole site, so every
      live trip must be rebuilt in one run and each needs its own Access app first.
- [ ] Poster as a trip-page banner — the poster engine is still there and unused.
- [ ] Narrow the bypass-mode instruction that tells agents to edit files via `sed`/heredocs.
      Gage declined it twice: routing writes through Bash bypasses his guard hook's
      protected-file check, which would matter on a job where the target *was* a protocol file.
- [ ] Renew `worldcities.ca` — registry expiry **2026-12-02**.
- [ ] Consider SPF/DKIM/DMARC on `worldcities.ca` if Rob ever sends from that address.

## Done (recent)

- [x] **Gate 0e 24-hour re-test PASS** — 19:28 MDT, 2 hops Gmail → Zoho, Quincy-verified (2026-09-22)
- [x] `tripsite/README.md` rewritten generic (2,503 → 489 lines); cutover gate cards removed,
      302-only Access verify built into the new guide (2026-09-22)
- [x] Public London demo (`examples/london-demo.md` → `examples/site/`) + README covers trip
      sites; build's closing message names its real output dir (165 tests) (2026-09-22)

- [x] **Mexico City trip live** at `worldcities.ca/mexico-city-2026-6b9638/` (2026-09-22)
- [x] Gate 5 — deploy `b36c4fc1`, all hostnames verified, Rob's login passed
- [x] Gate 4 — Access app + `trip-mates` policy, five paths → 302
- [x] Gate 3 — custom domain attached, MX diff clean
- [x] `hotel_display` decided: `exact`
- [x] "Enable access policy" re-checked after Zero Trust — still absent

- [x] tripsite v0 built, verified, 164 tests (2026-09-21, earlier session)
- [x] Renamed maptoposter → worldcities
- [x] Gate 2 — Pages project, placeholder only, real 404
- [x] Gate 3b — `*.pages.dev` locked down, hash hostnames included
- [x] Gate 0a — authoritative Route 53 export, backed up twice, checksummed
- [x] Gate 0b — MX TTL already 300; the real constraint is the `.ca` delegation TTL of 86400
- [x] Gate 0c — Cloudflare zone created, exactly 3 MX, pre-flip dig green from both NS
- [x] Gate 0e baseline — inbound mail proven pre-flip
- [x] **Gate 0d — the cutover.** Registry flipped 2026-09-21 19:10:10 MDT
- [x] Gate 0e post-flip — inbound mail proven 56 min after the flip
- [x] Gate 1 — zone Active, baseline export taken and backed up
- [x] Zero Trust onboarded, team `worldcities-trips`, One-time PIN added

---

**Bigger than a session?** The generic deploy guide is `tripsite/README.md` › "Deploy to
Cloudflare Pages with Access"; worldcities-specific rules are in CLAUDE.md.
