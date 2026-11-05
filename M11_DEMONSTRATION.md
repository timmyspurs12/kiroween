# NecroSpec flagship demonstration (M11)

**Positioning:** Understand legacy code. Expose hidden complexity. Modernise with evidence.

This walkthrough uses the real `examples/sample-project/` analysis as the flagship. Its findings are kept intact. The small controlled readiness cases are explicitly illustrative and use the ordinary `/api/project` analyzer and existing M10 classifier; they are not customer code or customer evidence.

## Start and load the application

From the repository root:

```bash
/tmp/env0venv/bin/python app/server.py --host 0.0.0.0 --port 8747
```

Open the running NecroSpec application, select **Project**, then **Load example project**. The sample API flow is `GET /api/project/example` followed by `POST /api/project`. The loaded project is analyzed by the same code as an uploaded directory.

For a repeatable DOM/API smoke run (not browser rendering), install frontend development dependencies once and run `NECROSPEC_BASE_URL=http://127.0.0.1:8747 npm run test:workflow` from `frontend/` while the server is running. It executes the production bundle in jsdom, exercises the sample, all three controlled cases, exact-line handoff, return navigation, requests and console output.

The initial Overview reports 18 indexed files (12 programs, 6 copybooks), parser/analysis coverage, dependency counts and skipped inputs. A rejected program is not hidden; a skipped/unreadable file appears in the inventory's **SKIPPED** group. In this checked-in sample there are no skipped inputs; rejected/unsupported source still remains visible.

## Application understanding and risk discovery

On **Project overview**, select a program from the inventory to open its detail, dependency graph, findings, dataflow, decision paths and rule candidates.

- **COPY relationship:** `src/AUDTOTAL.cbl:7` contains `COPY AUDREC.` The graph and resolved-edge evidence point to `copybooks/AUDREC.cpy`. This is a project scan result; COPY remains outside the frozen single-file grammar.
- **CALL and mapping:** `src/AUDTOTAL.cbl:16` contains `CALL "GLUPDATE" USING WS-TOTAL`. The target resolves to `src/GLUPDATE.cbl`; CALL USING evidence says the mapping is incomplete and preserves the `XFD_PARAM_SIZE_MISMATCH` finding. Positional correspondence is not a verified runtime contract.
- **Dataflow/provenance:** select `AUDTOTAL` and inspect its statement flow. `COMPUTE WS-TOTAL ROUNDED = LK-AMT * WS-COUNT` at line 12, the condition at line 13 and the write at line 14 remain separate source-backed operations. Operand/declaration chips identify source file, line and copybook origin where established.
- **Rule candidate:** AUDTOTAL's `IF WS-TOTAL > 1000` at line 13 is a structural candidate with a recorded `MOVE` at line 14. It is not a validated business requirement; the candidate's branches and limitations remain in the detail panel.
- **Data-integrity risk:** `src/GLUPDATE.cbl:11` records `SEM_PRECISION_LOSS` (`risk`): the computed result carries five fractional digits while `LK-POSTED` holds two. This is a source-backed static possibility, not a claim that a production execution has truncated a value.
- **Ambiguous dependency:** `src/REPORT.cbl:6` contains `COPY USRINFO.` It has two candidates: `libA/USRINFO.cpy` and `libB/USRINFO.cpy`. The intended target remains unresolved.
- **Unsupported construct:** `src/EVALFIX.cbl:13` uses `EVALUATE`, which this frozen subset does not interpret. Its WHEN bodies are not promoted to operations or business rules.

## Migration readiness and handoff

Select **Migration readiness**. The real sample reports 12/12 programs as `investigation_required`; it has no ready or not-assessable programs. That is the actual M10 output, not a presentation problem to be hidden. The view explains:

- **Ready for planning:** existing records meet the planning-entry checks in represented scope; this is not approval or runtime proof.
- **Investigation required:** the records expose a source rejection, risk, unsupported construct, or unresolved/incomplete relationship that needs work before detailed planning.
- **Not assessable:** required records are unavailable; this is unknown, not clean or low-risk. A per-program missing-model state is not currently emitted by the normal analyzer for indexed source because it constructs the M1–M9 logical/dataflow records. A no-program project can nevertheless be project-level not assessable, with explicit skipped-input evidence.

Select a program to see its five separate dimensions, reasons, source evidence and questions. For a package example, open **Verify incomplete CALL USING mapping** for AUDTOTAL/GLUPDATE. It retains the CALL line, mapping, dependency edge and mismatch finding, states the expected outcome, and makes the completion condition explicit: verify identity, passing mode, representation and any intended mismatch from authoritative declaration/layout evidence. It does not estimate effort or claim the called program's runtime behavior.

Use the package evidence's **open L16** link to switch to the single-file editor at the cited source line. The source text is unchanged; the editor caret/selection moves to the referenced line/column. Return to Project mode to continue the handoff. Shared `copybooks/AUDREC.cpy` has five indexed program dependants; shared `src/GLUPDATE.cbl` has four caller programs. Those counts describe static dependency relationships, not runtime reachability.

### Controlled state cases (not customer code)

In the Project toolbar open **Illustrative state cases**. Each control calls `GET /api/project/readiness-examples`, then submits the selected case to the ordinary `POST /api/project` endpoint. The resulting envelope is real analyzer output:

1. **Ready — synthetic supported source:** `examples/illustrative-readiness/READY.cbl` is accepted and reaches project state `ready_for_planning` under M10's existing rules.
2. **Investigation — existing sample risk source:** the unmodified GLUPDATE sample source reaches `investigation_required` with the actual `SEM_PRECISION_LOSS` reference.
3. **Not assessable — controlled no-source input:** the fixture submits a clearly marked `error` entry for `src/UNREADABLE.cbl`, with no COBOL bytes. The API preserves it under `skipped`; the project has no indexed programs and is project-level `not_assessable`. This illustrates missing input only—not a not-assessable program and not an observed disk failure.

A banner labels every controlled case and offers a return to the flagship sample. The normal sample itself is never edited, cleaned or reclassified.

API response contracts remain project schema v8 and single-file schema 2 (exact 12 keys). For an independent check, submit the case's `files` array from the GET response to `POST /api/project`; the test suite does this for all three cases and checks the resulting M10 state and evidence.

## Evidence still needed before planning

Resolve the ambiguous copybook selection; validate CALL USING declarations, layouts and intended contracts from authoritative sources; investigate each static risk in its business and data context; account for every rejected/unsupported source construct and skipped input; and establish requirements and tests from maintainers/domain owners. NecroSpec does not provide these external facts. A planning-ready state does not substitute for them.
