# Plan

*Last rewritten: 2026-09-21*

## Current milestone

**First live trip site** — Mexico City 2026 served at `https://worldcities.ca/<slug>/`,
private to Rob and Lucie behind Cloudflare Access email one-time PIN, with the domain
migrated off AWS and live email intact.

### Definition of done

- [x] Pages project `worldcities` exists, serving the neutral placeholder only (Gate 2)
- [x] Every `*.pages.dev` hostname 301s to `worldcities.ca`, hash previews included (Gate 3b)
- [x] `worldcities.ca` migrated from Route 53 to Cloudflare, zone Active (Gates 0a–0d, 1)
- [x] Zoho mail proven working after the cutover (Gate 0e post-flip)
- [ ] Zoho mail proven again ≥24 h after the cutover (Gate 0e re-test) — **earliest 2026-09-22 19:10 MDT**
- [ ] `worldcities.ca` attached to the Pages project, apex CNAME proxied (Gate 3)
- [ ] Access app on the trip path, One-time PIN, both emails allowlisted (Gate 4)
- [ ] Trip uploaded and unreachable without login on every hostname (Gate 5)
- [ ] Lucie opens the link on her own device and gets in

### In scope

- The six deploy gate families in `tripsite/README.md` (0a–0g, 1–6)
- One trip: `mexico-city-2026-6b9638`
- The `hotel_display` decision for the live page

### Out of scope for this milestone

- A second live trip (the upload model replaces the whole site — needs its own thinking)
- Poster integration (the poster engine is unused by tripsite)
- iPhone touch testing — real, but it doesn't block going live
- SPF/DKIM/DMARC on `worldcities.ca` (absent today; pre-existing gap, not caused here)
- Access on `*.pages.dev` as a second lock (Gate 3b's redirect already covers it)

## Roadmap

1. **Verify on a real phone** — map drag vs page scroll, and the small ↗ link targets.
   Never tested on hardware; Quincy couldn't cover touch.
2. **Two trips live at once** — every live trip must be rebuilt in one run before any
   upload, and each needs its own Access app before its page goes up.
3. **Poster as a trip banner** — the poster engine already exists and tripsite ignores it.
4. **Maybe:** teardown rehearsal (Gate 6), and deleting the Route 53 hosted zone once mail
   has been stable on Cloudflare for a couple of weeks (Gate 0g).

## Open risks

- **The 24-hour split-resolver window.** Measured, not theoretical: at 19:40 on 2026-09-21,
  `1.1.1.1` and `9.9.9.9` still returned the old S3 A records from the cached AWS
  delegation while `8.8.8.8` had switched. Gate 3 run from a stale resolver would *fail its
  own verify and trigger a rollback of a correct change*. This is why Gates 3–5 wait.
- **Gate cards are written, mostly unrun.** Five real defects were found in them today by
  running them (see DECISIONS.md). Assume the unrun ones carry more.
- **Hover and Zero Trust UI labels are unverified** — Gage has never seen either dashboard.
  Session A already proved a label from research can simply not exist.
- **Mail is the only irreversible-feeling thing here.** The website in the blast radius is a
  2020 placeholder being dropped on purpose.
- **Trip freeze:** if the deploy isn't finished by ~2026-10-16, stop and re-plan rather than
  working close to departure.

---

*Overwrite this file at milestone boundaries. Git keeps the history. If a decision caused
the rewrite, log it in DECISIONS.md.*
