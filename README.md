# NecroSpec

A static-analysis and migration-preparation workstation for the **frozen
Rev6.4.2 COBOL subset** — a five-layer compiler-grade engine (preflight →
lexer → recursive-descent parser → semantic AST → **semantic analysis**) with
a premium dark-first engineering frontend.

Milestone 2 adds a semantic layer: a data dictionary (categories, storage
lengths, precision, hierarchy), an identifier reference index, and
capacity/precision findings — potential high-order truncation, fractional
precision loss, discarded signs, SPACES moved into numeric items, and literal
zero divisors — each with a computed evidence trail grounded in the declared
PICTUREs and literal values.

Every finding is classified (**violation** = proven against declared rules
and evidence, **risk** = possibility needing human investigation, **note**,
**unsupported** = construct outside the analyzable subset), carries a
deterministic `finding_id` and machine-readable quantities (`detail`), and
every analysis publishes `coverage` (statements analyzed, findings by class,
what needs human review) and `assumptions` (the model's recorded limits).
This is the structured contract (`schema_version` 2) future multi-file and
migration-readiness capabilities build on.

### Project analysis (multi-file dependency intelligence, Milestone 3)

```bash
python3 app/cli.py project analyze ./my-cobol-project --json
```

Provide a directory of `.cbl`/`.cob` programs and `.cpy` copybooks (nested
directories supported). NecroSpec discovers COPY and CALL relationships from
source evidence, resolves them against the project (exact basename-stem
match — COPY prefers `.cpy`, CALL prefers programs), and reports resolved,
missing, ambiguous, dynamic and unresolved relationships with the source
line as evidence. It detects cyclic copybook inclusion, flags duplicate
basenames, rejects unsafe paths, and never silently skips a file. Every
file gets a per-file result (the full single-file envelope for programs
within the frozen subset; a rejection reason for files using out-of-subset
constructs such as COPY/CALL — their dependencies are still mapped, no text
is expanded). Impact analysis lists direct dependencies/dependants,
transitive dependencies (forward) and transitive dependants (reverse), and
unresolved relationships per file; project coverage reports risk-classified
findings as items needing human review. Exit codes:
`0` no violation-class findings, `1` violations found (e.g. a missing
copybook), `2` usage/I-O error. The workstation UI gains a Project mode
(header switch): load the example project or upload a directory, browse
files, inspect relationships and impact, and view the dependency graph —
solid edges resolved, dashed edges unresolved.

### Cross-file program understanding (CALL USING + copybooks, Milestone 4)

Project analysis also builds an evidence-backed model of data passed
between programs. For every statically resolved CALL edge it scans the
caller's `CALL "target" USING …` argument list (passing style recorded —
`BY REFERENCE`/`BY CONTENT`/`BY VALUE` as written, standard by-reference
defaulting marked as such) and the receiving program's
`PROCEDURE DIVISION USING` parameters. Arguments correspond to parameters
**by position only** — identifiers are never used to infer correspondence
or business meaning. Each mapping is classified `established`,
`incomplete` (counts differ, or a declaration is missing on one side) or
`unresolved` (dynamic/unresolved target); representation comparison
(byte sizes) runs **only** when both declarations are established, and a
difference becomes a `XFD_PARAM_SIZE_MISMATCH` warning — never a claimed
incompatibility from PIC text alone. Declarations come from the parser for
subset programs (recorded `parsed`) and from a fixed-format declaration
scan for non-subset programs and copybooks (`scanned`; single-line
entries; `REDEFINES`/`OCCURS` etc. are recorded as unsupported, not
interpreted). Copybook declarations are indexed with their file + line and
associated with copying programs (nested inclusion chains, cycles guarded,
ambiguous/missing copybooks yield no association); association is
inspection evidence only — per-file semantic analysis still does not see
copybook contents (no textual expansion). The impact view gains a separate
`data_flow` section (who sends/receives data, unresolved relationships);
neither it nor the dependency view claims verified runtime impact. Findings
reuse the Diagnostic model; schema grows additively (project envelope
`schema_version` 1 → 2).

### Copybook-aware semantic analysis (Milestone 5)

Programs that COPY a copybook are outside the frozen grammar, so the
parser cannot analyse them directly. NecroSpec closes this gap without
textual expansion: each program gets a **logical data model** — its own
declarations (parser-backed for subset programs, scanned otherwise) plus
the declarations of directly and nested-included copybooks, but only
where the COPY relationship was established against project files
(never by name matching, never from ambiguous/missing references, never
for COPY REPLACING). Every effective declaration keeps full provenance:
original file, line, column, origin (`program`/`copybook`), COPY chain,
and an `established`/`partial`/`unsupported` status — unknown storage
(REDEFINES, OCCURS, level-88, unsupported USAGE such as COMP) is never
treated as zero and never silently omitted. Name resolution is exact
plus OF/IN qualification through parent groups; duplicate names are
never merged and never resolved by first match — an ambiguous reference
is reported with its candidates (`XFS_REF_AMBIGUOUS`). For programs
outside the frozen subset, semantic participation currently covers one
scanned statement shape, `MOVE src TO dst…`: capacity, precision, sign
and SPACES-to-numeric rules identical to the single-file engine, with
findings reusing the SEM_* codes and citing the receiver's **original
copybook location**. CALL USING analysis resolves copybook-defined
arguments and parameters through the same model. Project envelope grows
additively (schema 2 → 3: `cross_file.logical`); the single-file
response is unchanged.

### Statement-level data-flow analysis (Milestone 6)

Project analysis also builds a deterministic intra-program data-flow
model. Recognised operations — MOVE, COMPUTE, ADD, SUBTRACT, MULTIPLY,
DIVIDE — are recorded per program with operands, receivers, literal
sources, options (ROUNDED, GIVING, TO/FROM/INTO/BY, REMAINDER,
ON SIZE ERROR), guarding conditions (IF/ELSE/END-IF with branch),
resolved declarations with full provenance, evidence text and an
`established`/`partial`/`unresolved`/`unsupported` status. Parsed
(frozen-subset) programs extract operations from the parser's statement
trees; COPY-using programs use the source-evidence scanner, whose
arithmetic capacity/precision/sign analysis reuses the layer-5 engine
verbatim (identical thresholds, codes, severities, hints — findings
cite the receiver's original declaration location). Operations and
declarations form a per-program graph (operand→operation→receiver,
condition→operation guard edges) supporting the questions: where does
this field get its value, what contributes to it, what modifies it,
what depends on it, where is it used — exposed in the UI as the FIELD
FLOW view. Cross-program links connect CALL USING arguments to receiving
parameters at operation level (caller writes → callee reads); dynamic
targets and unresolved declarations stop the trace and say so. Static
edges are source structure, not proof of runtime execution; EVALUATE
bodies, malformed statements and unterminated scopes are recorded
unsupported with evidence, never interpreted. Project envelope grows
additively (schema 3 → 4: `cross_file.dataflow`).

### Decision-path analysis (Milestone 7)

On top of the statement model, project analysis builds a deterministic
decision-path model answering: which condition is evaluated, which
operands participate, which operations belong to the THEN branch and to
the ELSE branch, how decisions nest, where the branches converge, and
which supported operation follows the decision. Decisions reference the
M6 operation and condition records by their unchanged ids (`op_id`,
`cond_id`) — branch membership is linked in both directions, and every
M6 risk calculation, threshold and finding is untouched. Parsed
(frozen-subset) programs derive decisions from the parser's IF AST
(nesting and spans come from the grammar, never from reformatted text);
COPY-using programs track IF / ELSE / END-IF scoping line by line in the
scanner, attributing inline statements by their exact column ranges.
An ELSE branch is recorded only when the source has one — none is ever
invented; nesting follows the innermost controlling decision; the
convergence point is the first supported operation after END-IF, joined
through explicit `joins`/`decides`/`continues` graph edges and a
`sequence` (source order) per program. Conditions that cannot be parsed
are unsupported; unterminated IF scopes, EVALUATE bodies (whose
statements are never presented as branch members), GO TO / ALTER /
PERFORM transfers and orphan ELSE / END-IF are recorded with evidence,
never interpreted. Summaries are source-backed strings only — "when
WS-TOTAL is greater than 1000, the THEN branch writes ZERO to WS-COUNT"
— no business meaning is inferred. The UI DECISION PATHS section lets a
developer select a condition and read the evidence: branch operations,
nested decisions, convergence, and what could not be established.
Project envelope grows additively (schema 4 → 5: `dataflow.decisions`,
`dataflow.sequence`, project decision totals); single-file output is
unchanged.

### Command-line use (batch / CI)

```bash
python3 app/cli.py analyze src/*.cbl            # human-readable findings
python3 app/cli.py analyze src/*.cbl --json     # full structured envelopes
# exit 0 = no violations, 1 = violations found, 2 = usage/I-O error
# warnings (risks) never fail a run — they are review items, not proofs
```

Everything in this repository runs locally with **zero third-party runtime
dependencies**: the API server is Python 3 stdlib; the frontend is a static
Vite/React build served by that same process.

> Scope honesty: NecroSpec analyzes only the frozen subset defined by
> `spike_evidence/spec/` (Rev4 extract → Rev6.4.2 errata chain). Syntax outside
> the subset is **rejected with explicit diagnostics — success is never
> fabricated**. The corpus fixtures #1–#18 embedded in `app/necro/fixtures.py`
> are verbatim transcripts from the TRANSCRIPT-DERIVED USER-ATTESTED BASELINE
> (`spike_evidence/spec/rev4_extract.md` §3.1/§3.2); they are not authenticated
> originals. `[EXT]`-labeled fixtures are agent-engineered additions.

## Run it

```bash
# 1. (already built) serve API + UI from one process:
python3 app/server.py                # http://0.0.0.0:8747

# 2. or, to hack on the frontend with hot reload:
cd frontend && npm install && npm run dev   # proxies /api to :8747
python3 app/server.py                       # in another shell
```

No `pip install` needed for the server. The optional test suite needs `pytest`
(the pinned offline wheel set lives in `spike_evidence/env0/wheels/`).

## Tests

```bash
python3 -m pytest app/tests/ -v
# 205 tests: fixture-corpus behavior, per-layer rejections, preflight
# positions, PIC expansion, symbol semantics, sign rules, data dictionary
# (validated against the corpus byte annotations), references, MOVE and
# arithmetic capacity findings, zero-divisor detection, determinism,
# envelope shape, HTTP API contract, static serving, path-traversal guard,
# logical model + copybook provenance, cross-file interfaces/mappings,
# statement-level data flow, and decision-path analysis
```

Observed result (this workspace, Python 3.11.2 / pytest 9.2.0):
**205 passed in ~2.9 s**.

## API

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/health` | GET | engine identity + version |
| `/api/samples` | GET | curated corpus metadata + verbatim sources |
| `/api/analyze` | POST | `{source, filename?}` → full analysis envelope |
| `/api/engine` | GET | layer description, unsupported-syntax policy |

The analysis envelope (`meta`, `layers`, `diagnostics`, `tokens`, `ast`,
`summary`) is the **single source of truth for the UI**. The frontend contains
no hardcoded analysis results; its editor highlighting falls back to a local
display heuristic only while a file is being edited, and switches to the
authoritative backend token stream once an analysis exists.

## Layout

```
app/
  server.py           stdlib HTTP server: JSON API + static host for web_dist
  cli.py              scriptable engine access (batch/CI), stdlib only
  necro/project.py    multi-file ingestion, COPY/CALL discovery, dependency
                      graph, cycles, impact analysis (project schema v1)
examples/
  sample-project/     realistic multi-file fixture: resolved/missing/
                      ambiguous copybooks, static+dynamic CALLs, a cycle,
                      nested directories, duplicate basenames
  necro/              the engine (L1 preflight, L2 lexer, L3 grammar,
                      L4 semantic AST, fixtures, diagnostics registry)
  tests/              pytest suite (engine + HTTP contract)
  web_dist/           committed frontend build (regenerate: npm run build)
frontend/             Vite + React + TypeScript workspace
  src/tokens.css      design tokens (surfaces, states, type, spacing, motion)
  src/components/     TopBar, Rail, EditorPane, Inspector, StatusBar, dialogs
  src/components/tabs Overview / Diagnostics / Tokens / AST workspaces
tools/gen_fixtures.py regenerates fixtures verbatim from the spec extract
spike_evidence/       frozen spec + Env-0 records (immutable, see below)
DESIGN.md             design evidence: skills, tokens, UX decisions, review
```

## Known limitations

- The supported language is the **frozen subset only** (see `IDENTIFICATION/
  DATA/PROCEDURE DIVISION` grammar in `spike_evidence/spec/rev4_extract.md`):
  no paragraphs/sections, no PERFORM, no file I/O, no PICTURE editing strings
  beyond `S?9(n)?[V9(n)?]` / `S?V9(n)?` (consequently there are no
  alphanumeric elementary PICTUREs such as `X`; group items are recorded as
  "group (alphanumeric)" but the grammar already rejects their use as
  operands), no COPY, no nested programs.
- The engine performs static structural/semantic validation only. It does not
  execute programs, compute decimal results, or produce runtime artifacts;
  claims of execution or differential equivalence are out of scope.
- Semantic analysis is static capacity reasoning only: DIVIDE-derived
  precision is deliberately reported as not established, findings are
  possibilities (warnings) rather than proof of misbehavior, and a clean
  report does **not** mean a program is safe to migrate. No execution, no
  GnuCOBOL parity, no transpilation.
- Fixed-format frame rules are strict: content past column 72, TAB, CR, NUL,
  bytes ≥ 0x80, and indicator values other than space/`*`/`/` are rejected.
- The editor is a purpose-built textarea with an overlay highlight (Tab
  inserts a 4-space indent, Enter auto-indents, Escape releases focus) — no
  find/replace, multi-cursor, or bracket matching. A heavyweight editor
  dependency was evaluated and deliberately not added for this milestone.
- Decision-path analysis (Milestone 7) is structural, not a CFG engine: no
  reachability, equivalence or execution claims; EVALUATE is never
  interpreted (its bodies are not presented as IF branches); ELSE is never
  assumed; GO TO / ALTER / PERFORM transfers and unparseable conditions stop
  the path and are recorded unsupported instead of guessed.
- `frontend/node_modules/` is not persisted in this workspace; run
  `npm install` before rebuilding the frontend. `app/web_dist/` is committed
  so the product runs without Node.
- Visual review of this build was performed at the code and HTTP level only
  (see DESIGN.md §6 — browser/screenshot tooling was re-evaluated at the
  post-build quality gate and remains unobtainable: no local browser, apt
  mirrors HTTP-blocked, Playwright CDN download fails, GitHub release-asset
  redirect host unreachable).

## Provenance

The `spike_evidence/` corpus is immutable once published: no content edits,
renames, or manifest regeneration. This build does not modify it; the fixture
generator reads it read-only. Baseline status and channel dispositions are
recorded in `spike_evidence/env0/` and the P0 records.
