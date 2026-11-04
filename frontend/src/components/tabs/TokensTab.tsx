import { useMemo, useState } from "react";
import { AnalysisResponse } from "../../api";

export function TokensTab({
  analysis,
  onJump,
}: {
  analysis: AnalysisResponse;
  onJump: (line: number | null, col?: number | null) => void;
}) {
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState<number | null>(null);

  const tokens = analysis.tokens;
  const filtered = useMemo(() => {
    if (!filter) return tokens;
    const q = filter.toLowerCase();
    return tokens.filter(
      (t) => t.text.toLowerCase().includes(q) || t.type.toLowerCase().includes(q),
    );
  }, [tokens, filter]);

  if (tokens.length === 0) {
    return (
      <div className="inspector-empty">
        No token stream — the source did not reach the lexical layer.
      </div>
    );
  }

  return (
    <div>
      <div
        style={{
          padding: "var(--sp-2) var(--sp-3)",
          borderBottom: "1px solid var(--edge)",
        }}
      >
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by text or type…"
          aria-label="Filter tokens"
          style={{
            width: "100%",
            padding: "5px var(--sp-2)",
            fontFamily: "var(--font-mono)",
            fontSize: "var(--fs-xs)",
            color: "var(--text-hi)",
            background: "var(--surface-inset)",
            border: "1px solid var(--edge-strong)",
            borderRadius: "var(--radius-s)",
          }}
        />
      </div>
      <table className="tok-table">
        <thead>
          <tr>
            <th>#</th>
            <th>TYPE</th>
            <th>TEXT</th>
            <th>LINE</th>
            <th>COL</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((t) => {
            const idx = tokens.indexOf(t);
            return (
              <tr
                key={idx}
                className={selected === idx ? "selected" : ""}
                onClick={() => {
                  setSelected(idx);
                  onJump(t.line, t.col);
                }}
                title="Jump to source location"
              >
                <td>{idx + 1}</td>
                <td>{t.type}</td>
                <td className="t-text">{t.text}</td>
                <td>{t.line}</td>
                <td>{t.col}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {filtered.length === 0 && (
        <div className="inspector-empty">No tokens match “{filter}”.</div>
      )}
    </div>
  );
}
