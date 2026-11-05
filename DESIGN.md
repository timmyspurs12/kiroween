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

## 7. Milestone 3 interface additions (project mode)

- Header gains a File/Project mode switch (same tokens, segmented control).
- Project mode: load the bundled example project or upload a directory
  (browser directory picker); file list with per-file status chips; selected
  file shows per-file verdict, relationships with evidence lines, transitive
  dependants and unresolved references (highlighted); project findings with
  classification + finding ids; deterministic circular-layout dependency
  graph (solid = resolved, dashed = missing/ambiguous/dynamic/unresolved);
  coverage + recorded model limits rendered inline.
- Correctness over decoration: every edge in the graph corresponds to a
  discovered source statement with line evidence; the graph is a view of
  the edges list, never a separate model.

## 7b. Milestone 4 interface additions (cross-file data)

- The per-file impact panel gains data-flow rows (`data →` / `← data`)
  with the same evidence treatment as dependency rows; unresolved data
  relationships are visually separated.
- A CROSS-FILE DATA section appears when the selected file participates in
  CALL USING mappings: the receiving interface (parser-backed or scanned
  origin shown), associated COPYbooks (nested chains labelled), and one
  card per CALL with positional rows — argument (line, passing style) →
  parameter (line), plus per-side declaration origin + byte sizes.
- Established is visually distinct from uncertain: green left border +
  `size =` for established/equal; amber border + `size ≠ … by reference`
  for mismatches; dimmed cards for unresolved targets. Unmatched
  arguments/parameters and "no declaration found" render in amber —
  uncertainty is never styled as success.
- Coverage adds mapping counts (established / incomplete / unresolved);
  every cross-file finding reuses the project findings list (Diagnostic
  model), so classification + finding ids stay uniform.

## 7c. Milestone 5 interface additions (effective data)

- Programs gain an EFFECTIVE DATA (LOGICAL MODEL) section: declarations
  from program source and established copybooks in one deterministic
  table — level, name, PICTURE/USAGE, byte size, status chip
  (established / partial / unsupported with reason), and an origin
  button that opens the declaring file at its original line (copybook
  origins in the state-blue accent).
- Nested COPY chains render on the row (`via A > B`); associations show
  as COPY chips with direct/nested labelling.
- Reference rows summarise resolved / ambiguous / unresolved data
  references; ambiguous references list every candidate with its origin
  — never a silent first-match pick.
- Unsupported structures and statements (REDEFINES, OCCURS, level-88,
  unsupported USAGE, non-MOVE data verbs) are listed with reasons and
  source evidence instead of being omitted or guessed.
- Coverage adds effective-declaration and reference counts, including
  copybook-origin findings. Semantic findings involving copybook data
  cite the copybook file:line in the findings list.

## 7d. Milestone 6 interface additions (data flow)

- Programs gain a DATA FLOW (STATEMENTS) section: one card per
  recognised operation — verb chip, line, status, ROUNDED / ON SIZE
  ERROR / REMAINDER / mode options, guard chips (IF line + branch),
  `→ writes` / `← from` operand chips with copybook-origin markers and
  explicit (unresolved) uncertainty, plus the statement evidence line.
- Cross-program CALL USING data flow rows show the sending/receiving
  program (clickable), the argument→parameter pair, and where the value
  is written/read — or exactly why the trace stops (unresolved
  declaration, dynamic target).
- Declaration names in EFFECTIVE DATA are buttons: selecting one opens
  FIELD FLOW — receives-value-from (with contributors and guards), used
  by (operations + roles), conditions it controls, and the
  not-proof-of-runtime note.
- Coverage adds operation/condition/link counts. Unsupported EVALUATE
  bodies and malformed statements are listed with reasons instead of
  being rendered as operations.

## 7e. Milestone 7 interface additions (decision paths)

- Programs with decision structure gain a DECISION PATHS section: a
  coverage line (decisions · with-ELSE · nested) and one card per
  top-level decision — IF chip, line, the condition text (operand
  chips), an explicit "no ELSE in source" marker when the source has no
  ELSE, and the analysis origin (parsed/scanned).
- Selecting a decision expands it in place: the condition evaluated
  (operand chips + source evidence), THEN operations and ELSE
  operations rendered as the same operation cards as DATA FLOW (status,
  options, guards, provenance), nested decisions indented beneath their
  parent (recursively selectable), and "after the decision" — the
  convergence operation with its evidence line.
- Decision boundaries that could not be established (unterminated IF,
  EVALUATE bodies, GO TO / PERFORM / ALTER transfers) are listed under
  "decision boundaries not established" with their reasons — never
  rendered as branches.
- Selection is program-scoped and resets when switching programs.
  Branch membership comes from the same operation records as M6 (no
  second model); no flowchart is drawn — evidence, ordering and source
  navigation first.

## 7f. Milestone 8 interface additions (rule candidates)

- Programs with eligible decisions gain a RULE CANDIDATES section: a
  coverage line (candidates · established structure · partial) and one
  card per candidate — RULE chip, line, the condition text, an explicit
  "no ELSE in source" marker when absent, and the structural status
  (established_structure / partial).
- Opening a candidate shows, in order: the source-derived explanation
  (with a traceability line: condition line, operation count, data-item
  count), the condition operand chips with declaration provenance, THEN
  and ELSE operations rendered as the same operation cards as DATA FLOW,
  data items read and written (chips with copybook-origin markers and
  unresolved uncertainty), downstream uses (later operations reading the
  written items, with evidence), cross-program rows (argument → callee
  parameter with the CALL line; incomplete mappings keep their
  qualification badge and never read as a complete data contract), and
  the "not established" list (unresolved operands, branch-operation
  status, argument mappings).
- Structures that could not establish a candidate (conditions without
  supported branch operations, EVALUATE bodies, unterminated IF) are
  listed under "rule structures not established" with reasons.
- Selection is program-scoped and resets on program switch. The visual
  language is the decision-path/operation one; no dashboard, scores or
  invented rule names are shown.
- Status treatments reuse the token system and never rely on colour
  alone: established-structure cards use the accent border and the
  established status token (label "established structure"; the API enum
  `established_structure` stays in the tooltip), partial cards use the
  warning status token and border. Downstream-use rows name the written
  item each use consumes ("via <item>", by declaration id from the
  candidate's own written items) or say "item not established".
- Every program with a rules section shows RULE CANDIDATES: with zero
  candidates and zero unsupported structures the section shows an
  explanatory empty state (no supported rule candidates established by
  the current analysis — not a claim that the program contains no
  business rules); with unsupported structures they are listed under
  "rule structures not established". The sample project's EVALFIX
  program demonstrates the unsupported-EVALUATE path end to end.

## 7g. Milestone 9 interface additions (project overview)

- With no program selected (the default after loading, and reachable via
  the "Project overview" item at the top of the file list), the detail pane
  shows the whole-project intelligence overview: Application inventory,
  Dependencies, Data & cross-program flow, Decisions & rule candidates,
  Investigation register, and Coverage & limitations.
- Every aggregate is paired with evidence: dependency rows cite source,
  target, kind, resolution, file + line + statement; CALL flow rows retain
  producer/consumer operation ids; rule candidates retain rule/decision ids,
  source line, condition text and branch operation ids. Program links open
  existing detail panels, and the adjacent "open source" action uses the
  existing editor callback when source text is available.
- Violations, notes and every risk finding retain their original id,
  message, evidence and best-supported source location. Risks are grouped
  only by code for headings; each original finding remains its own row.
  Project-wide findings without one exact location say so instead of
  inventing one. Unsupported constructs retain recorded reasons.
- Coverage rows state each dimension's covered/denominator explicitly and
  are never combined into a percentage; no health score is shown. The rule
  disclaimer ("discovered source structure, not verified business
  requirements") is part of the section.
- Selecting any program (or an overview row) switches to the existing
  detail panels; "Project overview" returns. Zero states are explicit
  (no cycles, no violations render as counts with no rows).

## 8. Milestone 2 interface additions

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

## 9. Skill credit

Methodology credit to the maintainers of `anthropics/skills` (frontend-design)
and `addyosmani/agent-skills` (frontend-ui-engineering). Their text was used
as guidance only; all code, tokens, and copy in this repository were written
for this build.
