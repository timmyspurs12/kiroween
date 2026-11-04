import { AnalysisResponse } from "../../api";

export function DiagnosticsTab({
  analysis,
  onJump,
}: {
  analysis: AnalysisResponse;
  onJump: (line: number | null, col?: number | null) => void;
}) {
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
          The source passed every layer: frame, lexicon, grammar and semantic
          AST. It is within the frozen Rev6.4.2 subset.
        </p>
      </div>
    );
  }

  return (
    <div role="list">
      {analysis.diagnostics.map((d, i) => (
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
          {d.hint && (
            <span className="diag-hint">
              <span className="hint-label">Suggested correction: </span>
              {d.hint}
            </span>
          )}
          {d.context_line && <span className="diag-context">{d.context_line}</span>}
          <span className="diag-layer-tag">layer: {d.layer}</span>
        </button>
      ))}
    </div>
  );
}
