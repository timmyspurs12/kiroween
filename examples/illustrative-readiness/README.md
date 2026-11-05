# Controlled readiness cases (M11)

These cases are teaching/evaluation aids, not customer programs and not additional grammar fixtures. They exercise the ordinary project-analysis API and unmodified M10 classification rules.

- **Ready for planning**: `READY.cbl` is a tiny synthetic fixed-format program in the supported subset. It demonstrates only the planning-entry state within represented records; it proves neither migration safety nor runtime equivalence.
- **Investigation required**: the UI's risk case reuses `examples/sample-project/src/GLUPDATE.cbl` without editing it. Its source-backed `SEM_PRECISION_LOSS` finding remains present when the file is assessed by itself.
- **Not assessable (project-level controlled input gap)**: the UI sends an explicit illustrative error entry for `src/UNREADABLE.cbl` with no source bytes. The API indexes no program, preserves the skipped-input evidence and reports the project as not assessable. This is not a source-backed program state and does not represent a real filesystem failure.

No case changes or suppresses a finding. The existing `examples/sample-project/` remains the flagship, evidence-rich demonstration.
