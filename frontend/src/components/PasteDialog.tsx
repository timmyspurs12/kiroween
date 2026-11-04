import { useEffect, useRef, useState } from "react";

export function PasteDialog(props: {
  onCancel: () => void;
  onSubmit: (filename: string, source: string) => void;
}) {
  const [filename, setFilename] = useState("PASTED.cbl");
  const [source, setSource] = useState("");
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    taRef.current?.focus();
  }, []);

  const valid = source.trim().length > 0 && filename.trim().length > 0;

  return (
    <div
      className="dialog-scrim"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) props.onCancel();
      }}
    >
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="paste-dialog-title"
      >
        <div className="dialog-head">
          <h2 id="paste-dialog-title">Paste COBOL source</h2>
          <button className="icon-btn" onClick={props.onCancel} aria-label="Close dialog">
            ×
          </button>
        </div>
        <div className="dialog-body">
          <div>
            <label htmlFor="paste-filename">File name</label>
            <input
              id="paste-filename"
              type="text"
              value={filename}
              onChange={(e) => setFilename(e.target.value)}
              placeholder="PROGRAM.cbl"
            />
          </div>
          <div>
            <label htmlFor="paste-source">Fixed-format source</label>
            <textarea
              id="paste-source"
              ref={taRef}
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder={"       IDENTIFICATION DIVISION.\n       PROGRAM-ID. EXAMPLE.\n       DATA DIVISION.\n       LINKAGE SECTION.\n       01  LK-IO.\n           05  LK-AMOUNT    PIC S9(5)V99  COMP-3.\n       PROCEDURE DIVISION USING LK-IO.\n           GOBACK."}
              spellCheck={false}
              wrap="off"
            />
          </div>
          <p style={{ margin: 0, fontSize: "var(--fs-xs)", color: "var(--text-faint)" }}>
            The pasted text becomes a session source in the inventory. Nothing
            is stored server-side; analysis happens per request.
          </p>
        </div>
        <div className="dialog-foot">
          <button className="btn" onClick={props.onCancel}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            disabled={!valid}
            onClick={() => props.onSubmit(filename.trim(), source)}
          >
            Add to session
          </button>
        </div>
      </div>
    </div>
  );
}
