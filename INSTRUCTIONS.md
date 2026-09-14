# Team instructions

**Read this before you touch anything.** It covers what we are building, how the
work is sequenced, and the rules that are not negotiable. It takes ten minutes.

---

## 1. What we are building, in one paragraph

A pipeline that collects public self-disclosure documents from universities —
Indian NIRF submission PDFs, US Common Data Set pages — stores them without
altering them, extracts KPI values, and indexes everything so that **every single
number can be traced back to the exact rectangle on the exact page of the exact
file it came from.** Iteration 1 covers three institutions over two years. The
output is a demo for a university president.

## 2. Why the rules are strict

The investigation that produced this design found a failure mode that defines the
whole project. NIRF PDFs are rotated 90 degrees internally. Read with ordinary
code, they produce **fluent, correctly-formatted, completely wrong output with no
error raised** — real numbers attached to the wrong labels. Nothing crashes.
Nothing looks broken. You only find out by checking a value by hand.

A separate incident: the word-parser for the digits-vs-words checksum reported
nine data defects, and **four of them were the parser's own bugs**. Two of those
four looked exactly like real findings. Had they shipped, the report accusing
four institutions of sloppy data would itself have been the sloppy artifact.

So the operating principle is:

> **A crash is a good outcome. A plausible wrong number is the failure we exist
> to prevent.**

Every rule in `CLAUDE.md` traces back to one of those two incidents. If a rule
seems paranoid, it is because something already went wrong there.

## 3. Roles

| Role | Owns | Minimum |
|---|---|---|
| **Operator** | Runs the Claude Code session for a phase, pastes the prompt, does not edit code mid-session | 1 per phase |
| **Reviewer** | Reads the gate file, signs it off or rejects it. **Cannot be the same person as the operator for that phase.** | 1 per phase |
| **Domain owner** | Decides mapping questions in the P2E review queue. Needs to understand the KPI dictionary, not the code. | 1 for the project |
| **Integrator** | Owns `CLAUDE.md`, `PROMPTS.md`, the gate chain, and merges | 1 for the project |

The operator/reviewer split is the only process control we have. Do not collapse
it because a phase looks trivial.

---

## 4. One-time setup

Run these in order. Do not skip step 6 — it is a real check, not a formality.

```bash
# 1. repo
mkdir kpi && cd kpi && git init

# 2. tree
mkdir -p findings notes registry/client-docs prompts gate \
         raw docs values derived db scripts
touch gate/.gitkeep raw/.gitkeep docs/.gitkeep values/.gitkeep derived/.gitkeep

# 3. the three governance files
#    CLAUDE.md      -> repo root            (loads automatically every session)
#    PROMPTS.md     -> prompts/
#    INSTRUCTIONS.md-> repo root
#    scaffold/*     -> copy into place (pyproject.toml, docker-compose.yml,
#                      .gitignore, registry/IN_sources.yaml)

# 4. the six investigation documents
#    findings/iteration-1-source-investigation.md
#    findings/digits-words-checksum-analysis.md
#    findings/nirf-coverage-of-229-kpis.md
#    notes/methodology.md
#    notes/v2-spec-disagreements.md
#    notes/dictionary-defect-verification.md
#    Exact filenames matter — CLAUDE.md names these paths and fails closed.

# 5. client originals, read-only
cp /path/to/DOC-20260901-WA0019.xlsx registry/client-docs/
cp /path/to/requirement-spec.docx     registry/client-docs/
cp /path/to/parameters.docx           registry/client-docs/
chmod 444 registry/client-docs/*

# 6. environment
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# 7. pre-warm Docling models (downloads layout + TableFormer weights)
python -c "from docling.document_converter import DocumentConverter; DocumentConverter()"

# 8. (was a licence scan for client work — not required for a college project.
#    Optional if you want it anyway: pip-licenses --format=markdown | grep -i GPL)

# 9. database
docker compose up -d
docker compose exec db psql -U postgres -d kpi -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 10. baseline
git add -A && git commit -m "scaffold"
```

**Verify before starting P0:**

- [ ] `CLAUDE.md` at repo root
- [ ] All six documents resolve at the exact paths listed
- [ ] Docling import succeeds and models are cached
- [ ] `docker compose ps` shows the db healthy
- [ ] Clean `git status`

---

## 5. How a phase works

```
   1. Reviewer confirms the ENTRY GATE file exists and is signed off
   2. Operator opens a FRESH Claude Code session
   3. Operator pastes exactly ONE prompt from prompts/PROMPTS.md
   4. Claude Code works; operator does not edit code mid-session
   5. Claude Code writes gate/PX-*.md and stops
   6. Reviewer reads the gate file against the checklist in §7
   7. Reviewer signs off in the gate file, or rejects with reasons
   8. Commit. Next phase, new session.
```

**One phase per session. Fresh session every time.** The gates only work if
context does not carry across — a fresh session forced to re-read `CLAUDE.md` and
the previous gate file is the mechanism, not an inconvenience.

### Phase order

```
P0  interrogate            ~1 session
P1  spike, one document    ~1 session      ← THE FORK, see §8
P2A acquisition            1–2 sessions
P2B classify + convert     1–2 sessions
P2C extract + checksum     2–3 sessions
P2E profiles + review      ~2 sessions
P2D index                  ~1 session
P3  diagram                ~1 session
P4  review                 ~1 session
```

P2E deliberately comes **before** P2D: the `profile` and `mapping_candidate`
tables are part of the schema, and discovering that after writing `schema.sql`
means a migration.

---

## 6. Rules for operators

**Do**

- Paste the prompt verbatim. It is written to be strict; softening it defeats it.
- Let Claude Code stop when a stop condition fires. A refusal to proceed is the
  system working.
- Paste real terminal output into gate files. "It worked" is not evidence.

**Do not**

- Do not tell Claude Code to "just continue" past a stop condition. If you think
  it stopped wrongly, escalate to the integrator — do not override in-session.
- Do not hand-edit code during a phase to make a test pass. If the test fails,
  that is the result.
- Do not run two phases in one session, even if the first finishes early.
- Do not skip the self-verification output. Every phase prints distributions
  before exiting; if that output is missing from the gate file, reject it.
- Do not install anything not in `pyproject.toml` without the integrator's
  sign-off. Untracked dependencies make the repo unreproducible for the rest
  of the team.

---

## 7. Reviewer checklist

Refuse to sign a gate file unless **all** of these hold.

**Every phase**

- [ ] Actual command output is pasted, not summarised
- [ ] Every claim carries `[VERIFIED]` / `[CARRIED-FORWARD]` / `[ASSUMED]` / `[OPEN]`
- [ ] Self-verification ran and its output is present
- [ ] No new dependency appeared without sign-off
- [ ] Any fitted constant is commented with what it was fitted on

**P1 specifically**

- [ ] CHECK B is an **assertion**, not a visual inspection. Eyes are not a valid
      instrument against fluent-but-wrong output.
- [ ] Page rotation and text angle reported as actual values, not "confirmed"

**P2C specifically**

- [ ] The word-parser self-test ran and passed **before** any real document
- [ ] Three states present; no branch collapses UNVERIFIED into a mismatch
- [ ] The Sandip 3750000 row is `CONFLICTING` with **both** values retained and
      no winner picked
- [ ] Every reported disagreement was hand-verified against raw text runs

**P2E specifically**

- [ ] T3 (random college homepage) returned **zero** values. If it returned even
      one, this is CRITICAL — halt the project, do not sign.
- [ ] No auto-accept path exists at any threshold
- [ ] Every confidence score is displayed to the reviewer
- [ ] The P2C parser was re-expressed as config and produced byte-identical rows

**P2D specifically**

- [ ] UPDATE and DELETE on `value` are structurally prevented, not just documented
- [ ] `value.sha256`, `value.item_id`, `value.profile_id` are NOT NULL
- [ ] No UNIQUE constraint on `(kpi_code, institution_code, period_value)`
- [ ] Q4 re-run proves prior rows unchanged with a checksum

Sign-off block to append to the gate file:

```
REVIEWED BY: <name>   DATE: <date>
CHECKLIST: all items pass
NOTES: <anything the next phase should know>
STATUS: SIGNED OFF
```

---

## 8. The fork at P1

P1 CHECK B asks whether Docling recovers
`UG [4 Years Program(s)] | 1161 | 1059 | 1039 | 1030` with correct
label-to-value association.

**If it passes:** everything downstream is unchanged. Proceed to P2A.

**If it fails:** only `convert/` changes. We port the geometric reconstruction
from `notes/methodology.md` §2.5 (which already works — it was written during the
investigation) to pypdfium2. Budget one day. This is **not** a crisis and **not**
an architecture change. The storage tree, schema, checksum and citation path are
all untouched.

Claude Code is explicitly forbidden from starting that port in the same session.
Stop, record the result, escalate to the integrator, start a fresh session.

---

## 9. Escalate immediately — do not resolve in-session

| Trigger | Why |
|---|---|
| P2E T3 returns any value from a random homepage | The rotation failure in a new costume (P-15) |
| A gate file claims a write succeeded without read-back | The exact defect that nearly shipped a false changelog (P-10) |
| A mapping is auto-accepted at any confidence | P-13; a threshold of 0.34 vs 0.30 changed match counts 116 → 164 |
| Claude Code proposes relaxing any P-rule | The rules encode incidents, not preferences |
| Any phase produces values without citations | The entire premise fails |

## 10. What "done" means for iteration 1

Four things, and not one more:

1. Three institutions acquired, twice, with identical hashes
2. Every value clickable to page + bbox + source URL; **zero uncitable values**
   in the database
3. The Sandip salary cell emitting `CONFLICTING` with both readings retained and
   no winner picked
4. `docs/architecture.md` complete and a clean P4 review

Everything else — OCR branch, institutions 4 through 537, run-diff view, the
public search UI — is after the president meeting. **The meeting is a capability
proof, not a product launch.** Resist scope creep; it is the most likely way this
slips.

---

## 11. Known-open items

These are unresolved by design. Do not let anyone quietly close them by guessing.

- **Partial fingerprint behaviour** — recommended: apply known blocks, queue the
  unknown, flag `PROFILE_INCOMPLETE`. P0/A8 may override; whatever P0 decides,
  wins.
- **Sandip and MIT acquisition paths** are documented but untested end to end.
  Sandip is unranked, so the WordPress `/wp-json/wp/v2/media` route is the only
  way in. MIT is HTML, not PDF. Expect P2A to take longer than it looks.
- **Terms of use at scale.** `ROBOTSTXT_OBEY` was set to `False` globally on
  2026-09-14 (see `CLAUDE.md` "Recorded decisions") to unblock Sandip's file,
  accepted specifically because this stays a college-scope, three-institution
  showcase. **If this project ever crawls beyond its current three
  institutions, this decision must be revisited before relying on it** — a
  global robots bypass does not belong in anything larger. The registry's
  `robots_checked_at` / `terms_reviewed_at` fields are still present for that
  future reckoning; a human fills those before any full run, and Claude Code
  must leave them null in the meantime.
- **Three KPIs marked `Context`** (`FIN02`, `FIN07`, `FIN10`) need a client
  decision on direction. Do not assign them to make a gap engine work.
- **`A09` review frequency** direction is genuinely ambiguous (`years` as unit vs
  "frequency" in the definition). Flagged `assigned-v2`; surfaces for review.

## 12. Glossary

| Term | Meaning |
|---|---|
| **Artifact** | One fetched file, identified by its sha256 |
| **Manifest** | The provenance row written before anything parses an artifact |
| **Profile** | Declarative config mapping a document family's sections to KPI codes |
| **Fingerprint** | The test that decides which profile applies to a document |
| **Discovery mode** | What runs when no profile matches: propose candidates for human review |
| **Gate file** | `gate/PX-*.md` — the signed record that a phase completed |
| **P-1** | Retired. Was an AGPL/client-licensing rule, not applicable to a college project. |
| **P-2 … P-16** | Active prohibitions in `CLAUDE.md` |
| **P1 … P22** | Pattern catalogue in `notes/methodology.md` §9. **Different numbering — do not confuse the two.** |
| **CONFIRMED / CONFLICTING / UNVERIFIED** | The three checksum states. Never two. |
| **MATCH / PARTIAL / NONE** | Fingerprint outcomes |

> Note the collision: `P-7` (a prohibition, the digits/words checksum) is not
> `P7` (a pattern, published-vs-institution copy). The hyphen is load-bearing.
> When in doubt, write the full name.
