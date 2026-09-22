# Tasks

**Now** is 1–2 items. **Next** is what the agent proposes at the start of a session.
**Later** is a holding pen, not a backlog.

## Now

- [ ] **Gate 0e 24-hour mail re-test** — earliest **2026-09-22 19:10 MDT**. Gmail →
      `rob@worldcities.ca`, save the `.eml` under a new filename, then:
      `grep -ic '^Received:'` → 2 · a Zoho host · no hop between Gmail and Zoho.
      **Nothing else runs until this passes.**
- [ ] **Decide `hotel_display`** — `exact` ships with no rebuild (`dist/` is already an
      exact-mode build); `approximate` or `hidden` needs an edit plus a rebuild after it.

## Next

Ordered. Cards in `tripsite/README.md`; do not improvise around them.

- [ ] **Gate 3** — attach `worldcities.ca` to the Pages project. Run its verify from a
      resolver that has switched (`8.8.8.8` had, `1.1.1.1` and `9.9.9.9` had not). Check the
      three Zoho MX are untouched in the zone diff against `project/secrets/cf-zone-2026-09-21.txt`.
- [ ] **Gate 4** — Access app. Path `mexico-city-2026-6b9638`, no leading/trailing slash, no
      wildcard. One-time PIN only, instant auth on, session 1 month. Allowlist
      `rob.kellington@gmail.com` and `lucie.beauchamp2020@gmail.com`. Verify: five curls,
      each a 302 to `worldcities-trips.cloudflareaccess.com` or a 404 — **never a 200**.
- [ ] **Gate 5** — rebuild all live trips in one run, `find dist -type f | sort` (expect 5
      files, no `.DS_Store`), then `npx wrangler pages deploy dist --project-name worldcities
      --branch main`. Then the private-browser login test.
- [ ] **Send Lucie the link** with the login note: the PIN comes from
      `noreply@notify.cloudflare.com`, often lands in spam, expires in 10 minutes, and the
      page says "code emailed" even for addresses that aren't on the list.
- [ ] **Gate 0f** — decide `www`. Recommendation: redirect to apex. Never CNAME it to the
      Pages project.

## Later

- [ ] Test the live page on a real iPhone — map drag vs page scroll, the small ↗ link
      targets. Never done on hardware.
- [ ] Check whether "Enable access policy" appeared in the Pages project settings now that
      Zero Trust exists.
- [ ] Revisit Access on `*.pages.dev` as a second lock — only after Gate 5 passes.
- [ ] Gate 0g — delete the Route 53 hosted zone `Z0944732VRZ4NUBNE0FL`, but not before mail
      has been stable on Cloudflare for a couple of weeks. It is the rollback.
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

**Bigger than a session?** The deploy already has its long-form document —
`tripsite/README.md`'s gate cards. Don't duplicate them here; link to a gate by name.
