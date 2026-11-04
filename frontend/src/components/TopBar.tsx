import { AnalysisResponse, HealthInfo } from "../api";
import { ActiveSource, WorkspaceMode } from "../App";

const STAGES = ["Preflight", "Lexical", "Grammar", "AST", "Semantic"];

export function TopBar(props: {
  active: ActiveSource | null;
  dirty: boolean;
  analyzing: boolean;
  analysis: AnalysisResponse | null;
  health: HealthInfo | { version: string; online: boolean };
  onAnalyze: () => void;
  onToggleRail: () => void;
  onToggleInspector: () => void;
  mode: WorkspaceMode;
  onMode: (m: WorkspaceMode) => void;
}) {
  const { active, dirty, analyzing, analysis, onAnalyze } = props;
  const summary = analysis?.summary ?? null;

  const pillState = analyzing
    ? "analyzing"
    : summary
      ? summary.ok
        ? "ok"
        : "errors"
      : "";

  const pillText = analyzing
    ? "Analyzing…"
    : summary
      ? summary.ok
        ? `Clean · ${summary.token_count} tokens`
        : `${summary.errors} error${summary.errors === 1 ? "" : "s"}`
      : "Not analyzed";

  const isMac =
    typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
  const kbd = isMac ? "⌘↵" : "Ctrl+↵";

  return (
    <header className="header">
      <button
        className="icon-btn rail-toggle"
        onClick={props.onToggleRail}
        aria-label="Toggle source list"
        title="Sources"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
          <path d="M1 3h12M1 7h12M1 11h12" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      </button>
      <div className="wordmark">
        <span className="wordmark-mark">
          Necro<span className="tick">Spec</span>
        </span>
        <span className="wordmark-sub">COBOL analysis workstation · Rev6.4.2 subset</span>
      </div>
      {active && (
        <div className="header-file">
          <span className="fname">{active.filename}</span>
          {dirty && (
            <span className="dirty" title="Source changed since last analysis">
              modified
            </span>
          )}
        </div>
      )}
      <div className="header-spacer" />
      <div className="mode-switch" role="tablist" aria-label="Workspace mode">
        <button
          role="tab"
          aria-selected={props.mode === "file"}
          className={props.mode === "file" ? "active" : ""}
          onClick={() => props.onMode("file")}
        >
          File
        </button>
        <button
          role="tab"
          aria-selected={props.mode === "project"}
          className={props.mode === "project" ? "active" : ""}
          onClick={() => props.onMode("project")}
        >
          Project
        </button>
      </div>
      {analysis && (
        <div className="pipeline-strip" role="img" aria-label="Pipeline layer states">
          {STAGES.map((name, i) => {
            const layer = analysis.layers.find((l) => l.layer === name);
            const status = layer?.status ?? "skipped";
            return (
              <span className="stage" key={name}>
                {i > 0 && <span className="stage-link" aria-hidden="true" />}
                <span className={`stage-dot ${status}`} aria-hidden="true" />
                <span className="stage-label">{name}</span>
              </span>
            );
          })}
        </div>
      )}
      <span className={`status-pill ${pillState}`} role="status">
        <span className="dot" aria-hidden="true" />
        {pillText}
      </span>
      <button
        className="btn btn-primary"
        onClick={onAnalyze}
        disabled={!active || analyzing}
        title="Analyze the current source"
      >
        {analyzing && <span className="spinner" aria-hidden="true" />}
        {analyzing ? "Analyzing…" : "Analyze"}
        <span className="btn-kbd">{kbd}</span>
      </button>
      <button
        className="icon-btn inspector-toggle"
        onClick={props.onToggleInspector}
        aria-label="Toggle inspector"
        title="Inspector"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
          <rect x="1" y="2" width="12" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
          <path d="M8.5 2v10" stroke="currentColor" strokeWidth="1.4" />
        </svg>
      </button>
    </header>
  );
}
