# RENAME runbook — `maptoposter` → `worldcities`

Written by Gage, 2026-09-21. **Nothing in here has been executed.** Every command
below is for Rob to run. Gates are ordered; run them in order and paste output back
before starting the next one.

Readings taken this session (the preconditions the gates below rest on):

| Reading | Value |
|---|---|
| Working tree | clean (`git status --porcelain` empty) |
| `main` | `fbff266` Merge branch 'vscode' — tracks `origin/main`, level |
| `vscode` | `4f187ac` tripsite: links, keep flag, airport, metro lines — tracks `origin/vscode`, level |
| Remotes | `origin` only → `https://github.com/kellington/maptoposter.git`. **No `upstream` remote exists.** |
| Tests | `164 tests, OK (expected failures=7)` in 0.802s |
| Trip build | OK — slug `mexico-city-2026-8877`, 5 files written |
| Poster CLI | `--list-themes` OK, `import create_map_poster` OK |

Scope note: worldcities = **map posters + trip sites**. `create_map_poster.py` and
`posters/` keep their names; the poster feature stays supported. This rename is a
label change, not a feature removal.

---

## Corrections to the brief (read before starting)

Four assumptions in the job packet didn't survive contact with the repo:

1. **`.github/workflows/pr-checks.yml` contains zero occurrences of "maptoposter".**
   It references `create_map_poster.py`, `font_management.py`, `test/all_variations.sh`
   by filename only — all unchanged by this rename. **No edit needed.** (Verified.)
2. **`AI+PROCESS.md` contains zero occurrences.** The hit is in the generated
   `AI+PROCESS.html` (line 154), which *is* tracked.
3. **`uv.lock` is tracked even though `.gitignore` lists it** (it was committed before
   the ignore rule; tracking wins over ignore). It contains `name = "maptoposter"` at
   line 387 with `source = { editable = "." }`. So the `pyproject.toml` name change
   **produces a tracked `uv.lock` diff** that must be committed. This is the one file
   the brief didn't anticipate as a commit-bearing change.
4. **`.venv` does hold the old absolute path, but `grep -r` will not find it.**
   On this machine `grep -rIl maptoposter .venv` returns **0** while
   `find .venv -type f | xargs grep -l maptoposter` returns **4**. Any verification
   step that uses `grep -r` under `.venv` will give a false "clean". Use `find | xargs`
   or `git grep` (which never reads `.venv` at all). The 4 files are listed in Gate 4.

**Ordering correction:** the brief's order recreates the venv (Gate 4) *before* the
`pyproject.toml` name change (Gate 5), which means the venv gets rebuilt with the old
package name and needs rebuilding again. Gate 5 therefore ends with a second `uv sync`
and a re-run of the Gate 4 verification. If you'd rather sync once, do Gate 5's
`pyproject.toml` edit before Gate 4 and skip Gate 5's re-sync.

---

## GATE 1: Pre-flight — freeze the facts

Class: local (no approval needed, but do it first)
Plan ref: brief §1

**Preconditions:** none. This is the reading everything else is checked against.

**Do exactly:**
```
cd /Users/rob/Documents/GitHub/Rob/maptoposter
git status --porcelain
git branch -vv
git remote -v
git log --oneline -1 main
git log --oneline -1 vscode
```

**Expect:**
- `git status --porcelain` prints **nothing** (clean tree).
- `main   fbff266 [origin/main]` and `vscode 4f187ac [origin/vscode]` — neither shows
  `[ahead N]` or `[behind N]`.
- `origin  https://github.com/kellington/maptoposter.git` (fetch and push), and no
  `upstream` line.

**Write down for rollback:** `main = fbff266`, `vscode = 4f187ac`. Both are already
pushed to GitHub, so GitHub itself is your backup for the code — there is no data to
export here. Nothing in this rename rewrites history.

**What breaks during the window (expected, all cosmetic):**

| Thing | Breaks when | Severity |
|---|---|---|
| The old folder path in any open shell | Gate 3 | shell `cd`s to a dead path; open a new one |
| An open VS Code / editor window on the old path | Gate 3 | file tree goes stale; reopen at the new path |
| A running `python -m http.server -d dist` preview | Gate 3 | serves from a dead path; restart it |
| `import create_map_poster` / the poster CLI | Gate 3 | editable install points at the old absolute path — fixed by Gate 4 |
| `https://github.com/kellington/maptoposter` | Gate 2 | GitHub 301-redirects it; keeps working |
| Claude Code session history for this project | Gate 3 | new path = new memory key; fixed by Gate 7 |

**Nothing serious is at risk.** No production service, no DNS, no database, no deploy
is touched by any gate in this runbook. worldcities.ca is not wired to this repo yet.

**Rollback:** nothing has changed; abort freely.

---

## GATE 2: Rename the repo on GitHub (dashboard)

Class: **remote / GitHub** — Rob runs this, Gage does not.
Plan ref: brief §2

**Preconditions (paste from Gate 1):** clean tree; `main` and `vscode` both level with
origin at `fbff266` / `4f187ac`. Do not rename with unpushed commits — nothing is lost
if you do, but the local/remote divergence makes Gate 3 harder to read.

**Blast radius:** the `kellington/maptoposter` repo only. It is a fork of
`originalankur/maptoposter`; renaming **your** fork does not touch, notify, or detach
the upstream repo. No other project in the portfolio depends on this repo's URL (checked:
no references outside `~/Documents/GitHub/CLAUDE.md` and `README.md`, both handled in
Gate 6).

**Do exactly:**
1. Open `https://github.com/kellington/maptoposter`
2. Click **Settings** (top tab bar, gear icon — repo settings, not account settings)
3. The **General** section is the landing page; the first box is **Repository name**
4. Clear the field and type: `worldcities`
5. Click **Rename**
6. A confirmation dialog appears — confirm it

**Expect on screen:** the page reloads at `https://github.com/kellington/worldcities`,
and the header reads `kellington / worldcities` with `forked from originalankur/maptoposter`
still directly beneath it.

**Verify (read-only, run locally):**
```
curl -sI https://github.com/kellington/maptoposter | head -3
```
Pass = a `301` with `location: https://github.com/kellington/worldcities`.

**Three facts to be aware of:**
- **GitHub redirects the old URL permanently** — web, `git clone`, `git fetch` and
  `git push` against the old URL all keep working. Gate 3 updates the remote anyway, so
  you're not relying on the redirect.
- **The fork link to `originalankur/maptoposter` is unaffected.** "forked from" stays,
  and upstream comparison/PR links keep working.
- **The name `maptoposter` immediately becomes available for anyone else to create
  under `kellington/`.** If you ever create a new repo with that name, GitHub breaks the
  redirect. Don't reuse the name.

**Rollback card (write before the cutover, not after):**
- **Trigger:** the rename fails, or the fork link is gone, or you decide against it.
- **Action:** Settings › General › Repository name → `maptoposter` → Rename. GitHub
  restores the original URL; the redirect reverses.
- **Who runs it:** Rob.
- **Data-loss window:** none. A rename moves no code, issues, PRs, stars or history.
- **Mechanism limit:** only while `kellington/maptoposter` is still unclaimed. Roll back
  the same day; don't leave the old name parked for weeks.
- **Rehearsed:** N/A — GitHub has no dry-run for this, and it is fully reversible.

**Paste back:** the `curl -sI` output.

---

## GATE 3: Local folder rename + remote update

Class: local filesystem + git remote config (no push, no history change)
Plan ref: brief §3

**Preconditions:** Gate 2 done and verified (the 301 confirmed).

**Before you start:** close or note every window holding the old path — editor windows,
terminal tabs, any running `http.server` preview. They will all point at a path that no
longer exists.

**Do exactly:**
```
cd /Users/rob/Documents/GitHub/Rob
mv maptoposter worldcities
cd /Users/rob/Documents/GitHub/Rob/worldcities
git remote set-url origin https://github.com/kellington/worldcities.git
git remote add upstream https://github.com/originalankur/maptoposter.git
git remote -v
```

**Expect:**
```
origin    https://github.com/kellington/worldcities.git (fetch)
origin    https://github.com/kellington/worldcities.git (push)
upstream  https://github.com/originalankur/maptoposter.git (fetch)
upstream  https://github.com/originalankur/maptoposter.git (push)
```

**Verify fetch and push both work** (this is a dry-run push — it contacts GitHub and
checks permissions but writes nothing):
```
git fetch origin
git fetch upstream
git push --dry-run origin main
git status -sb
```
Pass =
- both fetches succeed,
- `git push --dry-run origin main` reports `Everything up-to-date`,
- `git status -sb` shows `## main...origin/main` with no ahead/behind.

**Upstream check is now one command** (this is why `upstream` was added):
```
git log --oneline HEAD..upstream/main
```
Pass = **empty** (no upstream code to sync). Per the brief, upstream has only README
commits since the fork point; if this prints anything, stop and report it rather than
merging — that's a decision, not a rename step.

**Note on `upstream` push URL:** git sets fetch and push to the same URL. You have no
write access to `originalankur/maptoposter`, so a push there would simply be rejected.
If you want it belt-and-braces:
```
git remote set-url --push upstream DISABLED
```

**Rollback card:**
- **Trigger:** fetch or dry-run push fails, or the folder move broke something.
- **Action:** `cd /Users/rob/Documents/GitHub/Rob && mv worldcities maptoposter`, then
  `git remote set-url origin https://github.com/kellington/maptoposter.git` and
  `git remote remove upstream`. (Origin's old URL keeps working via the Gate 2 redirect
  even if you leave it pointing at `worldcities`.)
- **Who runs it:** Rob.
- **Data-loss window:** none — `mv` on the same volume moves the working tree and `.git`
  together, atomically. No commits involved.
- **Mechanism limit:** none.

**Paste back:** `git remote -v`, the dry-run push line, and the `HEAD..upstream/main` result.

---

## GATE 4: Recreate the Python environment

Class: local (the `uv sync` re-downloads/links packages — it is a network download, so
run it on a connection you're happy with)
Plan ref: brief §4

**Why:** the editable install hardcodes the old absolute path. Verified contents:

```
.venv/lib/python3.12/site-packages/__editable___maptoposter_0_2_0_finder.py:9:
MAPPING: dict[str, str] = {'create_map_poster': '/Users/rob/Documents/GitHub/Rob/maptoposter/create_map_poster'}
```

Four files under `.venv` carry the old name, plus the egg-info directory:

| Path | What it holds |
|---|---|
| `.venv/pyvenv.cfg` | `prompt = maptoposter` |
| `.venv/lib/python3.12/site-packages/__editable__.maptoposter-0.2.0.pth` | loads the finder |
| `.venv/lib/python3.12/site-packages/__editable___maptoposter_0_2_0_finder.py` | **the old absolute path** |
| `.venv/lib/python3.12/site-packages/maptoposter-0.2.0.dist-info/RECORD` | old dist name |
| `maptoposter.egg-info/` | old dist metadata (**not tracked** — gitignored, safe to delete) |

**Preconditions:** Gate 3 done; you are in the renamed folder.

**Do exactly** (one `rm` call, both targets, so it's a single confirmation):
```
cd /Users/rob/Documents/GitHub/Rob/worldcities
rm -rf .venv maptoposter.egg-info
uv sync
```

**Expect:** `uv sync` resolves and installs, ending with a `Installed N packages` or
`Audited N packages` line and no error.

**Verify:**
```
cd /Users/rob/Documents/GitHub/Rob/worldcities
.venv/bin/python -m unittest discover -s tripsite -p 'test_*.py'
.venv/bin/python create_map_poster.py --list-themes | head -3
.venv/bin/python -c "import create_map_poster; print('import OK')"
git status --porcelain
```
Pass =
- `Ran 164 tests ... OK (expected failures=7)` — the baseline. Fewer tests or any
  unexpected failure = stop.
- `Available Themes:` header prints.
- `import OK`.
- **`git status --porcelain` shows at most `uv.lock`** (see the note below). `.venv/`
  and `*.egg-info/` are gitignored and must not appear.

**`uv.lock` caution:** `uv sync` may rewrite the tracked `uv.lock`. If `git status` shows
it modified, run `git diff uv.lock` and read it. At this gate the only expected change is
noise (timestamps/ordering); the *intended* `uv.lock` change comes in Gate 5 when the
package name changes. If you see an unexpected dependency version move, stop and report.

**Residual check — do NOT use `grep -r` here** (it returns a false clean on this machine):
```
find .venv -type f -print0 2>/dev/null | xargs -0 grep -l maptoposter 2>/dev/null
```
Pass at this point = the same 4 files, still named `maptoposter`, because
`pyproject.toml` hasn't changed yet. They clear in Gate 5's re-sync.

**Rollback card:**
- **Trigger:** `uv sync` fails, or tests don't reach 164/OK.
- **Action:** `rm -rf .venv *.egg-info && uv sync` again. If it still fails,
  `git checkout uv.lock` to restore the committed lock, then re-sync.
- **Who runs it:** Rob.
- **Data-loss window:** none — `.venv` and `*.egg-info` are generated artifacts, both
  gitignored, fully reproducible from `pyproject.toml` + `uv.lock`.
- **Mechanism limit:** requires network for the package downloads.

**Paste back:** the test summary line and the `git status --porcelain` output.

---

## GATE 5: In-repo references

Class: local edits + one commit and push (**the commit and push are Rob's** — Gage does
not commit)
Plan ref: brief §5

**Preconditions:** Gate 4 green (164 tests OK).

**Enumerate first:**
```
cd /Users/rob/Documents/GitHub/Rob/worldcities
git grep -ni maptoposter
```

Full inventory as measured this session — 12 tracked files, 28 hits — with the
disposition of each:

| File:line | Hit | Disposition |
|---|---|---|
| `pyproject.toml:2` | `name = "maptoposter"` | **CHANGE** → `name = "worldcities"` |
| `uv.lock:387` | `name = "maptoposter"` | **REGENERATED** by `uv sync` — do not hand-edit |
| `README.md:4` | `Rob's version of https://github.com/originalankur/maptoposter.git` | **KEEP** — upstream credit |
| `README.md:10` | `<img src=...originalankur/maptoposter/tree/main/posters/...>` | **KEEP** — upstream credit |
| `README.md:15` | `See: https://github.com/originalankur/maptoposter/tree/main/posters` | **KEEP** — upstream credit |
| `project/diary/diary-2026-04.md:4` | `reforked from source .../originalankur/maptoposter.git` | **KEEP** — historical record, and `project/` is Alice's lane |
| `project/status/STATUS-SUMMARY.md:2` | `name: maptoposter` | **ALICE** — protocol file |
| `project/status/STATUS-SUMMARY.md:3` | `tagline: A personal fork of originalankur/maptoposter...` | **ALICE** — keep the upstream half of the sentence |
| `project/status/status-2026-06-08.html` (4 hits) | title/header/badge/footer | **KEEP** — dated historical artifact, don't rewrite the past |
| `project/status/status-2026-06-11.html` (4 hits) | title/header/badge/footer | **KEEP** — dated historical artifact |
| `project/status/status-2026-09-17.html` (4 hits) | title/header/badge/footer | **KEEP** — dated historical artifact |
| `AI+PROCESS.html:154` | `<span class="name">maptoposter</span>` | **CHANGE** → `worldcities` (tracked generated page; if it's regenerated from a source, regenerate instead) |
| `AI+PROCESS.md` | **zero hits** | no change |
| `.github/workflows/pr-checks.yml` | **zero hits** | **no change** — references filenames only |
| `AGENTS.md` (6 hits) | see below | **ALICE** — protocol file, listed not edited |
| `CLAUDE.md:1` | `# CLAUDE.md — maptoposter` | **ALICE** — protocol file, listed not edited |
| `.claude/commands/project-status.md` (6 hits) | see below | **ALICE** — `.claude/` path, listed not edited |

### The one edit Gage would make, stated exactly

`pyproject.toml` line 2:
```
-name = "maptoposter"
+name = "worldcities"
```
Leave everything else in that file alone — in particular
`py-modules = ["create_map_poster"]` (line 52) and the `authors` block crediting
Ankur Gupta. The **module** name does not change, so no `import` anywhere breaks.

Optionally `AI+PROCESS.html:154` `maptoposter` → `worldcities`.

### Exact edits for Alice to make (protocol files — Gage does not touch these)

**`CLAUDE.md`**
- Line 1: `# CLAUDE.md — maptoposter` → `# CLAUDE.md — worldcities`
- The "What this repo is" section currently says *"A clone of a map poster generator,
  customized for personal use... No productization plans."* That is now stale: it omits
  tripsite entirely. Suggested replacement scope line: *"worldcities = map posters +
  trip sites. A fork of originalankur/maptoposter (poster engine, still supported) plus
  `tripsite/`, which builds static trip websites hosted on Cloudflare Pages at
  worldcities.ca."*

**`AGENTS.md`** (6 hits — this file is about the poster engine and mostly stays)
- Line 1: `# AGENTS.md for MapToPoster Vacation Poster Project` → `# AGENTS.md for worldcities — Map Poster Engine`
- Lines 3, 13: keep the `originalankur/maptoposter` URLs — upstream credit and accurate.
- Lines 5, 15: "the original MapToPoster project" — keep; it refers to upstream, correctly.
- Line 262, 368: "When calling MapToPoster" / "Use the existing MapToPoster CLI" — keep
  or reword to "the poster CLI"; either is accurate.
- Line 397: `maptoposter-vacations/` in an illustrative tree → `worldcities/`.

**`.claude/commands/project-status.md`** (6 hits — in-repo skill, `.claude/` is off-limits to Gage)
- Line 2 (`description:`), line 5, line 32 (`Tool name: **maptoposter**`), line 173
  (footer template), line 203 (`name: maptoposter`) → `worldcities`.
- Line 35 `Origin badge: "Fork of originalankur/maptoposter"` → **KEEP** — that badge is
  the upstream credit.

### Then re-sync and commit

```
cd /Users/rob/Documents/GitHub/Rob/worldcities
uv sync
git diff --stat
git diff uv.lock | head -20
.venv/bin/python -m unittest discover -s tripsite -p 'test_*.py'
```
Expect `uv.lock` to now show `name = "worldcities"` and the venv's
`maptoposter-0.2.0.dist-info` / `__editable__` files to be replaced by `worldcities-0.2.0`
equivalents. Re-run the Gate 4 residual check:
```
find .venv -type f -print0 2>/dev/null | xargs -0 grep -l maptoposter 2>/dev/null
```
Pass = **no output**.

**Commit and push — Rob runs these, Gage does not:**
```
git add -A
git commit -m "Rename project to worldcities"
git push origin main
```

**Rollback card:**
- **Trigger:** tests fail after the edits, or the `uv.lock` diff looks wrong.
- **Action, before committing:** `git checkout -- pyproject.toml uv.lock AI+PROCESS.html && rm -rf .venv *.egg-info && uv sync`.
- **Action, after committing but before pushing:** `git reset --soft HEAD~1` (keeps the
  edits staged) or `git reset --hard fbff266` (discards them — note this is the recorded
  pre-rename commit from Gate 1).
- **Action, after pushing:** commit a revert; do **not** force-push a public fork.
- **Who runs it:** Rob.
- **Data-loss window:** only the uncommitted edits in this gate.
- **Mechanism limit:** none.

**Paste back:** `git diff --stat`, the test summary, and the empty residual-check result.

---

## GATE 6: Outside the repo — report only, Rob or Alice acts

Class: other repos + machine config. **Gage measured these and changed nothing.**
Plan ref: brief §6

Measured this session:

| Location | Hit | Who / note |
|---|---|---|
| `/Users/rob/Documents/GitHub/CLAUDE.md:26` | `│   ├── maptoposter/                 Python` | **Alice.** Separate repo (the GitHub meta-repo) → its own commit. Stack label should also change: it's no longer only "Python" — it's Python + a Cloudflare Pages static output. |
| `/Users/rob/Documents/GitHub/README.md:67` | table row 18: `| maptoposter | Utility | Fork of originalankur/maptoposter — print-quality city map posters from OSM | [2026-09-17](Rob/maptoposter/project/status/status-2026-09-17.html) |` | **Alice.** Same separate repo, same commit. Note the row contains a **path link** that breaks on the folder rename — it must become `Rob/worldcities/project/status/...`. The description should gain the trip-site half. |
| `*.code-workspace` anywhere under `~/Documents/GitHub` (depth 2) | **none found** | nothing to do |
| `~/.claude/skills`, `~/.claude/commands`, `~/.claude/agents`, `~/.claude/CLAUDE.md` | **zero hits for "maptoposter"** | The `project-status` skill that names maptoposter is the **in-repo** one at `.claude/commands/project-status.md`, covered in Gate 5. There is no global copy. |
| `~/.claude/ide/*.lock`, `~/.claude/history.jsonl`, `~/.claude/sessions/*.json`, `~/.claude/backups/*.json.backup` | old path present | **Leave alone.** Transient/append-only session state; it self-heals as you use the new path. Editing it risks corrupting Claude Code's own state for no benefit. |

Note the two `~/Documents/GitHub` files are **one separate git repo** — per the workspace
CLAUDE.md, commits there belong to that repo, not to worldcities.

**Rollback:** each is a one-line text edit in a git-tracked file; `git checkout -- <file>`
in that repo.

---

## GATE 7: Claude Code memory key

Class: local machine config. **For Alice to run** (Gage may not write under `~/.claude`).
Plan ref: brief §7

Claude Code keys project memory by absolute path, slug-ified. Measured:

- Existing key: `/Users/rob/.claude/projects/-Users-rob-Documents-GitHub-Rob-maptoposter/`
  — contains 2 session `.jsonl` transcripts, 1 session dir, and a `memory/` folder holding
  `MEMORY.md` and `tripsite-direction.md`.
- Target key `/Users/rob/.claude/projects/*worldcities*` — **does not exist yet.**

Because the target doesn't exist, a plain move is safe (no merge needed):
```
mv /Users/rob/.claude/projects/-Users-rob-Documents-GitHub-Rob-maptoposter \
   /Users/rob/.claude/projects/-Users-rob-Documents-GitHub-Rob-worldcities
```

**Run this only after Gate 3**, and with no Claude Code session open on this project —
a live session holds an open handle and will rewrite the old key on exit.

**Verify:**
```
ls /Users/rob/.claude/projects/-Users-rob-Documents-GitHub-Rob-worldcities/memory
```
Pass = `MEMORY.md` and `tripsite-direction.md` are listed.

**Caveat, as briefed:** older transcripts referenced elsewhere by the old key (and the
`history.jsonl` / `sessions/` entries from Gate 6) still name the old path internally.
The moved `memory/` carries forward, which is the part that matters; old transcript
*contents* keep the old path in their text. Harmless.

**Rollback:** `mv` back to the old name. No data loss — it is a directory rename.

---

## GATE 8: Post-checks

Class: local, read-only
Plan ref: brief §8

```
cd /Users/rob/Documents/GitHub/Rob/worldcities
.venv/bin/python -m unittest discover -s tripsite -p 'test_*.py'
.venv/bin/python tripsite/build.py trips/mexico-city-2026.md --dry-run
.venv/bin/python create_map_poster.py --list-themes | head -3
git grep -i maptoposter
git remote -v
git status -sb
```

Pass criteria:
1. **Tests:** `Ran 164 tests ... OK (expected failures=7)`. Any other number = stop.
2. **Trip build dry-run:** validates without error.
3. **Poster CLI:** `Available Themes:` prints — proves the poster half still works.
4. **`git grep -i maptoposter`:** review **line by line**. Every surviving hit must be
   one of: upstream credit in `README.md` (3), the diary entry (1), the three dated
   `project/status/*.html` artifacts (12), `STATUS-SUMMARY.md` upstream half (1), the
   `AGENTS.md` upstream references, and the `project-status.md` origin badge. **Zero
   hits should be a self-reference to our own project name.**
5. **`git remote -v`:** origin → `worldcities`, upstream → `originalankur/maptoposter`.
6. **GitHub page:** open `https://github.com/kellington/worldcities` — header reads
   `kellington / worldcities`, `forked from originalankur/maptoposter` still present,
   latest commit matches your Gate 5 commit.

---

## Separate recommendation (not part of the rename): regenerate the trip slug

**This is independent of the rename and should happen before any deploy.**

The slug `mexico-city-2026-8877` is the "unguessable" suffix protecting the trip page,
but it was committed publicly before `trips/` was scrubbed from tracking. Verified:

```
$ git log --oneline -S"mexico-city-2026-8877" --all
4f187ac tripsite: links, keep flag, airport, metro lines
5ae9004 Add tripsite: static trip website generator (v0)
```

`trips/` is gitignored now, but **git history is public and permanent** — anyone can read
that slug out of those two commits. Its secrecy is spent. Since the URL's unguessability
is part of the protection model, regenerate it before the site goes live at worldcities.ca.

**The one-line edit** — `/Users/rob/Documents/GitHub/Rob/worldcities/trips/mexico-city-2026.md`, line 8:
```
-  slug: mexico-city-2026-8877          # random suffix so the URL isn't guessable
+  slug: mexico-city-2026-<NEW4>        # random suffix so the URL isn't guessable
```
Generate a fresh suffix with:
```
python3 -c "import secrets; print(secrets.randbelow(9000)+1000)"
```
(Or use more entropy — `secrets.token_hex(4)` — since 4 digits is only 9,000 options.)

**`dist/` must be rebuilt and the old folder pruned.** The build writes to
`dist/<slug>/`, so a new slug creates a *new* folder and leaves `dist/mexico-city-2026-8877/`
behind. Uploading `dist/` as-is would publish **both** — defeating the point.

```
cd /Users/rob/Documents/GitHub/Rob/worldcities
rm -rf dist
.venv/bin/python tripsite/build.py trips/mexico-city-2026.md
ls dist
```
Pass = `dist/` contains exactly one trip folder, the new slug, and no
`mexico-city-2026-8877` anywhere. Confirm with:
```
grep -rn "8877" dist || echo "clean"
```

Two notes:
- `trips/` is gitignored, so this edit produces **no commit**. Nothing to push.
- A Cloudflare Pages direct upload is a **full-site snapshot** (per `tripsite/README.md`):
  whatever is in `dist/` becomes the entire site, and any live trip not in this build is
  taken down. Build every trip you want live in one run.
- Deploying to Cloudflare Pages is a **gated action** and is deliberately not in this
  runbook. It needs its own gate card with its own rollback, written when Rob is ready.

---

## Not verified by Gage

- The GitHub rename UI path (Gate 2) is written from the standard Settings › General
  layout; Gage made no call to GitHub. Verify on screen.
- Whether `AI+PROCESS.html` is hand-maintained or generated from another source — if
  generated, regenerate rather than hand-editing line 154.
- The upstream-has-no-code-changes claim is taken from the job packet, not re-derived.
  Gate 3's `git log --oneline HEAD..upstream/main` is the check that confirms it.
- No gate in this runbook was executed. All readings are pre-rename.
