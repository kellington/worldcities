---
name: worldcities
tagline: "Map posters + trip sites. A personal fork of originalankur/maptoposter that generates print-quality city map posters from OpenStreetMap data, plus tripsite/, which builds private static trip websites hosted at worldcities.ca."
group: Utilities
profile: Utility
priority: 19
status: "Live; dormant since 2026-10-06. Mexico City trip site up on worldcities.ca behind Cloudflare Access; milestone still waits on the second invitee's first login, and the iPhone test is undone with the trip freeze starting 2026-10-23. Poster CLI unchanged."
generated: 2026-10-17
questions_for_rob:
  - question: "Has the second invitee received the trip link and logged in?"
    blocks: "Milestone close and PLAN.md rewrite; proves the allowlist entry before the 2026-10-23 trip."
    asked: 2026-10-06
  - question: "Delete the Route 53 hosted zone now (Gate 0g, eligible since 2026-10-05)?"
    blocks: "Nothing urgent; zone is the mail rollback and costs ~$0.50/mo."
    asked: 2026-10-06
  - question: "www.worldcities.ca: redirect to apex (recommended)?"
    blocks: "www stays dark until decided."
    asked: 2026-10-06
  - question: "Is auto-renew on for worldcities.ca (expires 2026-12-02)?"
    blocks: "Lapse would take down the trip site and rob@worldcities.ca mail."
    asked: 2026-10-17
  - question: "Keep or drop the uncommitted README.md 'Prototype' link to the live trip URL?"
    blocks: "README.md can't be committed; link exposes the trip slug on the public repo front page."
    asked: 2026-10-17
---
