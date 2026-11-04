import { AnalysisResponse } from "../api";
import { ActiveSource } from "../App";

export function StatusBar(props: {
  health: { version: string; online: boolean };
  active: ActiveSource | null;
  analysis: AnalysisResponse | null;
  dirty: boolean;
  analyzing: boolean;
  engineFailure: string | null;
  caret: { line: number; col: number };
}) {
  const { health, active, analysis, dirty, analyzing, engineFailure, caret } = props;
  return (
    <footer className="statusbar">
      <span className="sb-item">
        <span
          aria-hidden="true"
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            background: health.online ? "var(--state-ok)" : "var(--state-error)",
          }}
        />
        engine {health.online ? `v${health.version}` : "offline"}
      </span>
      {active && (
        <>
          <span className="sb-item">
            <span className="sb-strong">{active.filename}</span>
          </span>
          <span className="sb-item">
            Ln {caret.line}, Col {caret.col}
          </span>
          <span className="sb-item">
            {analysis ? `${analysis.meta.bytes} B · ${analysis.meta.lines} lines` : `${active.source.length} B (unedited count)`}
          </span>
          <span className="sb-item">
            {analysis
              ? `${analysis.summary.token_count} tokens`
              : "not analyzed"}
          </span>
          <span className="sb-item">
            {analyzing
              ? "analyzing…"
              : dirty
                ? "modified since analysis"
                : analysis
                  ? analysis.summary.ok
                    ? "clean"
                    : `failed at ${analysis.summary.failed_layer}`
                  : ""}
          </span>
        </>
      )}
      <span className="sb-item" style={{ marginLeft: "auto" }}>
        {engineFailure ? (
          <span style={{ color: "var(--state-error)" }}>{engineFailure}</span>
        ) : (
          <>fixed-format frame · cols 1–6 seq · 7 ind · 8–72 code · 73+ rejected</>
        )}
      </span>
    </footer>
  );
}
