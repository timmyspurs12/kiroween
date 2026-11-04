import { AnalysisResponse, SymbolRow } from "../../api";

const STAGES = ["Preflight", "Lexical", "Grammar", "AST", "Semantic"];

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

  const counts = analysis.semantic_counts;
  const sev = { error: 0, warning: 0, info: 0 };
  for (const d of analysis.diagnostics) sev[d.severity] += 1;

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

      {counts && (
        <div className="ov-section">
          <h3>SEMANTIC ANALYSIS</h3>
          <dl className="ov-kv">
            <dt>Data items</dt>
            <dd>{counts.data_items}</dd>
            <dt>Declared identifiers</dt>
            <dd>{counts.declared_identifiers}</dd>
            <dt>Identifier references</dt>
            <dd>{counts.references} (all resolved)</dd>
            <dt>Findings</dt>
            <dd>
              <span style={{ color: sev.error ? "var(--state-error)" : undefined }}>
                {sev.error} error{sev.error === 1 ? "" : "s"}
              </span>
              {" · "}
              <span style={{ color: sev.warning ? "var(--state-warning)" : undefined }}>
                {sev.warning} warning{sev.warning === 1 ? "" : "s"}
              </span>
              {" · "}
              <span style={{ color: sev.info ? "var(--state-info)" : undefined }}>
                {sev.info} info
              </span>
            </dd>
          </dl>
          {analysis.coverage && (
            <dl className="ov-kv" style={{ marginTop: "var(--sp-2)" }}>
              <dt>Coverage</dt>
              <dd>
                {analysis.coverage.statements_analyzed}/
                {analysis.coverage.statements_total} statements analyzed
              </dd>
              <dt>Needs human review</dt>
              <dd>{analysis.coverage.needs_human_review} finding(s)</dd>
              <dt>Model limits</dt>
              <dd>
                {analysis.assumptions?.length ?? 0} on record
                <span
                  title={(analysis.assumptions ?? [])
                    .map((a) => `${a.topic}: ${a.detail}`)
                    .join("\n")}
                  style={{ color: "var(--text-faint)", marginLeft: 6, cursor: "help" }}
                >
                  (hover for the list)
                </span>
              </dd>
            </dl>
          )}
          {sev.warning > 0 && (
            <p className="ov-note">
              Warnings are possibilities established from declared PICTUREs
              and literal values (capacity, precision, sign) — not program
              failures. See the Diagnostics tab for the evidence behind each.
            </p>
          )}
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
