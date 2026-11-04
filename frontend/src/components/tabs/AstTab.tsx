import { useMemo, useState } from "react";
import { AnalysisResponse } from "../../api";

interface TreeNode {
  key: string;
  label: string;
  kindLabel: string | null;
  span: { line: number | null; col: number | null } | null;
  fields: [string, string][]; // scalar fields for the detail panel
  childCounts: [string, number][];
  children: TreeNode[];
  raw: unknown;
}

function labelFor(key: string, v: Record<string, unknown>): { label: string; kindLabel: string | null } {
  if (typeof v.type === "string") {
    const disc = ["name", "program_name", "op", "text", "form", "mode"];
    let extra = "";
    for (const d of disc) {
      if (typeof v[d] === "string" || typeof v[d] === "number") {
        extra = String(v[d]);
        break;
      }
    }
    return { label: extra ? `${v.type} · ${extra}` : v.type, kindLabel: v.type };
  }
  if (typeof v.name === "string") return { label: v.name, kindLabel: key };
  if (typeof v.kind === "string") {
    const extra = typeof v.name === "string" ? v.name : typeof v.text === "string" ? v.text : typeof v.op === "string" ? v.op : "";
    return { label: extra ? `${v.kind} · ${extra}` : v.kind, kindLabel: v.kind };
  }
  return { label: key, kindLabel: null };
}

function buildTree(key: string, value: unknown, path: string): TreeNode {
  if (Array.isArray(value)) {
    return {
      key: path,
      label: `${key} [${value.length}]`,
      kindLabel: "array",
      span: null,
      fields: [],
      childCounts: [],
      children: value.map((item, i) =>
        buildTree(Array.isArray(item) || (item && typeof item === "object") ? `${key}[${i}]` : `${key}[${i}]`, item, `${path}.${i}`),
      ),
      raw: value,
    };
  }
  if (value && typeof value === "object") {
    const v = value as Record<string, unknown>;
    const { label, kindLabel } = labelFor(key, v);
    const fields: [string, string][] = [];
    const childCounts: [string, number][] = [];
    const children: TreeNode[] = [];
    for (const [k, val] of Object.entries(v)) {
      if (k === "span") continue;
      if (val !== null && typeof val === "object") {
        if (Array.isArray(val)) {
          if (val.length > 0) {
            childCounts.push([k, val.length]);
            children.push(buildTree(k, val, `${path}.${k}`));
          }
        } else {
          children.push(buildTree(k, val, `${path}.${k}`));
        }
      } else if (val !== null) {
        fields.push([k, String(val)]);
      }
    }
    const span = (v.span as { line?: number | null; col?: number | null } | undefined) ?? null;
    return {
      key: path,
      label,
      kindLabel,
      span: span ? { line: span.line ?? null, col: span.col ?? null } : null,
      fields,
      childCounts,
      children,
      raw: value,
    };
  }
  return {
    key: path,
    label: `${key}: ${String(value)}`,
    kindLabel: null,
    span: null,
    fields: [[key, String(value)]],
    childCounts: [],
    children: [],
    raw: value,
  };
}

function NodeRow({
  node,
  depth,
  selectedPath,
  onSelect,
}: {
  node: TreeNode;
  depth: number;
  selectedPath: string | null;
  onSelect: (n: TreeNode) => void;
}) {
  const [open, setOpen] = useState(depth < 2);
  const hasKids = node.children.length > 0;
  const selected = selectedPath === node.key;
  return (
    <>
      <button
        className={`ast-node-row ${selected ? "selected" : ""}`}
        style={{ paddingLeft: `${12 + depth * 16}px` }}
        onClick={() => {
          onSelect(node);
          if (node.span?.line != null) {
            // jumping handled by parent through onSelect
          }
        }}
        title={node.span?.line != null ? `line ${node.span.line}` : node.key}
      >
        <span
          className="ast-caret"
          onClick={(e) => {
            if (hasKids) {
              e.stopPropagation();
              setOpen((v) => !v);
            }
          }}
          role="button"
          tabIndex={-1}
          aria-label={hasKids ? (open ? "Collapse" : "Expand") : undefined}
        >
          {hasKids ? (open ? "▾" : "▸") : "·"}
        </span>
        {node.kindLabel && <span className="ast-kind">{node.kindLabel}</span>}
        <span className="ast-label">{node.label}</span>
        {node.span?.line != null && (
          <span className="ast-loc">L{node.span.line}</span>
        )}
      </button>
      {open &&
        node.children.map((c) => (
          <NodeRow
            key={c.key}
            node={c}
            depth={depth + 1}
            selectedPath={selectedPath}
            onSelect={onSelect}
          />
        ))}
    </>
  );
}

export function AstTab({
  analysis,
  onJump,
}: {
  analysis: AnalysisResponse;
  onJump: (line: number | null, col?: number | null) => void;
}) {
  const [selected, setSelected] = useState<TreeNode | null>(null);

  const root = useMemo(() => {
    if (!analysis.ast) return null;
    return buildTree("Program", analysis.ast, "ast");
  }, [analysis.ast]);

  if (!analysis.ast || !root) {
    return (
      <div className="inspector-empty">
        No AST — the source did not reach the grammar layer. See the
        Diagnostics tab for why parsing stopped.
      </div>
    );
  }

  return (
    <div>
      <div className="ast-tree">
        <NodeRow
          node={root}
          depth={0}
          selectedPath={selected?.key ?? null}
          onSelect={(n) => {
            setSelected(n);
            if (n.span?.line != null) onJump(n.span.line, n.span.col);
          }}
        />
      </div>
      {selected && (
        <div className="ast-detail">
          <h4>
            NODE DETAIL{" "}
            {selected.span?.line != null && (
              <button
                className="btn"
                style={{ marginLeft: "var(--sp-2)", padding: "2px 8px", fontSize: "var(--fs-2xs)" }}
                onClick={() => onJump(selected.span?.line ?? null, selected.span?.col ?? null)}
              >
                jump to line {selected.span?.line}
              </button>
            )}
          </h4>
          <pre>
            {selected.kindLabel && <>type: {selected.kindLabel}{"\n"}</>}
            {selected.fields.map(([k, v]) => (
              <span key={k}>
                {k}: {v}
                {"\n"}
              </span>
            ))}
            {selected.childCounts.map(([k, n]) => (
              <span key={k} style={{ color: "var(--text-faint)" }}>
                {k}: {n} node{n === 1 ? "" : "s"} (expand in tree)
                {"\n"}
              </span>
            ))}
          </pre>
        </div>
      )}
    </div>
  );
}
