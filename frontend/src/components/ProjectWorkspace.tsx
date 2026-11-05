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
  RuleCandidate,
  RuleItem,
  ProjectOverview,
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

// ---- rule candidates (Milestone 8) -----------------------------------------

function ruleItemTitle(i: RuleItem): string {
  const d = i.decl;
  if (!d) return i.resolution ?? (i.text ?? "");
  return `${d.source_file}:L${d.line} (${d.origin} origin)` +
    (d.via_copybooks && d.via_copybooks.length
      ? ` via ${d.via_copybooks.join(" > ")}`
      : "");
}

function RuleItemChip({ i }: { i: RuleItem }) {
  const uncertain = i.resolution && i.resolution !== "resolved" &&
    i.resolution !== "literal";
  return (
    <span className={`df-operand ${uncertain ? "uncertain" : ""}`}
          title={ruleItemTitle(i)}>
      {i.name ?? i.text ?? "?"}
      {i.decl?.origin === "copybook" && <span className="df-cb"> ⌘</span>}
      {uncertain && <span className="df-unres"> ({i.resolution})</span>}
    </span>
  );
}

function RuleCandidateCard({ c, flow, selRule, onSelect }: {
  c: RuleCandidate;
  flow: DataflowProgram;
  selRule: string | null;
  onSelect: (id: string | null) => void;
}) {
  const open = selRule === c.rule_id;
  const opById = (id: string) =>
    flow.operations.find((o) => o.op_id === id);
  // via_item is a declaration id: name it from this candidate's own
  // written items (never invented — an unknown id stays explicit)
  const writtenNames = new Map<string, string>();
  for (const i of c.items_written) {
    if (i.decl?.decl_id && i.name) writtenNames.set(i.decl.decl_id, i.name);
  }
  return (
    <div className={`dec-card rule-card ${c.status} ${open ? "open" : ""}`}>
      <button
        className="dec-head"
        onClick={() => onSelect(open ? null : c.rule_id)}
        title={open ? "Collapse rule candidate" : "Inspect this rule candidate"}
      >
        <span className="xf-status interface parsed">RULE</span>
        <span className="diag-loc">L{c.line}</span>
        <span className="dec-cond">IF {c.condition_text}</span>
        {c.has_else ? (
          <span className="df-opt">ELSE</span>
        ) : (
          <span className="dec-noelse">no ELSE in source</span>
        )}
        <span
          className={`xf-status ${c.status === "partial" ? "partial" : "established"}`}
          title={`status: ${c.status}`}
        >
          {c.status === "partial" ? "partial" : "established structure"}
        </span>
      </button>
      {open && (
        <div className="dec-body">
          <div className="dec-row">
            <span className="df-block-title">source-derived explanation</span>
            <span className="rule-expl">{c.explanation}</span>
            <span className="df-cond-src">
              traceable to: condition L{c.trace.condition_line}
              {" · "}operations {c.trace.op_ids.length}
              {" · "}data items {c.trace.decl_ids.length}
            </span>
          </div>
          <div className="dec-row">
            <span className="df-block-title">condition evaluated</span>
            <span className="dec-operands">
              {c.condition_operands.map((i, k) => (
                <RuleItemChip key={k} i={i} />
              ))}
            </span>
            <span className="df-cond-src">{c.trace.condition_evidence}</span>
          </div>
          <div className="dec-row">
            <span className="df-block-title">
              THEN — {c.then_ops.length} operation{c.then_ops.length === 1 ? "" : "s"}
            </span>
            {c.then_ops.map((id) => {
              const o = opById(id);
              return o ? <OpRow key={id} o={o} conds={flow.conditions} /> : (
                <span key={id} className="lg-reason">operation record unavailable</span>
              );
            })}
          </div>
          <div className="dec-row">
            <span className="df-block-title">ELSE</span>
            {c.has_else ? (
              c.else_ops.length > 0 ? (
                c.else_ops.map((id) => {
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
          <div className="dec-row">
            <span className="df-block-title">data items read</span>
            <span className="dec-operands">
              {c.items_read.map((i, k) => <RuleItemChip key={k} i={i} />)}
            </span>
          </div>
          <div className="dec-row">
            <span className="df-block-title">data items written</span>
            <span className="dec-operands">
              {c.items_written.map((i, k) => <RuleItemChip key={k} i={i} />)}
            </span>
          </div>
          {c.downstream_uses.length > 0 && (
            <div className="dec-row">
              <span className="df-block-title">downstream uses</span>
              {c.downstream_uses.map((u, k) => (
                <span className="lg-ref-row" key={k}>
                  <span className="lg-name">{u.label ?? u.op_id}</span>
                  <span className="xf-pos-item">
                    via{" "}
                    {writtenNames.get(u.via_item) ?? (
                      <span className="lg-reason">item not established</span>
                    )}
                  </span>
                  <span className="xf-pos-item">L{u.line}</span>
                  <span className="pj-rel-ev">{u.evidence}</span>
                </span>
              ))}
            </div>
          )}
          {c.cross_program.length > 0 && (
            <div className="dec-row">
              <span className="df-block-title">cross-program data flow</span>
              {c.cross_program.map((x, k) => (
                <span className="lg-ref-row" key={k}>
                  <span className="lg-name">{x.argument}</span>
                  <span className="xf-pos-item">
                    → {x.callee} param {x.parameter} (CALL L{x.call_line})
                  </span>
                  {x.mapping_status !== "established" && (
                    <span className="xf-size unknown">
                      mapping {x.mapping_status}
                    </span>
                  )}
                  {x.qualification && (
                    <span className="lg-reason">{x.qualification}</span>
                  )}
                </span>
              ))}
            </div>
          )}
          {c.unresolved_elements.length > 0 && (
            <div className="dec-row">
              <span className="df-block-title">not established</span>
              {c.unresolved_elements.map((u, k) => (
                <span className="lg-ref-row" key={k}>
                  <span className="lg-name">{u.element}</span>
                  <span className="lg-reason">{u.detail} (L{u.line})</span>
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function RuleCandidatesView({ flow, selRule, onSelect }: {
  flow: DataflowProgram;
  selRule: string | null;
  onSelect: (id: string | null) => void;
}) {
  const rules = flow.rules;
  if (!rules) return null;
  const cov = rules.coverage;
  return (
    <>
      <p className="ov-note">
        {cov.candidates_total ?? 0} candidate(s) ·{" "}
        {cov.candidates_established_structure ?? 0} established structure ·{" "}
        {cov.candidates_partial ?? 0} partial — click a candidate to inspect
        its evidence. Candidates are source structure, not statements of
        business intent.
      </p>
      <div className="dec-list">
        {rules.candidates.map((c) => (
          <RuleCandidateCard key={c.rule_id} c={c} flow={flow}
                             selRule={selRule} onSelect={onSelect} />
        ))}
      </div>
      {rules.candidates.length === 0 &&
        rules.unsupported.length === 0 && (
        <p className="ov-note">
          No supported rule candidates were established for this program
          by the current analysis. This does not mean the program contains
          no business rules — it means no condition with established
          branch operations was found; see DECISION PATHS and DATA FLOW
          for what was established.
        </p>
      )}
      {rules.candidates.length === 0 &&
        rules.unsupported.length > 0 && (
        <p className="ov-note">
          No supported rule candidates were established for this program:
          its decision structures are recorded as not established below.
        </p>
      )}
      {rules.unsupported.length > 0 && (
        <div className="lg-unsup">
          <span className="df-block-title">
            rule structures not established
          </span>
          {rules.unsupported.map((u) => (
            <div className="lg-ref-row" key={u.rule_id}>
              <span className="lg-name">{u.structure}</span>
              <span className="lg-reason">
                {u.source_file}:L{u.line} — {u.reason}
              </span>
            </div>
          ))}
        </div>
      )}
      <p className="ov-note">
        Every explanation quotes recorded conditions, operations and data
        items with their source lines; unresolved operands, incomplete
        argument mappings and unsupported structures are listed, never
        interpreted.
      </p>
    </>
  );
}

// ---- project intelligence overview (Milestone 9) ----------------------------

function ProgramLink({ id, onSelect, onOpenSource, sourcesRef }: {
  id: string;
  onSelect: (id: string) => void;
  onOpenSource: (path: string, content: string) => void;
  sourcesRef?: Record<string, string>;
}) {
  return (
    <span className="ov-file-link">
      <button className="ref-decl" onClick={() => onSelect(id)} title={`Inspect ${id}`}>
        {id}
      </button>
      {sourcesRef?.[id] != null && (
        <button className="ov-source-link" onClick={() => onOpenSource(id, sourcesRef[id] ?? "")}
          title={`Open source for ${id}`}>
          open source
        </button>
      )}
    </span>
  );
}

function ProjectOverviewView({ ov, assumptions, onSelect, onOpenSource, sourcesRef }: {
  ov: ProjectOverview;
  assumptions: { id: string; topic: string; detail: string }[];
  onSelect: (id: string) => void;
  onOpenSource: (path: string, content: string) => void;
  sourcesRef?: Record<string, string>;
}) {
  const inv = ov.inventory;
  const deps = ov.dependencies;
  const data = ov.data;
  const dr = ov.decisions_rules;
  const reg = ov.register;
  const cov = ov.coverage;
  return (
    <>
      <div className="ov-section">
        <h3>PROJECT OVERVIEW</h3>
        <p className="ov-note">{ov.note}</p>
      </div>

      <div className="ov-section">
        <h3>APPLICATION INVENTORY</h3>
        <dl className="ov-kv">
          <dt>Discovered files</dt><dd>{inv.files_total}</dd>
          <dt>COBOL programs</dt><dd>{inv.programs_total}</dd>
          <dt>Copybooks</dt><dd>{inv.copybooks_total}</dd>
          <dt>Rejected (frozen-grammar parse)</dt><dd>{inv.files_rejected}</dd>
          <dt>Skipped / unreadable</dt><dd>{inv.files_skipped}</dd>
          <dt>Accepted by frozen grammar (subset)</dt><dd>{inv.programs_analyzed}</dd>
          <dt>Grammar rejected; supplemental scan ran</dt><dd>{inv.programs_partial_analysis}</dd>
          <dt>Programs with unsupported structures</dt><dd>{inv.programs_unsupported}</dd>
          <dt>Programs with statement scans</dt><dd>{inv.programs_with_dataflow}</dd>
        </dl>
        <p className="ov-note">{inv.note}</p>
      </div>

      <div className="ov-section">
        <h3>DEPENDENCIES</h3>
        <dl className="ov-kv">
          <dt>Relationships (edges)</dt><dd>{deps.total}</dd>
          <dt>Program CALLs</dt><dd>{deps.call_relationships}</dd>
          <dt>Program → copybook</dt><dd>{deps.copy_relationships}</dd>
          <dt>Resolved</dt><dd>{deps.resolved}</dd>
          <dt>Missing</dt><dd>{deps.missing}</dd>
          <dt>Ambiguous</dt><dd>{deps.ambiguous}</dd>
          <dt>Dynamic CALL targets</dt><dd>{deps.dynamic}</dd>
          <dt>Cycles</dt><dd>{deps.cycles.length}</dd>
        </dl>
        {deps.cycles.length > 0 && (
          <div className="lg-unsup">
            {deps.cycles.map((c, i) => (
              <div className="lg-ref-row" key={i}>
                <span className="lg-name">cycle</span>
                <span className="xf-pos-item">{c.join(" ⇄ ")}</span>
              </div>
            ))}
          </div>
        )}
        {deps.resolved_edges.length > 0 && (
          <div className="lg-unsup">
            <span className="df-block-title">resolved dependency evidence</span>
            {deps.resolved_edges.map((e, i) => (
              <div className="lg-ref-row" key={`${e.from}:${e.line}:${i}`}>
                <ProgramLink id={e.from} onSelect={onSelect} onOpenSource={onOpenSource} sourcesRef={sourcesRef} />
                <span className="xf-pos-item">→ {e.to ?? e.target} ({e.kind}, L{e.line})</span>
                {e.to && <ProgramLink id={e.to} onSelect={onSelect} onOpenSource={onOpenSource} sourcesRef={sourcesRef} />}
                <span className="pj-rel-ev">{e.evidence}</span>
              </div>
            ))}
          </div>
        )}
        <p className="ov-note">{deps.note}</p>
      </div>

      <div className="ov-section">
        <h3>DATA &amp; CROSS-PROGRAM FLOW</h3>
        <dl className="ov-kv">
          <dt>CALL USING mappings</dt>
          <dd>{data.mappings_total} ({data.mappings_established} established ·{" "}
            {data.mappings_incomplete} incomplete · {data.mappings_unresolved} unresolved)</dd>
          <dt>CALL rows with resolved declarations</dt>
          <dd>{data.cross_program_links_with_resolved_declarations} / {data.cross_program_links_total} (mapping status shown separately)</dd>
          <dt>Recorded operations</dt>
          <dd>{data.operations_established} / {data.operations_total}</dd>
          <dt>Conditions</dt><dd>{data.conditions_total}</dd>
          <dt>Logical declarations</dt><dd>{data.logical_declarations}</dd>
          <dt>Copybook-origin declarations</dt><dd>{data.copybook_origin_declarations}</dd>
        </dl>
        {data.dynamic_call_targets.length > 0 && (
          <div className="lg-unsup">
            {data.dynamic_call_targets.map((d, i) => (
              <div className="lg-ref-row" key={i}>
                <span className="lg-name">dynamic CALL</span>
                <ProgramLink id={d.caller} onSelect={onSelect} onOpenSource={onOpenSource} sourcesRef={sourcesRef} />
                <span className="xf-pos-item">
                  → {d.target ?? "unresolved target"} (L{d.line})
                </span>
              </div>
            ))}
          </div>
        )}
        {data.cross_program_flows.length > 0 && (
          <div className="lg-unsup">
            <span className="df-block-title">producer / consumer evidence across CALLs</span>
            {data.cross_program_flows.map((f, i) => (
              <div className="lg-ref-row" key={`${f.caller}:${f.call_line}:${i}`}>
                <ProgramLink id={f.caller} onSelect={onSelect} onOpenSource={onOpenSource} sourcesRef={sourcesRef} />
                <span className="xf-pos-item">→ {f.callee} · {f.argument ?? "argument"} → {f.parameter ?? "parameter"} (L{f.call_line})</span>
                <span className={`xf-status ${f.mapping_status ?? "unresolved"}`}>{f.mapping_status ?? "unresolved mapping"}</span>
                <span className="pj-rel-ev">{f.call_evidence}</span>
                {[...f.caller_writes.map((x) => ({ ...x, side: "producer" })),
                  ...f.callee_reads.map((x) => ({ ...x, side: "consumer" }))].map((op) => (
                  <span className="pj-rel-ev" key={`${op.side}:${op.op_id}`}>
                    {op.side} op {op.op_id} at L{op.line}: {op.evidence}
                  </span>
                ))}
              </div>
            ))}
          </div>
        )}
        {data.established_mappings.length > 0 && (
          <div className="lg-unsup">
            <span className="df-block-title">established structural mappings</span>
            {data.established_mappings.map((m, i) => (
              <div className="lg-ref-row" key={`${m.from}:${m.line}:${i}`}>
                <ProgramLink id={m.from} onSelect={onSelect} onOpenSource={onOpenSource} sourcesRef={sourcesRef} />
                <span className="xf-pos-item">→ {m.to} (L{m.line})</span>
                <span className="pj-rel-ev">{m.evidence}</span>
              </div>
            ))}
          </div>
        )}
        {reg.incomplete_mappings.length > 0 && (
          <div className="lg-unsup">
            <span className="df-block-title">incomplete / unresolved mappings</span>
            {reg.incomplete_mappings.map((m, i) => (
              <div className="lg-ref-row" key={`${m.from}:${m.line}:${i}`}>
                <ProgramLink id={m.from} onSelect={onSelect} onOpenSource={onOpenSource} sourcesRef={sourcesRef} />
                <span className="xf-pos-item">{m.status} → {m.to ?? "unknown receiver"} (L{m.line})</span>
                <span className="pj-rel-ev">{m.evidence}</span>
              </div>
            ))}
          </div>
        )}
        <p className="ov-note">{data.note}</p>
      </div>

      <div className="ov-section">
        <h3>DECISIONS &amp; RULE CANDIDATES</h3>
        <dl className="ov-kv">
          <dt>Decision structures</dt>
          <dd>{dr.decisions_total} ({dr.decisions_with_else} with ELSE · {dr.nested_decisions} nested)</dd>
          <dt>Rule candidates</dt>
          <dd>{dr.rules_total} ({dr.rules_established_structure} established structure ·{" "}
            {dr.rules_partial} partial · {dr.rules_unsupported} unsupported)</dd>
          <dt>Programs without candidates</dt><dd>{dr.programs_without_candidates.length}</dd>
        </dl>
        {dr.programs_without_candidates.length > 0 && (
          <div className="lg-unsup">
            {dr.programs_without_candidates.map((fid) => (
              <div className="lg-ref-row" key={fid}>
                <ProgramLink id={fid} onSelect={onSelect} onOpenSource={onOpenSource} sourcesRef={sourcesRef} />
                <span className="lg-reason">no supported rule candidates established</span>
              </div>
            ))}
          </div>
        )}
        {dr.candidates.length > 0 && (
          <div className="lg-unsup">
            <span className="df-block-title">rule candidate evidence</span>
            {dr.candidates.map((c) => (
              <div className="lg-ref-row" key={c.rule_id}>
                <ProgramLink id={c.program} onSelect={onSelect} onOpenSource={onOpenSource} sourcesRef={sourcesRef} />
                <span className={`rule-status ${c.status ?? "partial"}`}>{c.status ?? "status unavailable"}</span>
                <span className="xf-pos-item">{c.rule_id} · L{c.line}{c.end_line && c.end_line !== c.line ? `–${c.end_line}` : ""}</span>
                <span className="lg-reason">{c.condition_text}</span>
                <span className="pj-rel-ev">THEN ops: {c.then_ops.join(", ") || "none recorded"} · ELSE ops: {c.else_ops.join(", ") || "none recorded"}</span>
              </div>
            ))}
          </div>
        )}
        <div className="lg-unsup">
          <span className="df-block-title">per-program decision/rule counts</span>
          {dr.per_program.map((p) => (
            <div className="lg-ref-row" key={p.program}>
              <ProgramLink id={p.program} onSelect={onSelect} onOpenSource={onOpenSource} sourcesRef={sourcesRef} />
              <span className="xf-pos-item">{p.decisions} decisions · {p.candidates} candidates ({p.candidates_partial} partial) · {p.unsupported_structures} unsupported</span>
            </div>
          ))}
        </div>
        <p className="ov-note">{dr.disclaimer}</p>
      </div>

      <div className="ov-section">
        <h3>INVESTIGATION REGISTER</h3>
        <dl className="ov-kv">
          <dt>Violations</dt><dd>{reg.violations_total}</dd>
          <dt>Risks (human review)</dt><dd>{reg.risks_total}</dd>
          <dt>Notes</dt><dd>{reg.notes_total}</dd>
        </dl>
        {reg.violations.map((v) => (
          <div className="lg-ref-row" key={v.finding_id}>
            <span className="lg-name">{v.code} · {v.finding_id}</span>
            {v.file ? <ProgramLink id={v.file} onSelect={onSelect} onOpenSource={onOpenSource} sourcesRef={sourcesRef} /> : <span className="lg-reason">project-wide; no single source location</span>}
            <span className="xf-pos-item">{v.line ? `L${v.line}` : "location unavailable"}</span>
            <span className="lg-reason">{v.message}</span>
            {v.evidence && <span className="pj-rel-ev">{v.evidence}</span>}
          </div>
        ))}
        {reg.risks_by_code.map((group) => (
          <div className="lg-unsup" key={group.code}>
            <span className="df-block-title">{group.code} · {group.count} finding{group.count === 1 ? "" : "s"}</span>
            {group.findings.map((f) => (
              <div className="lg-ref-row" key={f.finding_id}>
                <span className="lg-name">{f.finding_id}</span>
                {f.file && <ProgramLink id={f.file} onSelect={onSelect} onOpenSource={onOpenSource} sourcesRef={sourcesRef} />}
                <span className="xf-pos-item">{f.line ? `L${f.line}` : "location unavailable"}{f.col ? `:${f.col}` : ""}</span>
                <span className="lg-reason">{f.message}</span>
                {f.evidence && <span className="pj-rel-ev">{f.evidence}</span>}
              </div>
            ))}
          </div>
        ))}
        {reg.unsupported_structures.length > 0 && (
          <div className="lg-unsup">
            <span className="df-block-title">unsupported constructs</span>
            {reg.unsupported_structures.map((u, i) => (
              <div className="lg-ref-row" key={i}>
                <span className="lg-name">{u.structure}</span>
                <ProgramLink id={u.file} onSelect={onSelect} onOpenSource={onOpenSource} sourcesRef={sourcesRef} />
                <span className="xf-pos-item">L{u.line}</span>
                <span className="lg-reason">{u.reason}</span>
              </div>
            ))}
          </div>
        )}
        {reg.unresolved_dependencies.length > 0 && (
          <div className="lg-unsup">
            <span className="df-block-title">unresolved dependencies</span>
            {reg.unresolved_dependencies.map((e, i) => (
              <div className="lg-ref-row" key={i}>
                <ProgramLink id={e.from} onSelect={onSelect} onOpenSource={onOpenSource} sourcesRef={sourcesRef} />
                <span className="xf-pos-item">
                  → {e.to ?? e.target ?? e.resolution} ({e.kind}, L{e.line})
                </span>
                <span className="pj-rel-ev">{e.evidence}</span>
              </div>
            ))}
          </div>
        )}
        {reg.ambiguous_dependencies.length > 0 && (
          <div className="lg-unsup">
            <span className="df-block-title">ambiguous dependencies</span>
            {reg.ambiguous_dependencies.map((e, i) => (
              <div className="lg-ref-row" key={`${e.from}:${e.line}:${i}`}>
                <ProgramLink id={e.from} onSelect={onSelect} onOpenSource={onOpenSource} sourcesRef={sourcesRef} />
                <span className="xf-pos-item">→ {e.target} ({e.kind}, L{e.line})</span>
                <span className="pj-rel-ev">{e.evidence}</span>
              </div>
            ))}
          </div>
        )}
        {reg.notes.length > 0 && (
          <div className="lg-unsup">
            <span className="df-block-title">notes</span>
            {reg.notes.map((n) => (
              <div className="lg-ref-row" key={n.finding_id}>
                <span className="lg-name">{n.code} · {n.finding_id}</span>
                {n.file && <ProgramLink id={n.file} onSelect={onSelect} onOpenSource={onOpenSource} sourcesRef={sourcesRef} />}
                <span className="xf-pos-item">{n.line ? `L${n.line}` : "location unavailable"}</span>
                <span className="lg-reason">{n.message}</span>
                {n.evidence && <span className="pj-rel-ev">{n.evidence}</span>}
              </div>
            ))}
          </div>
        )}
        <p className="ov-note">{reg.note}</p>
      </div>

      <div className="ov-section">
        <h3>COVERAGE &amp; LIMITATIONS</h3>
        <div className="lg-unsup">
          {cov.dimensions.map((d) => (
            <div className="lg-ref-row" key={d.dimension}>
              <span className="lg-name">{d.dimension}</span>
              <span className="xf-pos-item">
                {d.covered} of {d.denominator} programs
              </span>
              <span className="lg-reason">{d.note}</span>
            </div>
          ))}
        </div>
        <dl className="ov-kv">
          <dt>Unsupported constructs</dt><dd>{cov.unsupported_constructs_total}</dd>
          <dt>Unresolved relationships</dt><dd>{cov.unresolved_relationships_total}</dd>
          <dt>Analysis assumptions</dt><dd>{cov.assumptions_total}</dd>
        </dl>
        <p className="ov-note">{cov.note}</p>
        <div className="lg-unsup">
          <span className="df-block-title">analysis assumptions ({assumptions.length})</span>
          {assumptions.map((a) => (
            <div className="lg-ref-row" key={a.id}>
              <span className="lg-name">{a.topic}</span>
              <span className="lg-reason">{a.detail}</span>
            </div>
          ))}
        </div>
      </div>
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
  const [selRule, setSelRule] = useState<string | null>(null);
  // rule ids are program-scoped as well
  useEffect(() => {
    setSelRule(null);
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
            <button
              className={`sample-item ${selected === null ? "active" : ""}`}
              onClick={() => setSelected(null)}
              title="Whole-project intelligence overview"
            >
              <span className="name">Project overview</span>
              <span className="desc">inventory · dependencies · rules</span>
            </button>
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
            {!selected && env.overview && (
              <ProjectOverviewView ov={env.overview} assumptions={env.assumptions} onSelect={setSelected}
                onOpenSource={props.onOpenSource} sourcesRef={props.sourcesRef} />
            )}
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

            {selFlow?.rules && (
              <div className="ov-section">
                <h3>RULE CANDIDATES</h3>
                <RuleCandidatesView
                  flow={selFlow}
                  selRule={selRule}
                  onSelect={setSelRule}
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

            {selected && (
              <>
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
              </>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
