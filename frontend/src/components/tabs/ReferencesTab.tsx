import { AnalysisResponse, SemanticRef } from "../../api";

export function ReferencesTab({
  analysis,
  onJump,
}: {
  analysis: AnalysisResponse;
  onJump: (line: number | null, col?: number | null) => void;
}) {
  const refs = analysis.references;
  if (!refs) {
    return (
      <div className="inspector-empty">
        No reference index — the source did not reach semantic analysis.
      </div>
    );
  }
  const byName = new Map<string, SemanticRef[]>();
  for (const r of refs) {
    const arr = byName.get(r.name) ?? [];
    arr.push(r);
    byName.set(r.name, arr);
  }
  const names = [...byName.keys()].sort((a, b) => a.localeCompare(b));

  return (
    <div>
      <div className="view-note">
        {analysis.semantic_counts
          ? `${analysis.semantic_counts.references} identifier references · every use is resolved to its declaration by the semantic layer`
          : ""}
      </div>
      {names.map((name) => {
        const rows = byName.get(name)!;
        const decl = analysis.symbols
          ?.flatMap((s) => [s, ...s.children])
          .find((e) => e.name.toUpperCase() === name.toUpperCase());
        return (
          <div key={name} className="ref-group">
            <div className="ref-head">
              <span className="ref-name">{name}</span>
              {decl ? (
                <button
                  className="ref-decl"
                  onClick={() => onJump(decl.line, decl.col)}
                  title="Jump to declaration"
                >
                  declared line {decl.line} · PIC {decl.picture ?? "—"} ·{" "}
                  {decl.category}
                </button>
              ) : (
                <span className="ref-undecl">no declaration in the data division</span>
              )}
            </div>
            <table className="ref-table">
              <thead>
                <tr>
                  <th>ROLE</th>
                  <th>STATEMENT</th>
                  <th>LOCATION</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr
                    key={i}
                    onClick={() => onJump(r.line, r.col)}
                    title="Jump to this use"
                  >
                    <td>{r.role}</td>
                    <td>{r.statement}</td>
                    <td className="ref-loc">
                      {r.line != null ? `L${r.line}` : "—"}
                      {r.col != null ? ` C${r.col}` : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
      {names.length === 0 && (
        <div className="inspector-empty">No identifier references.</div>
      )}
    </div>
  );
}
