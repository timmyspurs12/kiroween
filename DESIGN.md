# NecroSpec — design evidence

Design record for the NecroSpec workstation build: skills inspected and
applied, identity decisions, token system, key UX decisions, and an honest
statement of what review was and was not performed.

## 1. Skill discovery (timeboxed, done before build)

Repos inspected via GitHub API (trees + SKILL.md reads):

| Repo | Verdict |
| --- | --- |
| **anthropics/skills → `frontend-design`** | **selected** — anti-generic calibration and the plan→critique→build→review loop shaped the whole pass |
| **addyosmani/agent-skills → `frontend-ui-engineering`** | **selected** — component composition, a11y/quality floor, production-not-AI aesthetic |
| ibelick/ui-skills | not selected — animation-effect catalog, not a system |
| vercel-labs/agent-skills | not selected — framework-specific ops skills |
| aladicf/better-web-ui | not selected — checklist breadth, no identity guidance |
| junaid-pk/frontend-design-skill | not selected — thin derivative |
| rahlplx/forge-ui-skill | not selected — styling-recipe oriented |

**Installed vs available:** skills are markdown methodology documents, not
packages; both selected skills were applied *as methodology* (read in full,
calibration extracted below) — no install machinery exists or is needed.
Nothing was installed into the runtime.

**Calibration applied from `frontend-design`:**
- cream `#F4F1EA` + terracotta `#D97757` is an AI tell — avoided; so are
  SaaS-card kits (identical rounded cards, one radius everywhere,
  `rgba(0,0,0,.1)` shadows), gradient washes, tracked ALL-CAPS eyebrows,
  middle-dot meta patterns, tinted near-black, mono-for-everything, `→` on
  links, emoji-as-icons.
- The hero should be the most characteristic element of the *subject*. For a
  static-analysis instrument that is the **fixed-format frame itself**: the
  80-column ruler, zone guides at columns 7/72, and the four-stage pipeline
  strip. Boldness is spent there and nowhere else.
- Structural devices must encode real information (ours do: ruler ticks,
  zone guides, layer dots, severity chips all map to engine facts).
- Motion: one orchestrated moment (stage dots lighting up on completion) plus
  action-answering transitions only; `prefers-reduced-motion` collapses all
  of it.
- Copy: active voice, plain verbs, user-side naming ("Analyze", "Diagnostics",
  "Suggested correction").

## 2. Identity

**Dark-first precision instrument.** The domain is dissecting dead code —
the accent is **verdigris** (`#45b08c`, the patina on aged copper), with a
single amber warning tone (`#d9a33c`) borrowed from terminal phosphor.
Surfaces are four deliberate steps of near-black steel (`#14171a → #262c32`)
plus a recessed inset for code wells. Hierarchy comes from surface steps,
hairline borders and weight — **no gradients, no glassmorphism, no drop
shadow except one popover shadow and one focus ring**.

Shape language is instrument-sharp: radii are 3–5 px, everything else is
square. Exactly one family pair: a system UI stack for chrome, a system mono
stack for everything that *is* data (code, tokens, columns, codes).

## 3. Token system (`frontend/src/tokens.css`)

Reusable custom properties, consumed by every component; no component
hard-codes a color or size:

- **surfaces**: `--surface-0..3`, `--surface-inset`
- **edges**: `--edge`, `--edge-strong`, `--edge-accent`
- **text**: `--text-hi / --text / --text-mute / --text-faint`
- **semantic states**: `--state-error/-warning/-ok/-info` + dim washes; each
  diagnostic severity, pipeline stage, and status pill maps to exactly one
- **code tokens**: `--tok-keyword/ident/number/comment/punct/level/str`
- **type**: two font stacks; `--fs-2xs..xl` (10.5–18 px), three line-heights
- **spacing**: 4 px grid `--sp-1..7`
- **shape**: `--radius-s/m`, 1 px borders
- **elevation**: one popover shadow, one focus ring
- **metrics**: header/statusbar/rail/inspector dimensions
- **motion**: `--t-fast/med/slow` with a shared easing; zeroed under
  `prefers-reduced-motion`

Contrast was computed, not eyeballed (WCAG ratios on the dark surfaces):
body 10.9:1, panel-hi 14.2:1, muted 5.7:1, faint 4.8:1 (raised from 3.35
after review), accent-hi 9.1:1, on-accent 6.9:1 — all ≥ 4.5:1.

## 4. Key UX decisions

1. **Three-region workspace, not a dashboard.** Source inventory (rail) →
   COBOL editor (canvas) → inspection panel (Overview / Diagnostics / Tokens
   / AST as real tabs). No card grids anywhere.
2. **The pipeline is the chrome.** The top bar shows four layer dots that
   light green/red per the actual response `layers` array; the Overview tab
   expands the same fact with counts. The status pill shows
   `Clean · N tokens` / `N errors` / `Analyzing…` / `Not analyzed` — every
   state is backed by response data.
3. **Diagnostics are compiler-grade.** Severity chip, stable code, message,
   line:col, the real source line as context, and an actionable "Suggested
   correction" hint where the engine provides one; clicking a diagnostic
   selects the offending token in the editor and scrolls to it. Gutter marks
   mirror per-line worst severity.
4. **Editing invalidates results honestly.** Any keystroke marks the file
   `modified` (header + status bar), dims stale results (inspector renders
   the empty state), and re-analysis is one `Ctrl/Cmd+Enter` away.
5. **Token inspector is dual-source.** While a fresh analysis exists, editor
   highlighting uses the authoritative backend tokens; during editing it
   falls back to a clearly display-only local heuristic (stated in code and
   here).
6. **AST is navigable, not decorative.** Collapsible tree with kinds, labels,
   line anchors; selection opens a node-detail panel with scalar fields and a
   jump button.
7. **Provenance is part of the UI copy.** The rail states that corpus
   fixtures are verbatim transcripts from the user-attested baseline and that
   `[EXT]` fixtures are engineered — the PASS/REJECT verdicts shown there are
   *expectations*, and every sample is still really analyzed.
8. **Every state exists**: first-use card, no-analysis empty states per tab,
   analyzing spinner, clean/errors pills + toasts, per-layer failures with
   context, engine-failure notice (never masked as a diagnostic), mobile
   drawers for rail/inspector, Escape closes overlays.

## 5. Accessibility & quality floor

- `role="tablist"/tab/tabpanel`, `aria-selected`, `aria-live="polite"` toast
  region, `role="status"` pill, `role="alert"` on engine-unreachable.
- Visible `:focus-visible` ring (2 px accent) on every interactive element;
  Escape closes dialog/drawers (and releases editor focus so keyboard users
  can tab out); Analyze is keyboard-first (`Ctrl/Cmd+Enter`). The editor
  inserts a 4-space indent on Tab and auto-indents on Enter.
- Responsive: rail + inspector become slide-in drawers under 980 px; editor
  always dominant; zone legend drops first.
- Reduced-motion honored globally.

## 6. Review — exactly what was performed

- **Performed, code level:** token/consumption audit (no hardcoded colors in
  components); contrast computation (one failure found and fixed: faint text
  3.35→4.79:1); state inventory against the required state list; bundle audit
  (`grep` for hardcoded analysis results — none; `localhost/127.0.0.1` —
  none; relative `/api` URLs only).
- **Performed, HTTP level (live server on 0.0.0.0:8747):** `/`, `/api/health`,
  `/api/samples`, `/api/engine` responses verified; the exact fetch sequence
  the UI performs (samples → analyze → render fields) executed against the
  real API for clean, rejected, and [EXT] fixtures, including context lines
  and hints.
- **Re-checked at the post-build quality gate:** browser tooling was re-eval
  uated for availability without destabilizing the environment. Result —
  genuinely unobtainable, with evidence: no browser binaries in the sandbox;
  `pip install playwright` succeeds (PyPI) but `playwright install` fails at
  the CDN (HTTP blocked); `apt-get update` fails on Debian mirrors
  (151.101.x.x, same as the Env-0 finding); GitHub release assets redirect to
  `release-assets.githubusercontent.com`, which is unreachable. TCP-level
  probes to those hosts appear to "connect" but the HTTP layer fails — an
  interception false-positive, recorded here so it is not misread later.
  **No screenshots exist and none are claimed.** External inspection: run
  `python3 app/server.py` (or use the platform preview on port 8747), load a
  corpus fixture, press Analyze, then check Overview / Diagnostics (click a
  diagnostic — the editor selects the offending token) / Tokens / AST tabs;
  narrow the viewport under 980 px to see the drawer layout.
- **Not performed:** browser rendering, screenshots, click-through/visual
  regression. Any visual claim beyond the code/HTTP review above is
  therefore not made.

## 7. Milestone 2 interface additions

The visual identity is unchanged; the milestone adds information views:

- **Six inspector tabs**: Overview / **Data** / **Refs** / Diagnostics /
  Tokens / AST. Data is the semantic data dictionary (hierarchy, PICTURE,
  category, USAGE, storage bytes, digits.precision, sign, VALUE); Refs is the
  identifier reference index (declaration link + every use with role and
  location, click to navigate).
- **Diagnostics severity filters** (All/Errors/Warnings/Info chips with live
  counts) and an **Evidence** block on every finding — the computed reason
  (declared PICTUREs, established bounds), distinct from the suggested
  correction.
- The pipeline strip and Overview gain the fifth stage (Semantic) and a
  findings summary that separates established facts from possibilities.
- New styles reuse the existing tokens only (no new colors); tables and the
  dictionary tree use the same hairline/mono instrument language.
- Platform model surfaced, not decorated: every diagnostic row states its
  classification (`violation` / `risk` / `note` / `unsupported`) and
  traceable `finding_id`; the Overview semantic section states coverage
  (statements analyzed vs total), how many findings need human review, and
  the recorded model limits.

## 8. Skill credit

Methodology credit to the maintainers of `anthropics/skills` (frontend-design)
and `addyosmani/agent-skills` (frontend-ui-engineering). Their text was used
as guidance only; all code, tokens, and copy in this repository were written
for this build.
