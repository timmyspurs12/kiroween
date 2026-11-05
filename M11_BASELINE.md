# M11 baseline and proposed scope

## Baseline identity (before implementation)

- Repository: `/home/user/kiroween` (`timmyspurs12/kiroween`)
- Branch: `arena/c6d3bcf5-kiroween`
- Starting HEAD: `7428fd7565d136aab079842df8e6cf2626036586` (`7428fd7 Add evidence-backed migration readiness assessment`), matching the requested start.
- Working tree: clean before this baseline note; no divergence from the expected commit.
- Project envelope schema: v8; single-file envelope schema 2.

## Frozen inputs and preservation

Read `spike_evidence/spec/rev642_errata.md` and the published Rev6.4.2 manifest. Rev6.4.2 is a documentation-only correction to the userspace pointer type in one pkey_mprotect example; the frozen COBOL grammar remains defined by the earlier Rev4 extract and its supersession chain. No M11 change is proposed to the specification, grammar, historical evidence, or their manifests.

At baseline, the publication, Rev64/641/642, specification, Env0, P0 channel and wheel manifests verified successfully. The first wheel-manifest check was invoked from the wrong directory and therefore reported missing relative paths; rerunning from `spike_evidence/env0/wheels/` verified all eight wheels. `git diff --exit-code -- spike_evidence` was clean.

## Baseline verification

- Python: `/tmp/env0venv/bin/python -m pytest app/tests -q` — 257 passed.
- Frontend: `npx tsc --noEmit` — passed.
- Production frontend: `npm run build` — passed; Vite emitted the existing v8 UI bundle.
- The baseline tests include project schema 8, single-file schema 2, and M1–M10 regression coverage.

## M10 output on the existing sample project

Analyzed `examples/sample-project` through `ingest_directory` and `analyze_project` (the same engine path used by the API):

- 18 indexed physical files: 12 programs and 6 copybooks; 0 skipped inputs.
- Project readiness: `investigation_required`.
- Program distribution: 0 `ready_for_planning`, 12 `investigation_required`, 0 `not_assessable`.
- 28 investigation work packages; 2 shared dependencies, 6 unresolved interfaces, and 1 unsupported construct in the assessment summary.

The sample is credible and sufficiently rich for COPY/CALL, mappings, dataflow, rule-candidate, risk, ambiguity and unsupported-construct demonstrations. Its state distribution must not be altered to make the demo appear cleaner. The normal project analyzer currently creates both logical and dataflow records for each indexed program, so the per-program `not_assessable` fallback is not naturally represented by this source project; it means a required analysis record is missing, not a source finding. A clean fixed-format control source was also tested through `analyze_project` and reaches `ready_for_planning`. An unreadable-only project reaches project-level `not_assessable` via the real ingestion-error path, with zero programs and an explicit skipped input; that is an input-coverage state, not a not-assessable program. Do not imply otherwise or fabricate a missing analysis record.

## Existing shortest coherent journey

1. Switch the top-bar workspace mode from File to Project.
2. Choose **Load example project** (or **Upload directory…**).
3. Use the file inventory and **Project overview** for inventory, dependencies, evidence, graph, findings, dataflow, and rule candidates.
4. Choose **Migration readiness**, select a program, and inspect state/reasons/dimensions/questions.
5. Open a related work package, then use its source reference to return to the program and exact source location.

The project overview and readiness pages already have distinct purposes. M9 detailed project/program panels and M10 traceability are present and should be retained.

## Concrete baseline usability issue and proposed changes

The example endpoint returns `{files, errors}`, but `getExampleProject()` types and returns only `files`; the UI then posts only those files for analysis. Likewise, browser `FileReader` errors during directory upload increment a counter but the failing path/error is omitted from the API request. As a result, some ingestion limitations can disappear before the server's existing skipped-input reporting sees them. Fix this as an additive ingestion-path/UI correction and test it end-to-end without changing analysis rules.

`EvidenceRefRows` visibly renders file and line, but its `ProgramLink` opens the source without carrying that line into the editor; the receiving app resets the caret to line 1. Add a location-aware handoff so the engineer lands on the cited line (column where available), and test that navigation behavior.

Proposed M11 scope, subject to validation against the current implementation:

1. Preserve the existing sample and make the missing-ingestion-error reporting path lossless.
2. Add concise first-run positioning and an explicitly labelled, source-backed demonstration guide using existing project evidence; explain the three M10 states and scope without overclaiming.
3. Provide repeatable API-backed workflow checks and exact click/source handoff instructions. Do not synthesize a customer result or change any M10 classification.
4. Add the requested concise product evaluation separating demonstrated capability from customer/enterprise hypotheses.
5. Fix only concrete defects found during the end-to-end audit; preserve the visual identity, schema v8, single-file contract, and all frozen inputs.

A separate state-generating fixture is justified for evaluation, but it must be explicit and must not change M10 records: use a minimal fixed-format synthetic clean program that the normal API assesses as ready; use the existing source-backed GLUPDATE sample in isolation for investigation (its real `SEM_PRECISION_LOSS` finding persists); and use an error-only, no-source API input for project-level not_assessable. Label all controlled cases as illustrative, distinguish the no-source project state from per-program state, and never claim a not-assessable program can be sourced from the ordinary analyzer while it always emits both supplemental models for indexed programs. Use the unchanged M10 classification function and regular `/api/project` route for each.

## Browser check at baseline

Playwright Python 1.64.1 is installed, but its configured Chromium executable is absent and the Playwright cache contains no browser installation. Per the no-retry constraint, do not download browser binaries. Use API and DOM-based verification if a browser remains unavailable, and do not claim screenshot, rendering, or responsive verification.
