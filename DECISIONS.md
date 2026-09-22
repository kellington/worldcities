# Decisions

Append-only log of meaningful decisions. Never edit past entries — if a decision is
reversed, add a new entry that references the old one.

## How to write an entry

```
## [YYYY-MM-DD] — Short title

**Decision:** What we decided, in one sentence.
**Why:** The reasoning that drove it.
**Trade-off:** What we're giving up.
**Impact:** What changes because of this (code, scope, process).
```

Keep entries short. If you need more than ~8 lines, you're probably writing a design doc,
which belongs elsewhere.

---

## [2026-09-21] — Cloudflare, not S3, because the trip page needs a login

**Decision:** Serve trip sites from Cloudflare Pages behind Cloudflare Access, rather than
from the existing AWS S3 bucket.
**Why:** The build output is pure static and S3 serves it fine — but S3 cannot authenticate
anyone. Real access control on AWS means CloudFront plus Cognito or Lambda@Edge, which stops
this being a static project. S3 would also have been http-only on a custom domain.
**Trade-off:** A Cloudflare dependency, and a nameserver migration to earn it.
**Impact:** Made the domain migration a prerequisite rather than a preference — a
self-hosted Access application requires an active zone in the account, and `*.pages.dev` is
not one.

## [2026-09-21] — Migrate worldcities.ca to Cloudflare and drop the S3 site

**Decision:** Move `worldcities.ca` from AWS Route 53 to Cloudflare nameservers; do not
recreate the apex or `www` S3 alias records.
**Why:** Access needs the zone on Cloudflare. Cloudflare's CNAME-only "partial" setup is
Business-plan and above, so a full nameserver move was the only route on Free. The S3 site
was a 204-byte placeholder from 2020 with nothing behind it.
**Trade-off:** `worldcities.ca` resolves to nothing between the flip and Gate 3, and `www`
stays dark until Gate 0f. A rollback takes up to 24 hours.
**Impact:** Added the Gate 0 family (0a–0g) to the deploy. Route 53 hosted zone
`Z0944732VRZ4NUBNE0FL` is retained as the rollback and must not be deleted yet.

## [2026-09-21] — Protect mail by serving identical MX from both providers, not by TTL

**Decision:** Put the three Zoho MX into Cloudflare and verify them from Cloudflare's own
nameservers *before* the flip, and leave Route 53 serving the same three throughout.
**Why:** The rollback instrument was assumed to be the MX TTL (300). It isn't — the binding
constraint is the parent `.ca` delegation TTL, measured at a `.ca` TLD server as **86400**,
set by CIRA and not lowerable from Route 53, Cloudflare or Hover. So a rollback is a
24-hour instrument in both directions, and no TTL makes it faster.
**Trade-off:** A pre-flip verification step and a longer Session B.
**Impact:** During the split window it does not matter which nameserver a resolver asks —
both answer the same three MX, and neither DNS provider ever holds a message. Mail came
through the cutover unchanged on four resolvers. This is the project's real safety
mechanism; the rollback card is the backup.

## [2026-09-21] — Trip-mates log in with an emailed code, never a password

**Decision:** Cloudflare Access with One-time PIN as the only identity provider. Session
duration 1 month.
**Why:** No account, no password, nothing for Rob to administer — access is a list of email
addresses, and removing one revokes it. 1 month rather than 1 week because the trip runs 8
days (Oct 23–30) and a week-long session would force a re-auth *mid-trip*, by email,
possibly on a dead SIM in Mexico City.
**Trade-off:** A longer cookie life if a device is lost. Acceptable for a page showing a
hotel and a list of restaurants.
**Impact:** Gate 4 allowlists `rob.kellington@gmail.com` and
`lucie.beauchamp2020@gmail.com`. Rob's own address must stay on it or he locks himself out.

## [2026-09-21] — Accept Zero Trust Free's $0 billing activation

**Decision:** Complete Zero Trust onboarding, including the $0 checkout with a card on file.
Team name `worldcities-trips`.
**Why:** Required to create a self-hosted Access application. Free tier is 50 seats and this
project uses 2; seats are per user, not per login or per app.
**Trade-off:** A live billing relationship. Cloudflare's own checkout states "additional
usage beyond included allowance billed monthly" — so exceeding 50 seats **bills** rather
than blocks, contradicting third-party claims that user 51 is simply refused.
**Impact:** `worldcities-trips.cloudflareaccess.com` is the login hostname trip-mates see,
and the string Gate 4's verify curls must 302 to. Inactive-user removal left at 3 months;
it only governs seat reuse and 2 of 50 is not near the ceiling.

## [2026-09-21] — Gates 3–5 wait for the 24-hour mail re-test, Gate 1 does not

**Decision:** After the cutover, run only the post-flip mail test and Gate 1; hold Gates 3,
0f, 4 and 5 until the 24-hour re-test passes. (Alice initially had Gates 3–5 unblocked by
the post-flip test alone; Gage overruled it with measurements and Alice adopted his order.)
**Why:** The split-resolver window is real and was measured — at 19:40, `1.1.1.1` and
`9.9.9.9` still returned the old S3 records while `8.8.8.8` had switched. Gate 3's verify
run from a stale resolver reports the old S3 page, which are two *documented failures* whose
documented reaction is removing the custom domain and deleting the apex CNAME: a DNS cache
tearing down a correct change. Gate 1 is exempt — read-only, no rollback card, evidence that
doesn't decay.
**Trade-off:** One evening, against 32 days of slack before the trip.
**Impact:** Session C runs after 2026-09-22 19:10 MDT. Order: 0e re-test → 3 → 4 → 5.

## [2026-09-21] — Decline a second Access lock on *.pages.dev for now

**Decision:** Do not add an Access application on `worldcities.pages.dev`, despite external
advice suggesting it.
**Why:** Gate 3b's Bulk Redirect already 301s every pages.dev hostname — bare, hash previews
and branch aliases — to `worldcities.ca`, verified including the real leak vector
`<hash>.worldcities.pages.dev/<slug>/`. The advice also contradicts Rex's finding that a
self-hosted app needs an active zone in the account, and neither claim has been tested.
Adding it now would introduce an untested interaction between two edge features and
invalidate a passing Gate 3b verification on the eve of the gates that matter.
**Trade-off:** One layer of defence in depth, deferred.
**Impact:** Revisit after Gate 5 passes, when a surprise costs nothing.

## [2026-09-21] — Gate cards are amended from what running them reveals, not from reasoning

**Decision:** Treat `tripsite/README.md`'s gate cards as the authoritative runbook, and
correct them from observed output; Alice's published runbook pages are working copies that
follow the cards, never the reverse.
**Why:** Running the gates exposed five defects that no amount of re-reading would have
found: (1) `grep -c "World Cities"` expected 1 where the placeholder has 2; (2) `--profile
rob` missing from every `aws` command; (3) BIND-export greps counting the file's own comment
text, reporting 4 and 1 on a correct zone; (4) the mail gate demanding a literal
`mx.zoho.com` when the real receiving MTA is `mx.zohomail.com`; (5) Gate 3's "old site gone"
check passing on a *dead* site, because an empty body scores 0 on every content grep.
**Trade-off:** The cards churn, and the working-copy pages go stale and need republishing.
**Impact:** Defects 3 and 4 were the expensive ones — both would have produced a false
verdict at a moment whose documented reaction was a rollback. Pass criteria are now written
as "say what you're looking for, give the observed value as an example, prefer a structural
test over a string match," and the remaining unrun gates are assumed to carry more of these.

## [2026-09-22] — Run Gates 3–5 ahead of the 24-hour mail re-test

**Decision:** Rob overrode the sequencing ruling that held Gates 3, 4 and 5 behind the
Gate 0e 24-hour re-test, and ran them from ~15:50 MDT — about 3h20m before the re-test
window opened.
**Why:** The ruling's measured reason was stale resolvers making Gate 3's verify fetch the
old S3 page and trigger a false rollback. At 15:45, `1.1.1.1`, `8.8.8.8`, `9.9.9.9`, OpenDNS
and Rob's ISP resolver all returned the Cloudflare delegation and no S3 IPs — the reason was
gone. Mail risk was near zero: the Route 53 zone still serves identical MX, and Gates 3–5
touch no MX (Gate 3's MX diff proved it).
**Trade-off:** An unseen resolver could still have been stale — worst case a few hours of
the site not resolving for someone. No leak path: Gate 4's Access app was in place before
Gate 5 uploaded the trip.
**Impact:** The trip went live the same afternoon. The 0e re-test still runs, as
confirmation rather than blocker.

## [2026-09-22] — hotel_display = exact for the Mexico City trip

**Decision:** The live page shows the stay's name, address and Google Maps link.
**Why:** Two-person allowlist behind email OTP, revocable per address; an exact marker is a
materially more useful page on the ground.
**Trade-off:** A lost, unlocked device with a live session (up to 730h) shows where Rob and
Lucie are staying. Mitigation: remove the address from `trip-mates` **and** revoke the
user's sessions.
**Impact:** No mode change, so no rebuild was required; Gate 5 shipped a fresh build
(2026-09-22 16:11) that post-dates the trip file.

## [2026-09-22] — Defect 6: Gate 4's verify accepted a 404 as a pass

**Decision:** Before a slug is uploaded, Gate 4 passes only on a 302 to
`<team>.cloudflareaccess.com`. A 404 is acceptable only after upload.
**Why:** Pre-upload, the slug 404s whether or not Access is attached, so a 404 cannot
distinguish a working app from a missing one. Observed: all five paths returned 404 for 2+
minutes after the app was saved; the 302s appeared only after Rob reopened the app. Taking
the card literally would have run Gate 5 and published the trip with no login. Same shape as
defect 5 (a check satisfied by a broken state).
**Impact:** Card amendment routed to Gage (TASKS, Next). General rule: a verify that also
passes when the feature is absent is not a verify.
