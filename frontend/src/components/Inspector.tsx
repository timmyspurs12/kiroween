import { AnalysisResponse } from "../api";
import { TabId } from "../App";
import { OverviewTab } from "./tabs/OverviewTab";
import { DiagnosticsTab } from "./tabs/DiagnosticsTab";
import { TokensTab } from "./tabs/TokensTab";
import { AstTab } from "./tabs/AstTab";

const TABS: { id: TabId; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "diagnostics", label: "Diagnostics" },
  { id: "tokens", label: "Tokens" },
  { id: "ast", label: "AST" },
];

export function Inspector(props: {
  analysis: AnalysisResponse | null;
  tab: TabId;
  onTab: (t: TabId) => void;
  onJump: (line: number | null, col?: number | null) => void;
  filename: string | null;
  source: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const { analysis, tab } = props;
  const errorCount = analysis?.summary.errors ?? 0;

  return (
    <aside
      className={`inspector ${props.open ? "open" : ""}`}
      aria-label="Inspection panel"
    >
      <div className="inspector-tabs" role="tablist" aria-label="Inspection views">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            className="tab"
            onClick={() => props.onTab(t.id)}
          >
            {t.label}
            {t.id === "diagnostics" && analysis && (
              <span className={`count ${errorCount > 0 ? "err" : ""}`}>
                {analysis.diagnostics.length}
              </span>
            )}
            {t.id === "tokens" && analysis && (
              <span className="count">{analysis.summary.token_count}</span>
            )}
          </button>
        ))}
        <button
          className="icon-btn"
          onClick={props.onClose}
          aria-label="Close inspector"
          title="Close"
          style={{ marginLeft: "auto", alignSelf: "center", display: "none" }}
        >
          ×
        </button>
      </div>
      <div className="inspector-body" role="tabpanel">
        {!analysis ? (
          <div className="inspector-empty">
            {props.filename ? (
              <>
                No analysis yet for{" "}
                <code style={{ fontFamily: "var(--font-mono)", color: "var(--text)" }}>
                  {props.filename}
                </code>
                . Run <strong>Analyze</strong> to validate the frame, lex,
                parse and build the semantic AST.
              </>
            ) : (
              <>Load a source from the inventory, then run Analyze.</>
            )}
          </div>
        ) : tab === "overview" ? (
          <OverviewTab analysis={analysis} />
        ) : tab === "diagnostics" ? (
          <DiagnosticsTab analysis={analysis} onJump={props.onJump} />
        ) : tab === "tokens" ? (
          <TokensTab analysis={analysis} onJump={props.onJump} />
        ) : (
          <AstTab analysis={analysis} onJump={props.onJump} />
        )}
      </div>
    </aside>
  );
}
