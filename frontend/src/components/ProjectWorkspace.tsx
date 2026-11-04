import { useMemo, useRef, useState } from "react";
import {
  ProjectEnvelope,
  ProjectFile,
  CrossFileMapping,
  CrossFilePosition,
  analyzeProject,
  getExampleProject,
} from "../api";

const RES_LABEL: Record<string, string> = {
  resolved: "resolved",
  missing: "missing",
  ambiguous: "ambiguous",
  dynamic: "dynamic target",
  unresolved: "unresolved",
};

function StatusChip({ status }: { status: string }) {
  const cls =
    status === "analyzed" ? "ok" : status === "rejected" ? "errors" : "";
  return <span className={`status-pill ${cls} pj-chip`}>{status}</span>;
}

/** Deterministic circular dependency graph: nodes sorted by file id,
 *  edges drawn by resolution status. Correctness over decoration. */
function DepGraph({
  env,
  selected,
  onSelect,
}: {
  env: ProjectEnvelope;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const nodes = useMemo(
    () => env.files.map((f) => f.file_id).sort(),
    [env.files],
  );
  const size = 2 * 170 + 80;
  const c = size / 2;
  const pos = new Map<string, { x: number; y: number }>();
  nodes.forEach((id, i) => {
    const a = (2 * Math.PI * i) / Math.max(nodes.length, 1) - Math.PI / 2;
    pos.set(id, { x: c + 150 * Math.cos(a), y: c + 150 * Math.sin(a) });
  });
  const short = (id: string) => id.split("/").pop() ?? id;
  return (
    <svg
      className="pj-graph"
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label="Dependency graph: nodes are files, edges are COPY or CALL relationships"
    >
      {env.edges.map((e, i) => {
        const a = pos.get(e.from);
        const b = e.to ? pos.get(e.to) : null;
        if (!a) return null;
        const cls =
          e.resolution === "resolved"
            ? "pj-edge resolved"
            : e.resolution === "missing"
              ? "pj-edge missing"
              : e.resolution === "ambiguous"
                ? "pj-edge ambiguous"
                : "pj-edge unresolved";
        if (b) {
          return <line key={i} className={cls} x1={a.x} y1={a.y} x2={b.x} y2={b.y} />;
        }
        // dangling edge: short marker toward the target name position
        const t = e.target;
        const hx = a.x + (t.charCodeAt(0) % 30) - 15;
        return (
          <line key={i} className={cls} x1={a.x} y1={a.y} x2={hx} y2={a.y - 26} />
        );
      })}
      {nodes.map((id) => {
        const p = pos.get(id)!;
        const f = env.files.find((x) => x.file_id === id)!;
        const fill =
          f.kind === "copybook" ? "var(--tok-level)" : "var(--accent)";
        return (
          <g key={id} onClick={() => onSelect(id)} className="pj-node">
            <circle
              cx={p.x}
              cy={p.y}
              r={selected === id ? 8 : 5}
              fill={fill}
              stroke={selected === id ? "var(--text-hi)" : "none"}
              strokeWidth={1.5}
            />
            <text x={p.x} y={p.y - 11} textAnchor="middle" className="pj-node-label">
              {short(id)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function ProjectWorkspace(props: {
  onOpenSource: (filename: string, content: string) => void;
  sourcesRef?: Record<string, string>;
}) {
  const [env, setEnv] = useState<ProjectEnvelope | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirInputRef = useRef<HTMLInputElement>(null);

  const runProject = async (name: string, files: { path: string; content: string }[]) => {
    setBusy(true);
    setError(null);
    try {
      const result = await analyzeProject(name, files);
      if (props.sourcesRef) {
        for (const f of files) props.sourcesRef[f.path] = f.content;
      }
      setEnv(result);
      setSelected(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "project analysis failed");
    } finally {
      setBusy(false);
    }
  };

  const loadExample = async () => {
    setBusy(true);
    setError(null);
    try {
      const ex = await getExampleProject();
      await runProject(ex.name, ex.files);
    } catch (err) {
      setError(err instanceof Error ? err.message : "example project unavailable");
      setBusy(false);
    }
  };

  const uploadDir = (files: FileList) => {
    const list = Array.from(files);
    if (list.length === 0) return;
    setBusy(true);
    let done = 0;
    const out: { path: string; content: string }[] = [];
    const rootName =
      (list[0]?.webkitRelativePath ?? "").split("/")[0] || "project";
    list.forEach((f) => {
      const reader = new FileReader();
      reader.onload = () => {
        const rel = f.webkitRelativePath || f.name;
        // strip the leading folder name for stable relative identities
        const path = rel.includes("/") ? rel.split("/").slice(1).join("/") : rel;
        out.push({ path, content: String(reader.result ?? "") });
        done += 1;
        if (done === list.length) {
          void runProject(rootName, out);
        }
      };
      reader.onerror = () => {
        done += 1;
        if (done === list.length) void runProject(rootName, out);
      };
      reader.readAsText(f);
    });
  };

function DeclRef({ d }: { d: { origin: string; file: string | null; line: number | null; byte_length: number | null; picture?: string | null } | null | undefined }) {
  if (!d) return <span className="xf-decl missing">no declaration found</span>;
  const where = [d.file, d.line != null ? `L${d.line}` : null]
    .filter(Boolean)
    .join(":");
  const size = d.byte_length != null ? `${d.byte_length} B` : "size unknown";
  return (
    <span className="xf-decl">
      {d.origin === "parsed" ? "parser-backed" : "scanned"} decl {where} · {size}
    </span>
  );
}

function PositionRow({ p }: { p: CrossFilePosition }) {
  const arg = p.caller;
  const prm = p.receiver;
  const passing = arg ? arg.passing + (arg.passing_explicit ? "" : " (default)") : null;
  return (
    <div className={`xf-pos ${p.status}`}>
      <span className="xf-pos-n">#{p.position}</span>
      {arg ? (
        <span className="xf-pos-item">
          <span className="xf-arg">{arg.name}</span>
          <span className="diag-loc">L{arg.line}</span>
          <span className="xf-passing">{passing}</span>
        </span>
      ) : (
        <span className="xf-pos-item xf-void">no argument</span>
      )}
      <span className="xf-arrow">→</span>
      {prm ? (
        <span className="xf-pos-item">
          <span className="xf-arg">{prm.name}</span>
          <span className="diag-loc">L{prm.line}</span>
        </span>
      ) : (
        <span className="xf-pos-item xf-void">no receiving parameter</span>
      )}
      {p.status === "established" && (
        <>
          <DeclRef d={p.caller_decl} />
          <DeclRef d={p.receiver_decl} />
          {p.size_status === "mismatch" && (
            <span className="xf-size mismatch">
              {p.size_caller} B ≠ {p.size_receiver} B by reference
            </span>
          )}
          {p.size_status === "equal" && (
            <span className="xf-size equal">
              {p.size_caller} B = {p.size_receiver} B
            </span>
          )}
          {p.size_status === "unknown" && (
            <span className="xf-size unknown">sizes not established</span>
          )}
        </>
      )}
    </div>
  );
}

function MappingCard({ m, onSelect }: { m: CrossFileMapping; onSelect: (id: string) => void }) {
  return (
    <div className={`xf-card ${m.status}`}>
      <div className="xf-card-top">
        <span className={`xf-status ${m.status}`}>{m.status}</span>
        <span className="xf-card-call">
          CALL {m.target} · L{m.line}
        </span>
        {m.to ? (
          <button className="ref-decl" onClick={() => onSelect(m.to as string)}>
            {m.to}
          </button>
        ) : (
          <span className="xf-target unknown">{m.reason ?? "target unresolved"}</span>
        )}
        <span className="pj-rel-ev">{m.text}</span>
      </div>
      {m.positions.map((p) => (
        <PositionRow key={p.position} p={p} />
      ))}
    </div>
  );
}

  const sel: ProjectFile | null =
    env && selected ? env.files.find((f) => f.file_id === selected) ?? null : null;
  const selImpact = env && selected ? env.impact?.[selected] : undefined;
  const selPerFile = env && selected ? env.per_file[selected] : undefined;
  const xf = env?.cross_file;
  const selInterface = xf && selected ? xf.interfaces[selected] : undefined;
  const outMappings = useMemo(
    () => (xf && selected ? xf.mappings.filter((m) => m.from === selected) : []),
    [xf, selected],
  );
  const inMappings = useMemo(
    () => (xf && selected ? xf.mappings.filter((m) => m.to === selected) : []),
    [xf, selected],
  );

  return (
    <main className="pj-pane" aria-label="Project workspace">
      <div className="pj-toolbar">
        <button className="btn" onClick={() => void loadExample()} disabled={busy}>
          Load example project
        </button>
        <button className="btn" onClick={() => dirInputRef.current?.click()} disabled={busy}>
          Upload directory…
        </button>
        <input
          ref={dirInputRef}
          type="file"
          multiple
          // @ts-expect-error non-standard directory picker attributes
          webkitdirectory=""
          directory=""
          style={{ display: "none" }}
          onChange={(e) => {
            if (e.target.files) uploadDir(e.target.files);
            e.target.value = "";
          }}
          aria-hidden="true"
          tabIndex={-1}
        />
        {env && (
          <span className="pj-summary">
            {env.project.name} · {env.files.length} files ·{" "}
            {env.coverage.dependencies_resolved as number} resolved ·{" "}
            {env.coverage.dependencies_unresolved as number} unresolved ·{" "}
            {env.coverage.dependencies_ambiguous as number} ambiguous ·{" "}
            {env.coverage.cycles as number} cycle(s)
          </span>
        )}
        <span className="header-spacer" />
        {env && (
          <span className={`status-pill ${env.summary.ok ? "ok" : "errors"}`}>
            <span className="dot" aria-hidden="true" />
            {env.summary.ok
              ? "no project violations"
              : `${env.summary.errors} violation${env.summary.errors === 1 ? "" : "s"}`}
          </span>
        )}
      </div>

      {error && <div className="system-notice">Project analysis failed — {error}</div>}

      {!env && !busy && (
        <div className="editor-empty">
          <div className="card">
            <h2>Analyze a whole COBOL project</h2>
            <p>
              Point NecroSpec at a directory of <code>.cbl</code>/<code>.cob</code>{" "}
              programs and <code>.cpy</code> copybooks. It discovers COPY and
              CALL relationships from the source, resolves them against the
              project, flags missing, ambiguous and dynamic references, and
              shows impact per file — every relationship with its evidence.
              COPY and CALL are outside the frozen single-file grammar, so
              files containing them are reported as rejected for full
              analysis while their dependencies are still mapped.
            </p>
            <div className="actions">
              <button className="btn btn-primary" onClick={() => void loadExample()}>
                Load example project
              </button>
              <button className="btn" onClick={() => dirInputRef.current?.click()}>
                Upload directory…
              </button>
            </div>
          </div>
        </div>
      )}

      {busy && (
        <div className="editor-empty">
          <div className="card">
            <h2>Analyzing project…</h2>
          </div>
        </div>
      )}

      {env && !busy && (
        <div className="pj-body">
          <div className="pj-files" role="list" aria-label="Project files">
            {env.files.map((f) => {
              const st = env.per_file[f.file_id]?.status ?? "?";
              return (
                <button
                  key={f.file_id}
                  role="listitem"
                  className={`sample-item ${selected === f.file_id ? "active" : ""}`}
                  onClick={() => setSelected(f.file_id)}
                  title={f.file_id}
                >
                  <span className="name">
                    {f.file_id}
                    <StatusChip status={st} />
                  </span>
                  <span className="desc">
                    {f.kind} · {f.bytes} B · {f.lines} lines
                  </span>
                </button>
              );
            })}
            {env.skipped.length > 0 && (
              <div className="rail-group-label">
                SKIPPED <span className="badge">{env.skipped.length}</span>
              </div>
            )}
            {env.skipped.map((s) => (
              <div key={s.path} className="sample-item" style={{ cursor: "default" }}>
                <span className="name">{s.path}</span>
                <span className="desc">{s.reason}</span>
              </div>
            ))}
          </div>

          <div className="pj-detail">
            {sel && (
              <div className="ov-section">
                <h3>
                  {sel.file_id}
                  <StatusChip status={selPerFile?.status ?? "?"} />
                  {selPerFile && (
                    <button
                      className="btn"
                      style={{ marginLeft: "var(--sp-2)", padding: "2px 8px", fontSize: "var(--fs-2xs)" }}
                      onClick={() =>
                        props.onOpenSource(
                          sel.path,
                          props.sourcesRef?.[sel.file_id] ?? "",
                        )
                      }
                      title="Open this file in the single-file workspace"
                    >
                      open in editor
                    </button>
                  )}
                </h3>
                {selPerFile?.reason && (
                  <p className="ov-note">{selPerFile.reason}</p>
                )}
                {selImpact && (
                  <>
                    <dl className="ov-kv" style={{ marginTop: "var(--sp-2)" }}>
                      <dt>Direct dependencies</dt>
                      <dd>{selImpact.direct_dependencies.length}</dd>
                      <dt>Direct dependants</dt>
                      <dd>{selImpact.direct_dependants.length}</dd>
                      <dt>Transitive dependants</dt>
                      <dd>{selImpact.transitive_dependants.length}</dd>
                    </dl>
                    <div className="pj-rel">
                      {selImpact.direct_dependencies.map((d, i) => (
                        <div key={i} className="pj-rel-row">
                          <span className="pj-rel-kind">{d.kind} →</span>
                          <button className="ref-decl" onClick={() => setSelected(d.to)}>
                            {d.to}
                          </button>
                          <span className="diag-loc">L{d.line}</span>
                          <span className="pj-rel-ev">{d.evidence}</span>
                        </div>
                      ))}
                      {selImpact.direct_dependants.map((d, i) => (
                        <div key={`d${i}`} className="pj-rel-row">
                          <span className="pj-rel-kind">← {d.kind}</span>
                          <button className="ref-decl" onClick={() => setSelected(d.from)}>
                            {d.from}
                          </button>
                          <span className="diag-loc">L{d.line}</span>
                          <span className="pj-rel-ev">{d.evidence}</span>
                        </div>
                      ))}
                      {selImpact.transitive_dependencies.length > 0 && (
                        <div className="pj-rel-row">
                          <span className="pj-rel-kind">transitive dependencies</span>
                          <span className="pj-rel-ev">
                            {selImpact.transitive_dependencies.join(", ")}
                          </span>
                        </div>
                      )}
                      {selImpact.transitive_dependants.length > 0 && (
                        <div className="pj-rel-row">
                          <span className="pj-rel-kind">transitive dependants</span>
                          <span className="pj-rel-ev">
                            {selImpact.transitive_dependants.join(", ")}
                          </span>
                        </div>
                      )}
                      {selImpact.unresolved_relationships.map((u, i) => (
                        <div key={`u${i}`} className="pj-rel-row unresolved">
                          <span className="pj-rel-kind">
                            {u.kind} ({RES_LABEL[u.resolution] ?? u.resolution})
                          </span>
                          <span className="pj-rel-ev">
                            {u.from}:{u.line} → {u.target} · {u.evidence}
                          </span>
                        </div>
                      ))}
                      {(selImpact.data_flow?.sends_data_to ?? []).map((r, i) => (
                        <div key={`sf${i}`} className="pj-rel-row">
                          <span className="pj-rel-kind data">data →</span>
                          <button className="ref-decl" onClick={() => setSelected(r.with)}>
                            {r.with}
                          </button>
                          <span className="diag-loc">L{r.line}</span>
                          <span className="pj-rel-ev">{r.evidence}</span>
                          <span className={`xf-status ${r.status}`}>{r.status}</span>
                        </div>
                      ))}
                      {(selImpact.data_flow?.receives_data_from ?? []).map((r, i) => (
                        <div key={`rf${i}`} className="pj-rel-row">
                          <span className="pj-rel-kind data">← data</span>
                          <button className="ref-decl" onClick={() => setSelected(r.with)}>
                            {r.with}
                          </button>
                          <span className="diag-loc">L{r.line}</span>
                          <span className="pj-rel-ev">{r.evidence}</span>
                          <span className={`xf-status ${r.status}`}>{r.status}</span>
                        </div>
                      ))}
                      {(selImpact.data_flow?.unresolved_data_relationships ?? []).map((r, i) => (
                        <div key={`ud${i}`} className="pj-rel-row unresolved">
                          <span className="pj-rel-kind data">↔ data (unresolved)</span>
                          <span className="pj-rel-ev">
                            {r.target} · L{r.line} · {r.evidence}
                          </span>
                        </div>
                      ))}
                    </div>
                    <p className="ov-note">{selImpact.note}</p>
                  </>
                )}
              </div>
            )}

            {xf && selected && (selInterface || outMappings.length > 0 || inMappings.length > 0) && (
              <div className="ov-section">
                <h3>CROSS-FILE DATA</h3>
                {selInterface && selInterface.params.length > 0 && (
                  <div className="xf-card established">
                    <div className="xf-card-top">
                      <span className={`xf-status interface ${selInterface.origin}`}>
                        receives · {selInterface.origin}
                      </span>
                    </div>
                    {selInterface.params.map((p, i) => (
                      <div className="xf-pos" key={i}>
                        <span className="xf-pos-n">param</span>
                        <span className="xf-pos-item">
                          <span className="xf-arg">{p.name}</span>
                          {p.line != null && <span className="diag-loc">L{p.line}</span>}
                        </span>
                        <DeclRef d={p.declaration} />
                      </div>
                    ))}
                  </div>
                )}
                {selInterface && selInterface.copybooks.length > 0 && (
                  <div className="xf-copybooks">
                    {selInterface.copybooks.map((c, i) => (
                      <span className="xf-copybook" key={i}>
                        COPY {c.copybook} ({c.via}
                        {c.via === "nested" ? `: ${c.chain.join(" → ")}` : ""})
                      </span>
                    ))}
                  </div>
                )}
                {outMappings.map((m, i) => (
                  <MappingCard key={`o${i}`} m={m} onSelect={setSelected} />
                ))}
                {inMappings.length > 0 && (
                  <p className="ov-note">
                    Receives data in {inMappings.length} mapping(s):
                  </p>
                )}
                {inMappings.map((m, i) => (
                  <MappingCard key={`i${i}`} m={m} onSelect={setSelected} />
                ))}
                <p className="ov-note">
                  Arguments correspond to receiving parameters by position
                  only; identifiers are never used to infer correspondence.
                  Established rows have declarations on both sides; anything
                  else is left visibly incomplete.
                </p>
              </div>
            )}

            <div className="ov-section">
              <h3>PROJECT FINDINGS</h3>
              {env.findings.length === 0 && (
                <p className="ov-note">No project-level findings.</p>
              )}
              {env.findings.map((d) => (
                <div key={d.finding_id} className={`diag-row sev-${d.severity}`}>
                  <span className="diag-top">
                    <span className={`sev-chip ${d.severity}`}>
                      {d.severity.toUpperCase()}
                    </span>
                    <span className="diag-code">{d.code}</span>
                    <span className="diag-loc">
                      {(d.detail?.file ?? "project") + (d.line ? `:${d.line}` : "")}
                    </span>
                  </span>
                  <span className="diag-msg">{d.message}</span>
                  {d.evidence && <span className="diag-evidence">{d.evidence}</span>}
                  {d.hint && (
                    <span className="diag-hint">
                      <span className="hint-label">Suggested investigation: </span>
                      {d.hint}
                    </span>
                  )}
                </div>
              ))}
            </div>

            <div className="ov-section">
              <h3>DEPENDENCY GRAPH</h3>
              <DepGraph env={env} selected={selected} onSelect={setSelected} />
              <p className="ov-note">
                Solid edges are resolved; dashed edges are missing, ambiguous,
                dynamic or unresolved — each listed with its evidence above.
              </p>
            </div>

            <div className="ov-section">
              <h3>COVERAGE &amp; MODEL LIMITS</h3>
              <dl className="ov-kv">
                <dt>Files analyzed</dt>
                <dd>
                  {env.coverage.files_analyzed as number} of{" "}
                  {env.coverage.files_indexed as number} indexed
                </dd>
                {env.cross_file && (
                  <>
                    <dt>CALL USING mappings</dt>
                    <dd>
                      {env.cross_file.coverage.mappings_established}{" "}
                      established ·{" "}
                      {env.cross_file.coverage.mappings_incomplete}{" "}
                      incomplete ·{" "}
                      {env.cross_file.coverage.mappings_unresolved}{" "}
                      unresolved
                    </dd>
                  </>
                )}
                <dt>Dependencies</dt>
                <dd>
                  {env.coverage.dependencies_total as number} total ·{" "}
                  {env.coverage.dependencies_resolved as number} resolved
                </dd>
              </dl>
              <ul className="pj-assumptions">
                {env.assumptions.map((a) => (
                  <li key={a.id}>
                    <strong>{a.topic}:</strong> {a.detail}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
