import { useCallback, useEffect, useRef, useState } from "react";
import {
  AnalysisResponse,
  ApiError,
  SampleMeta,
  analyzeSource,
  getHealth,
  getSamples,
} from "./api";
import { TopBar } from "./components/TopBar";
import { Rail } from "./components/Rail";
import { EditorPane } from "./components/EditorPane";
import { Inspector } from "./components/Inspector";
import { StatusBar } from "./components/StatusBar";
import { PasteDialog } from "./components/PasteDialog";
import { ProjectWorkspace } from "./components/ProjectWorkspace";

export type TabId = "overview" | "data" | "references" | "diagnostics" | "tokens" | "ast";
export type WorkspaceMode = "file" | "project";

export interface SessionFile {
  id: string;
  filename: string;
  source: string;
}

export interface ActiveSource {
  kind: "sample" | "session";
  id: string;
  filename: string;
  source: string;
}

export interface Toast {
  id: number;
  kind: "ok" | "errors" | "failure";
  text: string;
}

let nextSessionId = 1;
let nextToastId = 1;

export default function App() {
  const [health, setHealth] = useState<{ version: string; online: boolean }>({
    version: "…",
    online: false,
  });
  const [samples, setSamples] = useState<SampleMeta[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [active, setActive] = useState<ActiveSource | null>(null);
  const [sessionFiles, setSessionFiles] = useState<SessionFile[]>([]);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [analyzedSource, setAnalyzedSource] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [engineFailure, setEngineFailure] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>("overview");
  const [caret, setCaret] = useState<{ line: number; col: number }>({ line: 1, col: 1 });
  const [railOpen, setRailOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [mode, setMode] = useState<WorkspaceMode>("file");
  const projectSources = useRef<Record<string, string>>({});
  const [toasts, setToasts] = useState<Toast[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const pushToast = useCallback((kind: Toast["kind"], text: string) => {
    const id = nextToastId++;
    setToasts((ts) => [...ts.slice(-2), { id, kind, text }]);
    window.setTimeout(() => {
      setToasts((ts) => ts.filter((t) => t.id !== id));
    }, 4200);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const h = await getHealth();
        if (!cancelled) setHealth({ version: h.version, online: true });
        const s = await getSamples();
        if (!cancelled) setSamples(s);
      } catch (err) {
        if (!cancelled) {
          setHealth({ version: "?", online: false });
          setLoadError(
            err instanceof Error ? err.message : "engine unreachable",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const dirty = active !== null && analyzedSource !== null && analyzedSource !== active.source;

  const loadSample = useCallback((s: SampleMeta) => {
    setActive({
      kind: "sample",
      id: s.id,
      filename: s.filename,
      source: s.source,
    });
    setAnalysis(null);
    setAnalyzedSource(null);
    setEngineFailure(null);
    setCaret({ line: 1, col: 1 });
    setRailOpen(false);
  }, []);

  const loadSessionFile = useCallback((f: SessionFile) => {
    setActive({ kind: "session", id: f.id, filename: f.filename, source: f.source });
    setAnalysis(null);
    setAnalyzedSource(null);
    setEngineFailure(null);
    setCaret({ line: 1, col: 1 });
    setRailOpen(false);
  }, []);

  const updateSource = useCallback((source: string) => {
    setActive((a) => (a ? { ...a, source } : a));
  }, []);

  const runAnalysis = useCallback(async () => {
    if (!active || analyzing) return;
    setAnalyzing(true);
    setEngineFailure(null);
    try {
      const result = await analyzeSource(active.source, active.filename);
      setAnalysis(result);
      setAnalyzedSource(active.source);
      if (result.summary.ok) {
        pushToast("ok", `Clean parse — ${result.summary.token_count} tokens, within the Rev6.4.2 subset`);
      } else {
        pushToast(
          "errors",
          `${result.summary.errors} error${result.summary.errors === 1 ? "" : "s"} at the ${result.summary.failed_layer} layer`,
        );
        setTab("diagnostics");
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setEngineFailure(`${err.code}: ${err.message}`);
        pushToast("failure", `Analysis failed — ${err.code}`);
      } else {
        setEngineFailure("network: engine unreachable");
        pushToast("failure", "Analysis failed — engine unreachable");
      }
    } finally {
      setAnalyzing(false);
    }
  }, [active, analyzing, pushToast]);

  // Ctrl/Cmd+Enter runs the analysis from anywhere
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        void runAnalysis();
      }
      if (e.key === "Escape") {
        setPasteOpen(false);
        setRailOpen(false);
        setInspectorOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [runAnalysis]);

  const openFile = useCallback(
    (file: File) => {
      const reader = new FileReader();
      reader.onload = () => {
        const text = String(reader.result ?? "");
        const f: SessionFile = {
          id: `session-${nextSessionId++}`,
          filename: file.name,
          source: text,
        };
        setSessionFiles((fs) => [...fs, f]);
        loadSessionFile(f);
      };
      reader.readAsText(file);
    },
    [loadSessionFile],
  );

  const addPasted = useCallback(
    (filename: string, source: string) => {
      const f: SessionFile = {
        id: `session-${nextSessionId++}`,
        filename,
        source,
      };
      setSessionFiles((fs) => [...fs, f]);
      loadSessionFile(f);
      setPasteOpen(false);
    },
    [loadSessionFile],
  );

  const jumpToLine = useCallback((line: number | null, col?: number | null) => {
    if (line !== null) setCaret({ line, col: col ?? 1 });
    if (line !== null) {
      // select the token/word under (line, col) inside the textarea
      const ta = document.querySelector<HTMLTextAreaElement>(".code-input");
      if (ta) {
        const lines = ta.value.split("\n");
        let pos = 0;
        for (let i = 0; i < line - 1 && i < lines.length; i++) {
          pos += (lines[i]?.length ?? 0) + 1;
        }
        const lineText = lines[line - 1] ?? "";
        let start = pos;
        let end = pos + lineText.length;
        if (col && col >= 1) {
          start = pos + Math.min(col - 1, lineText.length);
          // extend over the word at that position
          const value = ta.value;
          let s = start;
          while (s > pos && !/[\s]/.test(value[s - 1] ?? " ")) s -= 1;
          let e = start;
          while (e < pos + lineText.length && !/[\s]/.test(value[e] ?? " ")) e += 1;
          start = s;
          end = Math.max(e, start + 1);
        }
        ta.focus();
        ta.setSelectionRange(start, end);
        // scroll the line into view
        const lineHeight = 19.4;
        ta.scrollTop = Math.max(0, (line - 4) * lineHeight);
        const hl = document.querySelector<HTMLElement>(".code-highlight");
        if (hl) hl.scrollTop = ta.scrollTop;
        const g = document.querySelector<HTMLElement>(".gutter-inner");
        if (g) g.style.transform = `translateY(${-ta.scrollTop}px)`;
      }
    }
  }, []);

  const analyzed = analysis !== null && analyzedSource === active?.source && !dirty;

  return (
    <div className="app">
      <TopBar
        active={active}
        dirty={dirty}
        analyzing={analyzing}
        analysis={analyzed ? analysis : null}
        health={health}
        onAnalyze={() => void runAnalysis()}
        onToggleRail={() => setRailOpen((v) => !v)}
        onToggleInspector={() => setInspectorOpen((v) => !v)}
        mode={mode}
        onMode={setMode}
      />
      <div className="app-body">
        {mode === "project" ? (
          <ProjectWorkspace
            sourcesRef={projectSources.current}
            onOpenSource={(filename, content) => {
              const f: SessionFile = {
                id: `session-${nextSessionId++}`,
                filename,
                source: content,
              };
              setSessionFiles((fs) => [...fs, f]);
              loadSessionFile(f);
              setMode("file");
            }}
          />
        ) : (
          <>
        <Rail
          open={railOpen}
          samples={samples}
          sessionFiles={sessionFiles}
          active={active}
          loadError={loadError}
          onLoadSample={loadSample}
          onLoadSessionFile={loadSessionFile}
          onPaste={() => setPasteOpen(true)}
          onUpload={() => fileInputRef.current?.click()}
          onClose={() => setRailOpen(false)}
        />
        <input
          ref={fileInputRef}
          type="file"
          accept=".cbl,.cob,.txt,text/plain"
          style={{ display: "none" }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) openFile(f);
            e.target.value = "";
          }}
          aria-hidden="true"
          tabIndex={-1}
        />
        <main className="editor-pane" aria-label="COBOL source workspace">
          {active ? (
            <EditorPane
              key={active.id + active.filename}
              source={active.source}
              analyzed={analyzed}
              analysis={analysis}
              activeLine={caret.line}
              onChange={updateSource}
              onCaret={(line, col) => setCaret({ line, col })}
            />
          ) : (
            <div className="editor-empty">
              <div className="card">
                <h2>Load a source to begin</h2>
                <p>
                  NecroSpec validates and parses fixed-format COBOL from the
                  frozen Rev6.4.2 subset: preflight frame checks, lexing,
                  recursive-descent parsing and a semantic AST — with
                  compiler-grade diagnostics at every layer.
                </p>
                <div className="actions">
                  <button
                    className="btn btn-primary"
                    onClick={() => {
                      const first = samples[0];
                      if (first) loadSample(first);
                    }}
                    disabled={samples.length === 0}
                  >
                    Load first corpus fixture
                  </button>
                  <button className="btn" onClick={() => setPasteOpen(true)}>
                    Paste source…
                  </button>
                  <button className="btn" onClick={() => fileInputRef.current?.click()}>
                    Upload file…
                  </button>
                </div>
                {loadError && (
                  <p style={{ marginTop: "var(--sp-4)", color: "var(--state-error)" }}>
                    Engine unreachable: {loadError}
                  </p>
                )}
              </div>
            </div>
          )}
        </main>
        <Inspector
          analysis={analyzed ? analysis : null}
          tab={tab}
          onTab={setTab}
          onJump={jumpToLine}
          filename={active?.filename ?? null}
          source={active?.source ?? null}
          open={inspectorOpen}
          onClose={() => setInspectorOpen(false)}
        />
          </>
        )}
      </div>
      <StatusBar
        health={health}
        active={active}
        analysis={analyzed ? analysis : null}
        dirty={dirty}
        analyzing={analyzing}
        engineFailure={engineFailure}
        caret={caret}
      />
      {pasteOpen && (
        <PasteDialog onCancel={() => setPasteOpen(false)} onSubmit={addPasted} />
      )}
      <div className="toast-region" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind === "failure" ? "errors" : t.kind}`}>
            <span className="t-dot" aria-hidden="true" />
            {t.text}
          </div>
        ))}
      </div>
    </div>
  );
}
