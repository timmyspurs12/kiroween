import { SampleMeta } from "../api";
import { ActiveSource, SessionFile } from "../App";

export function Rail(props: {
  open: boolean;
  samples: SampleMeta[];
  sessionFiles: SessionFile[];
  active: ActiveSource | null;
  loadError: string | null;
  onLoadSample: (s: SampleMeta) => void;
  onLoadSessionFile: (f: SessionFile) => void;
  onPaste: () => void;
  onUpload: () => void;
  onClose: () => void;
}) {
  const positives = props.samples.filter((s) => s.expect_ok);
  const negatives = props.samples.filter((s) => !s.expect_ok && !s.id.startsWith("EXT-"));
  const ext = props.samples.filter((s) => s.id.startsWith("EXT-"));

  const renderItem = (
    key: string,
    filename: string,
    description: string,
    origin: string,
    verdict: "pass" | "reject" | "open",
    activeId: string | null,
    onLoad: () => void,
  ) => (
    <button
      key={key}
      className={`sample-item ${activeId === key ? "active" : ""}`}
      onClick={onLoad}
      title={description}
    >
      <span className="name">
        {filename}
        <span className={`verdict verdict-${verdict}`}>
          {verdict === "pass" ? "PASS" : verdict === "reject" ? "REJECT" : "—"}
        </span>
      </span>
      <span className="desc">{description}</span>
      <span className="origin">{origin}</span>
    </button>
  );

  return (
    <nav className={`rail ${props.open ? "open" : ""}`} aria-label="Source inventory">
      <div className="rail-head">
        <span className="rail-title">SOURCES</span>
        <span className="rail-actions">
          <button className="icon-btn" onClick={props.onPaste} title="Paste source" aria-label="Paste source">
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden="true">
              <rect x="3.5" y="1.5" width="8" height="10" rx="1" stroke="currentColor" strokeWidth="1.3" />
              <path d="M1.5 3.5v7a1 1 0 0 0 1 1H3" stroke="currentColor" strokeWidth="1.3" />
            </svg>
          </button>
          <button className="icon-btn" onClick={props.onUpload} title="Upload file" aria-label="Upload file">
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden="true">
              <path d="M6.5 9V2m0 0L4 4.5M6.5 2 9 4.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M1.5 11.5h10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
          </button>
          <button className="icon-btn rail-close" onClick={props.onClose} title="Close" aria-label="Close source list">
            ×
          </button>
        </span>
      </div>
      <div className="rail-scroll">
        {props.loadError && (
          <div className="rail-group-label" role="alert">
            Engine unreachable — {props.loadError}
          </div>
        )}
        {props.sessionFiles.length > 0 && (
          <>
            <div className="rail-group-label">
              SESSION <span className="badge">{props.sessionFiles.length}</span>
            </div>
            {props.sessionFiles.map((f) =>
              renderItem(
                f.id,
                f.filename,
                "Pasted or uploaded this session",
                "your source",
                "open",
                props.active?.kind === "session" && props.active.id === f.id ? f.id : null,
                () => props.onLoadSessionFile(f),
              ),
            )}
          </>
        )}
        {positives.length > 0 && (
          <>
            <div className="rail-group-label">
              CORPUS · POSITIVE <span className="badge">{positives.length}</span>
            </div>
            {positives.map((s) =>
              renderItem(
                s.id,
                s.filename,
                s.description,
                s.origin,
                "pass",
                props.active?.kind === "sample" && props.active.id === s.id ? s.id : null,
                () => props.onLoadSample(s),
              ),
            )}
          </>
        )}
        {negatives.length > 0 && (
          <>
            <div className="rail-group-label">
              CORPUS · NEGATIVE <span className="badge">{negatives.length}</span>
            </div>
            {negatives.map((s) =>
              renderItem(
                s.id,
                s.filename,
                s.description,
                s.origin,
                "reject",
                props.active?.kind === "sample" && props.active.id === s.id ? s.id : null,
                () => props.onLoadSample(s),
              ),
            )}
          </>
        )}
        {ext.length > 0 && (
          <>
            <div className="rail-group-label">
              ENGINEERED · [EXT] <span className="badge">{ext.length}</span>
            </div>
            {ext.map((s) =>
              renderItem(
                s.id,
                s.filename,
                s.description,
                s.origin,
                "reject",
                props.active?.kind === "sample" && props.active.id === s.id ? s.id : null,
                () => props.onLoadSample(s),
              ),
            )}
          </>
        )}
      </div>
      <div className="rail-foot">
        Corpus fixtures #1–#18 are verbatim transcripts from
        rev4_extract.md (user-attested baseline). [EXT] fixtures are
        agent-engineered. Expected verdicts are shown but never forced —
        every sample is really analyzed when loaded and run.
      </div>
    </nav>
  );
}
