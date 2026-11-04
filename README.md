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
# 63 tests: fixture-corpus behavior, per-layer rejections, preflight
# positions, PIC expansion, symbol semantics, sign rules, data dictionary
# (validated against the corpus byte annotations), references, MOVE and
# arithmetic capacity findings, zero-divisor detection, determinism,
# envelope shape, HTTP API contract, static serving, path-traversal guard
```

Observed result (this workspace, Python 3.11.2 / pytest 9.2.0):
**63 passed in ~1.2 s**.

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
