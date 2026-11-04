import { AnalysisResponse, SemanticSymbol } from "../../api";

function SymRow({ sym, depth }: { sym: SemanticSymbol; depth: number }) {
  const open = depth < 2;
  return (
    <>
      <div
        className="dd-row"
        style={{ paddingLeft: `${12 + depth * 18}px` }}
        role="row"
      >
        <span className="dd-caret">{sym.children.length > 0 ? (open ? "▾" : "▸") : "·"}</span>
        <span className="dd-name">{sym.name}</span>
        <span className="dd-meta">
          L{sym.level}
          {sym.picture ? ` · PIC ${sym.picture}` : ""}
          {` · ${sym.category}`}
          {` · ${sym.usage_label}`}
        </span>
        <span className="dd-numbers">
          {sym.byte_length != null && <span title="storage bytes">{sym.byte_length}B</span>}
          {sym.digits != null && (
            <span title="digits">
              {sym.integer_digits}.{sym.fractional_digits}
            </span>
          )}
          {sym.signed && <span className="dd-signed">S</span>}
          {sym.value != null && <span title="VALUE clause">= {sym.value}</span>}
        </span>
      </div>
      {open &&
        sym.children.map((c) => (
          <SymRow key={c.name + c.line} sym={c} depth={depth + 1} />
        ))}
    </>
  );
}

export function DataTab({
  analysis,
  onJump,
}: {
  analysis: AnalysisResponse;
  onJump: (line: number | null, col?: number | null) => void;
}) {
  const symbols = analysis.symbols;
  if (!symbols) {
    return (
      <div className="inspector-empty">
        No data dictionary — the source did not reach semantic analysis.
      </div>
    );
  }
  const items = symbols.flatMap((s) => [s, ...s.children]);
  return (
    <div>
      <div className="view-note">
        {analysis.semantic_counts
          ? `${analysis.semantic_counts.data_items} data items · ${analysis.semantic_counts.declared_identifiers} declared identifiers · lengths derived from the declared PICTUREs and USAGE`
          : ""}
      </div>
      <div className="dd-tree" role="table" aria-label="Data dictionary">
        {symbols.map((root) => (
          <div key={root.name + root.line} className="dd-group">
            <button
              className="dd-section"
              onClick={() => onJump(root.line, root.col)}
              title="Jump to declaration"
            >
              {root.section} SECTION
            </button>
            <SymRow sym={root} depth={0} />
          </div>
        ))}
        {items.length === 0 && (
          <div className="inspector-empty">No data declarations.</div>
        )}
      </div>
    </div>
  );
}
