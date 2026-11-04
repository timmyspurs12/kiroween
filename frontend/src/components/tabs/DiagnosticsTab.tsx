import { useMemo, useState } from "react";
import { AnalysisResponse } from "../../api";

type Filter = "all" | "error" | "warning" | "info";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "error", label: "Errors" },
  { id: "warning", label: "Warnings" },
  { id: "info", label: "Info" },
];

export function DiagnosticsTab({
  analysis,
  onJump,
}: {
  analysis: AnalysisResponse;
  onJump: (line: number | null, col?: number | null) => void;
}) {
  const [filter, setFilter] = useState<Filter>("all");

  const counts = useMemo(() => {
    const c = { error: 0, warning: 0, info: 0 };
    for (const d of analysis.diagnostics) c[d.severity] += 1;
    return c;
  }, [analysis.diagnostics]);

  const visible = useMemo(
    () =>
      filter === "all"
        ? analysis.diagnostics
        : analysis.diagnostics.filter((d) => d.severity === filter),
    [analysis.diagnostics, filter],
  );

  if (analysis.diagnostics.length === 0) {
    return (
      <div style={{ padding: "var(--sp-5) var(--sp-4)" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--sp-2)",
            color: "var(--state-ok)",
            fontWeight: 600,
            fontSize: "var(--fs-m)",
          }}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.5" />
            <path d="m4.4 7.2 1.8 1.8 3.4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          No diagnostics
        </div>
        <p style={{ color: "var(--text-mute)", fontSize: "var(--fs-s)", lineHeight: "var(--lh-body)" }}>
          The source passed every layer, and the semantic capacity analysis
          found nothing to flag: every operation fits its receivers.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="diag-filters" role="group" aria-label="Filter by severity">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            className={`filter-chip ${filter === f.id ? "active" : ""}`}
            onClick={() => setFilter(f.id)}
            aria-pressed={filter === f.id}
          >
            {f.label}
            <span className="fc-count">{counts[f.id as keyof typeof counts]}</span>
          </button>
        ))}
      </div>
      <div role="list">
        {visible.map((d, i) => (
          <button
            key={`${d.code}-${d.line ?? "x"}-${d.col ?? "x"}-${i}`}
            role="listitem"
            className={`diag-row sev-${d.severity}`}
            onClick={() => onJump(d.line, d.col)}
            title="Click to jump to the location"
          >
            <span className="diag-top">
              <span className={`sev-chip ${d.severity}`}>{d.severity.toUpperCase()}</span>
              <span className="diag-code">{d.code}</span>
              <span className="diag-loc">
                {d.line != null ? `line ${d.line}` : "—"}
                {d.col != null ? `: col ${d.col}` : ""}
              </span>
            </span>
            <span className="diag-msg">{d.message}</span>
            {d.evidence && (
              <span className="diag-evidence">
                <span className="hint-label">Evidence: </span>
                {d.evidence}
              </span>
            )}
            {d.hint && (
              <span className="diag-hint">
                <span className="hint-label">Suggested correction: </span>
                {d.hint}
              </span>
            )}
            {d.context_line && <span className="diag-context">{d.context_line}</span>}
            <span className="diag-layer-tag">
              layer: {d.layer} · {d.classification} · {d.finding_id}
            </span>
          </button>
        ))}
      </div>
      {visible.length === 0 && (
        <div className="inspector-empty">No {filter} findings.</div>
      )}
    </div>
  );
}
