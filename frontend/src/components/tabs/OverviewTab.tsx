import { AnalysisResponse, SymbolRow } from "../../api";

const STAGES = ["Preflight", "Lexical", "Grammar", "AST"];

function SymbolCard({ sym, depth = 0 }: { sym: SymbolRow; depth?: number }) {
  const pic =
    sym.picture ??
    (sym.children && sym.children.length > 0 ? null : undefined);
  return (
    <div className="sym" style={depth > 0 ? { marginLeft: "var(--sp-3)" } : undefined}>
      <div className="sym-head">
        <span className="sym-name">{sym.name}</span>
        <span className="sym-meta">
          L{sym.level} · {sym.section}
          {sym.usage ? ` · ${sym.usage}` : " · DISPLAY"}
          {sym.sign ? ` · SIGN ${sym.sign}` : ""}
        </span>
        {pic && <span className="sym-pic">PIC {pic}</span>}
      </div>
      {sym.expanded && (
        <div className="sym-meta" style={{ marginTop: 2 }}>
          {sym.expanded.signed ? "signed" : "unsigned"} ·{" "}
          {sym.expanded.int_digits} int + {sym.expanded.frac_digits} frac ={" "}
          {sym.expanded.int_digits + sym.expanded.frac_digits} digits
        </div>
      )}
      {sym.value != null && (
        <div className="sym-meta" style={{ marginTop: 2 }}>
          VALUE {sym.value}
        </div>
      )}
      {sym.children && sym.children.length > 0 && (
        <div style={{ marginTop: "var(--sp-1)" }}>
          {sym.children.map((c) => (
            <SymbolCard key={c.name + c.line} sym={c} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export function OverviewTab({
  analysis,
}: {
  analysis: AnalysisResponse;
}) {
  const s = analysis.summary;
  const idDiv = analysis.ast?.identification_division as
    | { program_name?: string; is_initial?: boolean }
    | undefined;
  const symbols = (analysis.ast?.symbols ?? null) as
    | { working_storage: SymbolRow[]; linkage: SymbolRow[]; using_resolved: string[] }
    | null;
  const procDiv = analysis.ast?.procedure_division as
    | { sentences?: unknown[]; using?: string[] }
    | undefined;

  return (
    <div>
      <div className="ov-section">
        <h3>PIPELINE</h3>
        <div className="pipeline">
          {STAGES.map((name) => {
            const layer = analysis.layers.find((l) => l.layer === name);
            const status = layer?.status ?? "skipped";
            return (
              <div key={name} className={`pl-stage ${status}`}>
                <div className="pl-name">{name.toUpperCase()}</div>
                <div className="pl-status">
                  {status === "passed"
                    ? layer?.diagnostics
                      ? `PASS · ${layer.diagnostics} finding${layer.diagnostics === 1 ? "" : "s"}`
                      : "PASS"
                    : status === "failed"
                      ? "FAIL"
                      : "—"}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="ov-section">
        <h3>PROGRAM</h3>
        <dl className="ov-kv">
          <dt>Program-ID</dt>
          <dd>{s.program_name ?? (idDiv?.program_name ?? "—")}</dd>
          <dt>Source file</dt>
          <dd>{analysis.meta.name}</dd>
          <dt>Attributes</dt>
          <dd>{s.is_initial || idDiv?.is_initial ? "IS INITIAL" : "non-INITIAL"}</dd>
          <dt>Size</dt>
          <dd>
            {analysis.meta.bytes} B · {analysis.meta.lines} lines
          </dd>
          <dt>USING parameters</dt>
          <dd>
            {s.using && s.using.length > 0
              ? s.using.join(", ")
              : procDiv?.using && procDiv.using.length > 0
                ? procDiv.using.join(", ")
                : "none"}
          </dd>
          <dt>Verdict</dt>
          <dd
            style={{
              color: s.ok ? "var(--state-ok)" : "var(--state-error)",
              fontWeight: 600,
            }}
          >
            {s.ok
              ? "within the frozen subset"
              : `rejected at ${s.failed_layer} layer`}
          </dd>
        </dl>
      </div>

      {symbols && (symbols.linkage.length > 0 || symbols.working_storage.length > 0) && (
        <div className="ov-section">
          <h3>DATA · SYMBOL TABLE</h3>
          {symbols.linkage.map((sym) => (
            <SymbolCard key={`lk-${sym.name}-${sym.line}`} sym={sym} />
          ))}
          {symbols.working_storage.map((sym) => (
            <SymbolCard key={`ws-${sym.name}-${sym.line}`} sym={sym} />
          ))}
        </div>
      )}

      {procDiv?.sentences && (
        <div className="ov-section">
          <h3>PROCEDURE</h3>
          <dl className="ov-kv">
            <dt>Sentences</dt>
            <dd>{procDiv.sentences.length}</dd>
            <dt>Statements</dt>
            <dd>
              {
                (procDiv.sentences as { statements?: unknown[] }[]).reduce(
                  (acc, sent) => acc + (sent.statements?.length ?? 0),
                  0,
                )
              }
            </dd>
          </dl>
        </div>
      )}
    </div>
  );
}
