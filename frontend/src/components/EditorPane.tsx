import { useEffect, useMemo, useRef, useState } from "react";
import { AnalysisResponse } from "../api";
import { highlightSource, tokensToLines, HlSpan } from "../highlight";

/** Map diagnostics to per-line worst severity for gutter marks. */
function lineSeverity(analysis: AnalysisResponse | null): Map<number, "error" | "warning"> {
  const map = new Map<number, "error" | "warning">();
  if (!analysis) return map;
  const rank = { error: 2, warning: 1, info: 0 } as const;
  for (const d of analysis.diagnostics) {
    if (d.line == null || d.severity === "info") continue;
    const prev = map.get(d.line);
    if (!prev || rank[d.severity] > rank[prev]) {
      map.set(d.line, d.severity);
    }
  }
  return map;
}

export function EditorPane(props: {
  source: string;
  analyzed: boolean;
  analysis: AnalysisResponse | null;
  activeLine: number | null;
  onChange: (src: string) => void;
  onCaretLine: (line: number) => void;
}) {
  const { source, analysis, analyzed, activeLine } = props;
  const taRef = useRef<HTMLTextAreaElement>(null);
  const hlRef = useRef<HTMLPreElement>(null);
  const gutterRef = useRef<HTMLDivElement>(null);
  const guidesRef = useRef<HTMLDivElement>(null);
  const [caretLine, setCaretLine] = useState(1);

  const sevByLine = useMemo(() => lineSeverity(analysis), [analysis]);

  // while a fresh analysis exists and the source is untouched, colorize from
  // the authoritative backend tokens; while editing, fall back to the local
  // heuristic highlighter
  const lineSpans: HlSpan[][] = useMemo(() => {
    if (analyzed && analysis && analysis.summary.token_count > 0) {
      return tokensToLines(analysis.tokens, source);
    }
    return highlightSource(source);
  }, [analyzed, analysis, source]);

  const lineCount = useMemo(() => source.split("\n").length, [source]);

  const syncScroll = () => {
    const ta = taRef.current;
    if (!ta) return;
    if (hlRef.current) {
      hlRef.current.scrollTop = ta.scrollTop;
      hlRef.current.scrollLeft = ta.scrollLeft;
    }
    if (gutterRef.current) {
      gutterRef.current.style.transform = `translateY(${-ta.scrollTop}px)`;
    }
    if (guidesRef.current) {
      guidesRef.current.style.transform = `translateX(${-ta.scrollLeft}px)`;
    }
  };

  const updateCaret = () => {
    const ta = taRef.current;
    if (!ta) return;
    const upto = ta.value.slice(0, ta.selectionStart);
    const line = upto.split("\n").length;
    setCaretLine(line);
    props.onCaretLine(line);
  };

  useEffect(() => {
    syncScroll();
  }, [source]);

  const hasOver72 = useMemo(
    () => source.split("\n").some((l) => l.length > 72),
    [source],
  );

  // fixed-format ruler geometry: 1 char == 1ch at the code font metrics
  const rulerTicks: { col: number; label: string }[] = [
    { col: 1, label: "1" },
    { col: 7, label: "7" },
    { col: 8, label: "8" },
    { col: 72, label: "72" },
    { col: 73, label: "73" },
  ];

  return (
    <>
      <div className="editor-toolbar">
        <div className="zone-legend" aria-hidden="true">
          <span className="z">
            <span className="sw" style={{ background: "rgba(141,152,162,0.25)" }} />
            1–6 seq
          </span>
          <span className="z">
            <span className="sw" style={{ background: "rgba(217,163,60,0.4)" }} />
            7 indicator
          </span>
          <span className="z">
            <span className="sw" style={{ background: "rgba(69,176,140,0.35)" }} />
            8–72 code
          </span>
          <span className="z">
            <span className="sw" style={{ background: "rgba(224,100,90,0.45)" }} />
            73+ rejected
          </span>
        </div>
        <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: "var(--fs-2xs)" }}>
          {hasOver72 ? (
            <span style={{ color: "var(--state-error)" }}>content past col 72 will be rejected</span>
          ) : (
            <>fixed format · 80-col frame</>
          )}
        </span>
      </div>
      <div className="editor-scroll">
        <div className="ruler" aria-hidden="true">
          <div className="ruler-gutter" />
          <div className="ruler-track">
            <span className="ruler-zone-label" style={{ left: "calc(var(--pad))", transform: "none" }}>
              SEQ
            </span>
            <span className="ruler-zone-label" style={{ left: "calc(var(--pad) + 7ch)" }}>
              IND
            </span>
            <span className="ruler-zone-label" style={{ left: "calc(var(--pad) + 22ch)" }}>
              CODE 8–72
            </span>
            <span
              className="ruler-zone-label"
              style={{ left: "calc(var(--pad) + 73ch)", color: "var(--state-error)" }}
            >
              REJECT
            </span>
            {rulerTicks.map((t) => (
              <span
                key={t.col}
                className="ruler-tick"
                style={{ left: `calc(var(--pad) + ${t.col - 0.5}ch)` }}
              >
                {t.label}
              </span>
            ))}
          </div>
        </div>
        <div className="code-wrap">
          <div className="gutter" style={{ overflow: "hidden" }}>
            <div className="gutter-inner" ref={gutterRef}>
              {Array.from({ length: lineCount }, (_, i) => {
                const n = i + 1;
                const sev = sevByLine.get(n);
                const cls = [
                  "ln",
                  n === caretLine ? "active" : "",
                  sev === "error" ? "diag-error" : sev === "warning" ? "diag-warning" : "",
                ]
                  .filter(Boolean)
                  .join(" ");
                return (
                  <span
                    key={n}
                    className={cls}
                    style={
                      n === activeLine
                        ? { color: "var(--accent-hi)", background: "var(--accent-dim)" }
                        : undefined
                    }
                  >
                    {n}
                  </span>
                );
              })}
            </div>
          </div>
          <div className="code-zone">
            <div className="zone-guides" aria-hidden="true" ref={guidesRef}>
              <span className="zone-guide" style={{ left: "calc(var(--pad) + 6ch)" }} />
              <span className="zone-guide g7" style={{ left: "calc(var(--pad) + 7ch)" }} />
              <span className="zone-guide g72" style={{ left: "calc(var(--pad) + 72ch)" }} />
            </div>
            <pre className="code-highlight" ref={hlRef} aria-hidden="true">
              <code>
                {lineSpans.map((spans, i) => (
                  <span key={i}>
                    {spans.map((s, j) =>
                      s.cls ? (
                        <span key={j} className={s.cls}>
                          {s.text}
                        </span>
                      ) : (
                        <span key={j}>{s.text}</span>
                      ),
                    )}
                    {"\n"}
                  </span>
                ))}
              </code>
            </pre>
            <textarea
              ref={taRef}
              className="code-input"
              value={source}
              onChange={(e) => props.onChange(e.target.value)}
              onScroll={syncScroll}
              onKeyUp={updateCaret}
              onClick={updateCaret}
              onSelect={updateCaret}
              spellCheck={false}
              wrap="off"
              aria-label="COBOL source editor"
            />
          </div>
        </div>
      </div>
    </>
  );
}
