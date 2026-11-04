import { useEffect, useMemo, useRef, useState } from "react";
import {
  ProjectEnvelope,
  ProjectFile,
  CrossFileMapping,
  CrossFilePosition,
  LogicalModel,
  DataflowProgram,
  CrossProgramLink,
  FlowOperand,
  DecisionRecord,
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

function operandLabel(o: FlowOperand): string {
  if (o.kind === "literal" || o.kind === "figurative") return o.text ?? "?";
  return o.name ?? "?";
}

function OperandChip({ o }: { o: FlowOperand }) {
  const decl = o.decl;
  const uncertain = o.resolution && o.resolution !== "resolved";
  return (
    <span
      className={`df-operand ${uncertain ? "uncertain" : ""}`}
      title={
        decl
          ? `${decl.source_file}:L${decl.line} (${decl.origin} origin)` +
            (decl.via_copybooks && decl.via_copybooks.length
              ? ` via ${decl.via_copybooks.join(" > ")}`
              : "")
          : o.resolution ?? ""
      }
    >
      {operandLabel(o)}
      {decl?.origin === "copybook" && <span className="df-cb"> ⌘</span>}
      {uncertain && <span className="df-unres"> ({o.resolution})</span>}
    </span>
  );
}

function OpRow({ o, conds }: { o: DataflowProgram["operations"][number]; conds: DataflowProgram["conditions"] }) {
  return (
    <div className={`df-op ${o.status}`}>
      <span className="df-op-head">
        <span className="xf-status interface parsed">{o.type}</span>
        <span className="diag-loc">L{o.line}</span>
        <span className={`xf-status ${o.status}`}>{o.status}</span>
        {o.options.rounded && <span className="df-opt">ROUNDED</span>}
        {o.options.size_error && <span className="df-opt">ON SIZE ERROR</span>}
        {o.options.remainder && (
          <span className="df-opt">REMAINDER {o.options.remainder}</span>
        )}
        {o.options.mode && <span className="df-opt">{o.options.mode}</span>}
        {o.guards.map((g, i) => (
          <span className="df-guard" key={i} title="guarding condition">
            IF L{g.line} ({g.branch})
          </span>
        ))}
      </span>
      <span className="df-op-body">
        {o.receivers.length > 0 && (
          <>
            <span className="df-arrow">→ writes </span>
            {o.receivers.map((t, i) => (
              <OperandChip key={i} o={t} />
            ))}
          </>
        )}
        {o.source_operands.length > 0 && (
          <>
            <span className="df-arrow"> ← from </span>
            {o.source_operands.map((x, i) => (
              <OperandChip key={i} o={x} />
            ))}
          </>
        )}
        {o.expression && !o.expression.supported && (
          <span className="lg-reason"> expression not established</span>
        )}
      </span>
      <span className="pj-rel-ev">{o.evidence}</span>
      {o.guards.length > 0 && (
        <span className="df-cond-src">
          {o.guards.map((g) => {
            const c = conds.find((x) => x.cond_id === g.cond_id);
            return c ? `condition L${c.line}: ${c.evidence}` : null;
          })}
        </span>
      )}
    </div>
  );
}

function FieldFlow({ flow, logical, declId, links, onSelect }: {
  flow: DataflowProgram;
  logical?: LogicalModel;
  declId: string;
  links: CrossProgramLink[];
  onSelect: (id: string) => void;
}) {
  const graph = flow.graph;
  const did = "d:" + declId;
  const decl = logical?.declarations.find((d) => d.decl_id === declId);
  const producerEdges = graph.edges.filter(
    (e) => e.kind === "receiver" && e.to === did,
  );
  const consumerEdges = graph.edges.filter(
    (e) => e.kind === "operand" && e.from === did,
  );
  const condEdges = graph.edges.filter(
    (e) => e.kind === "condition" && e.from === did,
  );
  const nodeLabel = (id: string) =>
    graph.nodes.find((n) => n.id === id)?.label ?? id;
  return (
    <div className="df-field">
      <p className="ov-note">
        data flow for <span className="lg-name">{decl?.name ?? declId}</span>
        {decl && (
          <>
            {" "}— declared in {decl.source_file}:L{decl.line} (
            {decl.origin} origin
            {decl.via_copybooks.length > 0 &&
              `, via ${decl.via_copybooks.join(" > ")}`}
            )
          </>
        )}
      </p>
      <div className="df-field-block">
        <span className="df-block-title">receives value from</span>
        {producerEdges.length === 0 && (
          <span className="xf-void">no supported operation writes it</span>
        )}
        {producerEdges.map((e, i) => {
          const contribs = graph.edges.filter(
            (x) => x.kind === "operand" && x.to === e.from,
          );
          const guards = graph.edges.filter(
            (x) => x.kind === "guard" && x.to === e.from,
          );
          return (
            <div className="lg-ref-row" key={i}>
              <span className="lg-name">
                {nodeLabel(e.from)} L{e.line}
              </span>
              <span className="xf-pos-item">
                ← {contribs.map((c) => nodeLabel(c.from)).join(", ") ||
                  "literal / unknown"}
              </span>
              {e.rounded && <span className="df-opt">ROUNDED</span>}
              {guards.map((g, gi) => (
                <span className="df-guard" key={gi}>
                  IF L{graph.nodes.find((n) => n.id === g.from)?.line} (
                  {g.role})
                </span>
              ))}
              <span className="pj-rel-ev">{e.evidence}</span>
            </div>
          );
        })}
      </div>
      <div className="df-field-block">
        <span className="df-block-title">used by</span>
        {consumerEdges.length === 0 && (
          <span className="xf-void">no supported operation reads it</span>
        )}
        {consumerEdges.map((e, i) => (
          <div className="lg-ref-row" key={i}>
            <span className="lg-name">
              {nodeLabel(e.to)} L{e.line}
            </span>
            <span className="xf-pos-item">as {e.role}</span>
            <span className="pj-rel-ev">{e.evidence}</span>
          </div>
        ))}
      </div>
      {condEdges.length > 0 && (
        <div className="df-field-block">
          <span className="df-block-title">controls conditions</span>
          {condEdges.map((e, i) => (
            <div className="lg-ref-row" key={i}>
              <span className="lg-name">IF L{e.line}</span>
              <span className="pj-rel-ev">{e.evidence}</span>
            </div>
          ))}
        </div>
      )}
      {links.filter((l) => l.from_decl === declId || l.to_decl === declId)
        .length > 0 && (
        <div className="df-field-block">
          <span className="df-block-title">
            crosses a program boundary (CALL USING)
          </span>
          {links
            .filter((l) => l.from_decl === declId || l.to_decl === declId)
            .map((l, i) => (
              <div className="lg-ref-row" key={i}>
                {l.from_decl === declId ? (
                  <>
                    <span className="lg-name">passed to</span>
                    <button
                      className="ref-decl"
                      onClick={() => onSelect(l.callee)}
                    >
                      {l.callee}
                    </button>
                    <span className="xf-pos-item">
                      as argument for parameter {l.parameter} (call L
                      {l.call.line})
                    </span>
                  </>
                ) : (
                  <>
                    <span className="lg-name">received from</span>
                    <button
                      className="ref-decl"
                      onClick={() => onSelect(l.caller)}
                    >
                      {l.caller}
                    </button>
                    <span className="xf-pos-item">
                      as parameter {l.parameter} for argument {l.argument}{" "}
                      (call L{l.call.line})
                    </span>
                  </>
                )}
                <span className={`xf-status ${l.status}`}>
                  {l.status === "established" ? "established" : l.reason}
                </span>
              </div>
            ))}
        </div>
      )}
      <p className="ov-note">
        Static source structure only — not proof of runtime execution.
      </p>
    </div>
  );
}

function DataFlowView({ flow, links, program, onSelect }: {
  flow: DataflowProgram;
  links: CrossProgramLink[];
  program: string;
  onSelect: (id: string) => void;
}) {
  const here = links.filter(
    (l) => l.caller === program || l.callee === program,
  );
  return (
    <>
      {flow.operations.map((o) => (
        <OpRow key={o.op_id} o={o} conds={flow.conditions} />
      ))}
      {flow.operations.length === 0 && (
        <p className="ov-note">No supported operations recognised.</p>
      )}
      {flow.unsupported_statements.length > 0 && (
        <div className="lg-unsup">
          {flow.unsupported_statements.map((u, i) => (
            <div className="lg-ref-row" key={i}>
              <span className="lg-name">{u.structure}</span>
              <span className="lg-reason">
                {u.file}:L{u.line} — {u.reason}
              </span>
            </div>
          ))}
        </div>
      )}
      {here.length > 0 && (
        <div className="df-field-block">
          <span className="df-block-title">
            cross-program data flow (CALL USING)
          </span>
          {here.map((l, i) => (
            <div className="lg-ref-row" key={i}>
              {l.caller === program ? (
                <>
                  <span className="lg-name">sends {l.argument}</span>
                  <button className="ref-decl" onClick={() => onSelect(l.callee)}>
                    {l.callee}
                  </button>
                  <span className="xf-pos-item">
                    → param {l.parameter} (L{l.call.line})
                  </span>
                </>
              ) : (
                <>
                  <span className="lg-name">receives {l.parameter}</span>
                  <button className="ref-decl" onClick={() => onSelect(l.caller)}>
                    {l.caller}
                  </button>
                  <span className="xf-pos-item">
                    ← arg {l.argument} (L{l.call.line})
                  </span>
                </>
              )}
              {l.status === "established" ? (
                <>
                  {l.caller_writes.length > 0 && (
                    <span className="xf-size equal">
                      written at L{l.caller_writes[0]?.line}
                    </span>
                  )}
                  {l.callee_reads.length > 0 && (
                    <span className="xf-size equal">
                      read at L{l.callee_reads[0]?.line}
                    </span>
                  )}
                  {l.callee_reads.length === 0 && (
                    <span className="xf-size unknown">
                      no supported operation reads this parameter in the
                      callee
                    </span>
                  )}
                  {l.caller_writes.length === 0 &&
                    l.callee_reads.length === 0 && (
                      <span className="xf-size unknown">
                        no supported operation on either side
                      </span>
                    )}
                </>
              ) : (
                <span className="lg-reason">{l.reason}</span>
              )}
            </div>
          ))}
        </div>
      )}
      <p className="ov-note">
        Operations are recorded with evidence; unknown operands, unsupported
        constructs and dynamic call boundaries stop the trace and say so.
      </p>
    </>
  );
}

// ---- decision paths (Milestone 7) -----------------------------------------

function DecisionCard({ d, flow, selDecision, onSelect }: {
  d: DecisionRecord;
  flow: DataflowProgram;
  selDecision: string | null;
  onSelect: (id: string | null) => void;
}) {
  const cond = flow.conditions.find((c) => c.cond_id === d.condition_id);
  const condText = cond
    ? `${operandLabel(cond.left)} ${cond.op ?? "?"} ${operandLabel(cond.right)}`
    : d.summary.condition;
  const children = (d.nested_decisions ?? [])
    .map((id) => flow.decisions?.find((x) => x.decision_id === id))
    .filter((x): x is DecisionRecord => !!x);
  const open = selDecision === d.decision_id;
  const opById = (id: string) =>
    flow.operations.find((o) => o.op_id === id);
  return (
    <div className={`dec-card ${open ? "open" : ""}`}>
      <button
        className="dec-head"
        onClick={() => onSelect(open ? null : d.decision_id)}
        title={open ? "Collapse decision detail" : "Inspect this decision"}
      >
        <span className="xf-status interface parsed">IF</span>
        <span className="diag-loc">L{d.line}</span>
        <span className="dec-cond">{condText ?? "condition not established"}</span>
        {d.has_else ? (
          <span className="df-opt">ELSE</span>
        ) : (
          <span className="dec-noelse">no ELSE in source</span>
        )}
        <span className={`xf-status interface ${d.origin}`}>{d.origin}</span>
      </button>
      {open && (
        <div className="dec-body">
          <div className="dec-row">
            <span className="df-block-title">condition evaluated</span>
            {cond ? (
              <>
                <span className="dec-operands">
                  <OperandChip o={cond.left} /> {cond.op}{" "}
                  <OperandChip o={cond.right} />
                </span>
                <span className="df-cond-src">{cond.evidence}</span>
              </>
            ) : (
              <span className="lg-reason">condition record unavailable</span>
            )}
          </div>
          <div className="dec-row">
            <span className="df-block-title">
              THEN — {d.then_ops.length} operation{d.then_ops.length === 1 ? "" : "s"}
            </span>
            {d.then_ops.map((id) => {
              const o = opById(id);
              return o ? <OpRow key={id} o={o} conds={flow.conditions} /> : (
                <span key={id} className="lg-reason">operation record unavailable</span>
              );
            })}
            {d.then_ops.length === 0 && (
              <span className="ov-note">no supported operation in this branch</span>
            )}
          </div>
          <div className="dec-row">
            <span className="df-block-title">ELSE</span>
            {d.has_else ? (
              d.else_ops.length > 0 ? (
                d.else_ops.map((id) => {
                  const o = opById(id);
                  return o ? <OpRow key={id} o={o} conds={flow.conditions} /> : (
                    <span key={id} className="lg-reason">operation record unavailable</span>
                  );
                })
              ) : (
                <span className="ov-note">
                  ELSE present in source; no supported operation recorded in it
                </span>
              )
            ) : (
              <span className="dec-noelse">
                no ELSE in source — none invented
              </span>
            )}
          </div>
          {children.length > 0 && (
            <div className="dec-row">
              <span className="df-block-title">
                nested decisions — {children.length}
              </span>
              <div className="dec-nested">
                {children.map((c) => (
                  <DecisionCard key={c.decision_id} d={c} flow={flow}
                                selDecision={selDecision} onSelect={onSelect} />
                ))}
              </div>
            </div>
          )}
          <div className="dec-row">
            <span className="df-block-title">after the decision</span>
            <span className="xf-pos-item">
              {d.summary.after ??
                "no supported operation follows the decision"}
            </span>
            {d.convergence && (
              <span className="pj-rel-ev">{d.convergence.evidence}</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function DecisionPathsView({ flow, selDecision, onSelect }: {
  flow: DataflowProgram;
  selDecision: string | null;
  onSelect: (id: string | null) => void;
}) {
  const decisions = flow.decisions ?? [];
  const roots = decisions.filter((d) => !d.parent_decision);
  const cov = flow.coverage;
  const boundaries = flow.unsupported_statements.filter((u) =>
    /IF|EVALUATE|transfer/i.test(u.structure));
  return (
    <>
      {decisions.length > 0 && (
        <p className="ov-note">
          {cov.decisions_total ?? decisions.length} decision(s) ·{" "}
          {cov.decisions_with_else ?? 0} with ELSE ·{" "}
          {cov.nested_decisions ?? 0} nested — click a decision to inspect
          its branches and convergence.
        </p>
      )}
      {decisions.length === 0 && (
        <p className="ov-note">
          No decision structure established for this program.
        </p>
      )}
      <div className="dec-list">
        {roots.map((d) => (
          <DecisionCard key={d.decision_id} d={d} flow={flow}
                        selDecision={selDecision} onSelect={onSelect} />
        ))}
      </div>
      {boundaries.length > 0 && (
        <div className="lg-unsup">
          <span className="df-block-title">
            decision boundaries not established
          </span>
          {boundaries.map((u, i) => (
            <div className="lg-ref-row" key={i}>
              <span className="lg-name">{u.structure}</span>
              <span className="lg-reason">
                {u.file}:L{u.line} — {u.reason}
              </span>
            </div>
          ))}
        </div>
      )}
      <p className="ov-note">
        Branch membership, nesting and convergence come from source evidence
        only; ELSE is never assumed, and unsupported constructs stop the path
        and say so.
      </p>
    </>
  );
}

function DeclTree({ m, onSelect, onSelectDecl }: { m: LogicalModel; onSelect: (id: string) => void; onSelectDecl: (declId: string) => void }) {
  const rows = [...m.declarations].sort((a, b) => {
    const da = a.source_file.localeCompare(b.source_file);
    return da !== 0 ? da : (a.line ?? 0) - (b.line ?? 0);
  });
  return (
    <div className="lg-tree">
      {rows.map((d) => {
        const depth = d.ancestor_groups.length;
        const fileShown = d.source_file;
        return (
          <div className="lg-row" key={d.decl_id}
               style={{ paddingLeft: `calc(var(--sp-3) * ${depth})` }}>
            <span className="lg-level">{d.level}</span>
            <button
              className="lg-name lg-name-btn"
              onClick={() => onSelectDecl(d.decl_id)}
              title="Inspect data flow for this item"
            >
              {d.name}
            </button>
            {d.picture && <span className="lg-pic">PIC {d.picture}</span>}
            {d.usage === "comp3" && <span className="lg-pic">COMP-3</span>}
            {d.usage && d.usage.startsWith("unsupported:") && (
              <span className="lg-pic">{d.usage.split(":")[1]}</span>
            )}
            {d.byte_length != null && (
              <span className="lg-size">{d.byte_length} B</span>
            )}
            <span className={`lg-status ${d.status}`}>
              {d.status}
            </span>
            <button
              className={`lg-origin ${d.origin}`}
              onClick={() => onSelect(fileShown)}
              title={`Open ${fileShown}`}
            >
              {d.origin === "copybook" ? "copybook" : "program"}
              {" "}
              {fileShown}{d.line != null ? `:L${d.line}` : ""}
            </button>
            {d.via_copybooks.length > 1 && (
              <span className="lg-via">
                via {d.via_copybooks.join(" > ")}
              </span>
            )}
            {d.unsupported_reason && (
              <span className="lg-reason" title={d.unsupported_reason}>
                {d.unsupported_reason}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

function EffectiveData({ m, onSelect, onSelectDecl }: { m: LogicalModel; onSelect: (id: string) => void; onSelectDecl: (declId: string) => void }) {
  const counts = { resolved: 0, ambiguous: 0, unresolved: 0 };
  for (const r of m.references) {
    if (r.status in counts) counts[r.status as keyof typeof counts] += 1;
  }
  return (
    <>
      {m.associations.length > 0 && (
        <div className="xf-copybooks">
          {m.associations.map((a, i) => (
            <span className="xf-copybook" key={i}>
              COPY {a.copybook} ({a.via}
              {a.via === "nested" ? `: ${a.chain.join(" > ")}` : ""})
            </span>
          ))}
        </div>
      )}
      <DeclTree m={m} onSelect={onSelect} onSelectDecl={onSelectDecl} />
      {m.references.length > 0 && (
        <div className="lg-refs">
          <span className="ov-note">
            references: {counts.resolved} resolved · {counts.ambiguous}{" "}
            ambiguous · {counts.unresolved} unresolved
          </span>
          {m.references.filter((r) => r.status === "ambiguous").map((r, i) => (
            <div className="lg-ref-row" key={i}>
              <span className="lg-name">{r.name}</span>
              <span className="lg-reason">
                ambiguous
                {r.qualified_by ? ` under ${r.qualified_by}` : ""} —
                candidates: {(r.candidates ?? [])
                  .map((c) => `${c.source_file}:L${c.line} (${c.origin})`)
                  .join("; ")}
              </span>
            </div>
          ))}
        </div>
      )}
      {(m.unsupported_structures.length > 0 ||
        m.unsupported_statements.length > 0) && (
        <div className="lg-unsup">
          {[...m.unsupported_structures, ...m.unsupported_statements].map(
            (u, i) => (
              <div className="lg-ref-row" key={i}>
                <span className="lg-name">{u.structure}</span>
                <span className="lg-reason">
                  {u.file}{u.line != null ? `:L${u.line}` : ""} — {u.reason}
                </span>
              </div>
            ),
          )}
        </div>
      )}
    </>
  );
}

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
  const selLogical: LogicalModel | undefined =
    xf && selected ? xf.logical?.[selected] : undefined;
  const selFlow = xf?.dataflow && selected
    ? xf.dataflow.programs[selected]
    : undefined;
  const [flowDecl, setFlowDecl] = useState<string | null>(null);
  // declaration ids are program-scoped: switching programs invalidates
  // any selected field flow (stale ids must never render against
  // another program's model)
  useEffect(() => {
    setFlowDecl(null);
  }, [selected]);
  const [selDecision, setSelDecision] = useState<string | null>(null);
  // decision ids are program-scoped too: reset on program switch
  useEffect(() => {
    setSelDecision(null);
  }, [selected]);
  const xfCov = env?.cross_file?.coverage;
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

            {selLogical && selLogical.declarations.length > 0 && (
              <div className="ov-section">
                <h3>EFFECTIVE DATA (LOGICAL MODEL)</h3>
                <EffectiveData
                  m={selLogical}
                  onSelect={setSelected}
                  onSelectDecl={setFlowDecl}
                />
                <p className="ov-note">
                  Effective declarations combine this program&apos;s own
                  source with established COPY associations; every row keeps
                  its original file and line. Unsupported structures are
                  recorded, never silently sized or omitted.
                </p>
              </div>
            )}

            {selFlow && (selFlow.operations.length > 0 ||
              selFlow.unsupported_statements.length > 0 ||
              (xf?.dataflow?.cross_program_links ?? []).some(
                (l) => l.caller === selected || l.callee === selected,
              )) && (
              <div className="ov-section">
                <h3>DATA FLOW (STATEMENTS)</h3>
                <DataFlowView
                  flow={selFlow}
                  links={xf?.dataflow?.cross_program_links ?? []}
                  program={selected ?? ""}
                  onSelect={setSelected}
                />
              </div>
            )}

            {selFlow && ((selFlow.decisions?.length ?? 0) > 0 ||
              selFlow.unsupported_statements.length > 0) && (
              <div className="ov-section">
                <h3>DECISION PATHS</h3>
                <DecisionPathsView
                  flow={selFlow}
                  selDecision={selDecision}
                  onSelect={setSelDecision}
                />
              </div>
            )}

            {selFlow && flowDecl && (
              <div className="ov-section">
                <h3>FIELD FLOW</h3>
                <FieldFlow
                  flow={selFlow}
                  logical={selLogical}
                  declId={flowDecl}
                  links={xf?.dataflow?.cross_program_links ?? []}
                  onSelect={setSelected}
                />
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
                {xfCov && xfCov.logical_programs != null && (
                  <>
                    <dt>Effective declarations</dt>
                    <dd>
                      {xfCov.logical_declarations}{" "}
                      ({xfCov.logical_copybook_origin_declarations}{" "}
                      from copybooks ·{" "}
                      {xfCov.logical_unsupported_declarations}{" "}
                      unsupported)
                    </dd>
                    <dt>Data references</dt>
                    <dd>
                      {xfCov.references_resolved}{" "}
                      resolved ·{" "}
                      {xfCov.references_ambiguous}{" "}
                      ambiguous ·{" "}
                      {xfCov.references_unresolved}{" "}
                      unresolved ·{" "}
                      {xfCov.copybook_semantic_findings}{" "}
                      copybook-origin finding(s)
                    </dd>
                  </>
                )}
                {xfCov && xfCov.operations_total != null && (
                  <>
                    <dt>Operations</dt>
                    <dd>
                      {xfCov.operations_total} recognised (
                      {xfCov.operations_established} established ·{" "}
                      {xfCov.operations_unsupported} unsupported) ·{" "}
                      {xfCov.conditions_total} condition(s) ·{" "}
                      {xfCov.cross_program_links} cross-program link(s)
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
