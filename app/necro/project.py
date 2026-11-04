"""NecroSpec project analysis (Milestone 3) — multi-file dependency intelligence.

Ingests a set of COBOL source files (.cbl/.cob programs, .cpy copybooks),
discovers COPY and CALL relationships from source evidence, and builds a
deterministic dependency graph with resolution status, evidence and impact
analysis.

Design boundaries (frozen Rev6.4.2 subset):
  * COPY and CALL are reserved words OUTSIDE the frozen program grammar.
    Files containing them are rejected for full single-file analysis (the
    per-file result shows the grammar diagnostic). This module therefore
    performs a separate, source-grounded DISCOVERY SCAN: it recognizes the
    statement shapes COPY <name> [OF|IN lib] [. | REPLACING ...] and
    CALL "literal" / CALL identifier in the fixed-format content area
    (columns 8-72, comment lines skipped). A relationship is recorded only
    when the statement shape matches exactly — similar names are never
    treated as dependencies. No textual COPY expansion is performed.
  * Resolution is by exact basename stem match (case-insensitive) against
    the project file set — never by similarity.
  * Determinism: every list is sorted; two runs over the same inputs
    produce byte-identical JSON.

Project result schema: {"schema_version": 1, ...}. Per-file analysis
results embed the single-file envelope (schema_version 2) unchanged —
proven findings are never downgraded.
"""
import hashlib
import re
from typing import Dict, List, Optional, Tuple

from necro.analyzer import analyze
from necro.diagnostics import (CLASS_NOTE, CLASS_RISK, CLASS_UNSUPPORTED,
                               CLASS_VIOLATION, Diagnostic, LAYER_SEMANTIC,
                               SEVERITY_ERROR, SEVERITY_INFO,
                               SEVERITY_WARNING, _SEVERITY_CLASSIFICATION)

PROJECT_SCHEMA_VERSION = 1

PROGRAM_EXTS = {".cbl", ".cob"}
COPYBOOK_EXTS = {".cpy"}
SUPPORTED_EXTS = PROGRAM_EXTS | COPYBOOK_EXTS

# program-level project finding codes ([EXT])
DEP_COPYBOOK_MISSING = "DEP_COPYBOOK_MISSING"
DEP_COPYBOOK_AMBIGUOUS = "DEP_COPYBOOK_AMBIGUOUS"
DEP_CALL_DYNAMIC = "DEP_CALL_DYNAMIC"
DEP_CALL_STATIC_UNRESOLVED = "DEP_CALL_STATIC_UNRESOLVED"
DEP_CYCLE = "DEP_CYCLE"
DEP_COPY_REPLACING_UNSUPPORTED = "DEP_COPY_REPLACING_UNSUPPORTED"
DEP_FILE_UNREADABLE = "DEP_FILE_UNREADABLE"
DEP_PATH_REJECTED = "DEP_PATH_REJECTED"
DEP_EXT_UNSUPPORTED = "DEP_EXT_UNSUPPORTED"
DEP_DUPLICATE_BASENAME = "DEP_DUPLICATE_BASENAME"

PROJECT_HINTS = {
    DEP_COPYBOOK_MISSING: "Add the copybook to the project (a file whose "
                          "basename matches the referenced name), or correct "
                          "the COPY statement.",
    DEP_COPYBOOK_AMBIGUOUS: "Disambiguate by removing or renaming duplicate "
                            "copybooks, or by qualifying with COPY name OF/IN "
                            "library (recorded, not yet used for resolution).",
    DEP_CALL_DYNAMIC: "Locate the assignment to the call identifier to "
                      "establish the real target; static analysis cannot "
                      "resolve it.",
    DEP_CALL_STATIC_UNRESOLVED: "Include the called program in the project, "
                                "or confirm the literal target.",
    DEP_CYCLE: "Break the inclusion cycle; cyclic copybooks cannot be "
               "expanded or analyzed in dependency order.",
    DEP_COPY_REPLACING_UNSUPPORTED: "The dependency is recorded, but "
                                    "REPLACING semantics are outside the "
                                    "analyzed subset and were not applied.",
    DEP_FILE_UNREADABLE: "Check file permissions or re-include the file.",
    DEP_PATH_REJECTED: "Use project-relative paths without dot-dot segments "
                       "or absolute roots.",
    DEP_EXT_UNSUPPORTED: "Only .cbl/.cob programs and .cpy copybooks are "
                         "analyzed in this milestone.",
    DEP_DUPLICATE_BASENAME: "Duplicate basenames make COPY/CALL resolution "
                            "ambiguous when referenced; rename or qualify.",
}

PROJECT_ASSUMPTIONS = [
    {
        "id": "no-copy-expansion",
        "topic": "No COPY expansion",
        "detail": ("COPY statements are discovered as dependencies with "
                   "evidence but are NOT textually expanded; per-file "
                   "analysis does not see copybook-defined data. Programs "
                   "containing COPY or CALL are outside the frozen program "
                   "grammar and are reported as rejected for full "
                   "single-file analysis."),
    },
    {
        "id": "resolution-by-stem",
        "topic": "Resolution by basename stem",
        "detail": ("COPY targets resolve by exact case-insensitive stem "
                   "match, preferring .cpy files when any candidate exists; "
                   "CALL targets prefer .cbl/.cob programs. OF/IN library "
                   "qualifiers are recorded as evidence but not yet used to "
                   "disambiguate."),
    },
    {
        "id": "calls-not-executed",
        "topic": "Calls are static references only",
        "detail": ("CALL targets are resolved to project files by name "
                   "literal; no program is executed and dynamic targets "
                   "(identifiers) are reported as unresolved."),
    },
    {
        "id": "impact-not-runtime",
        "topic": "Dependency impact is not runtime impact",
        "detail": ("Graph impact lists files whose source references a "
                   "changed file; it is not proof of runtime behavior "
                   "change."),
    },
    {
        "id": "subset-per-file",
        "topic": "Per-file analysis covers the frozen subset",
        "detail": ("Full analysis applies only to files within the frozen "
                   "Rev6.4.2 grammar; other files contribute dependency "
                   "evidence but not semantic results."),
    },
]

# ---- discovery scans ----------------------------------------------------

_WORD = r"[A-Za-z][A-Za-z0-9-]*"
COPY_RE = re.compile(
    r"^COPY\s+(?P<name>%s)(?:\s+(?:OF|IN)\s+(?P<lib>%s))?(?P<rest>.*)$"
    % (_WORD, _WORD), re.IGNORECASE)
REPLACING_RE = re.compile(r"^REPLACING\b", re.IGNORECASE)
CALL_LIT_RE = re.compile(r"^CALL\s+\"(?P<target>[^\"]*)\"", re.IGNORECASE)
CALL_ID_RE = re.compile(r"^CALL\s+(?P<target>%s)\b" % _WORD, re.IGNORECASE)
COPY_KW_RE = re.compile(r"\bCOPY\b", re.IGNORECASE)
CALL_KW_RE = re.compile(r"\bCALL\b", re.IGNORECASE)

_MAX_STATEMENT_WINDOW = 8  # lines a discovered COPY statement may span


def _safe_relpath(path: str) -> Optional[str]:
    """Normalize and validate a project-relative path; None if rejected."""
    if not path or not isinstance(path, str):
        return None
    p = path.replace("\\", "/").strip()
    if p.startswith("/") or (len(p) > 1 and p[1] == ":"):
        return None
    parts = p.split("/")
    if any(seg in ("", ".", "..") for seg in parts):
        return None
    return "/".join(parts)


def _kind_for(path: str) -> Optional[str]:
    lower = path.lower()
    if lower.endswith(tuple(PROGRAM_EXTS)):
        return "program"
    if lower.endswith(tuple(COPYBOOK_EXTS)):
        return "copybook"
    return None


def _stem(path: str) -> str:
    base = path.rsplit("/", 1)[-1]
    return base.rsplit(".", 1)[0].upper()


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def _indicator_ok(line: str) -> bool:
    """Comment lines (*) and page ejects (/) carry no statements."""
    return len(line) < 7 or line[6] not in ("*", "/")


def _content(line: str) -> str:
    return line[7:72] if len(line) > 7 else ""


def _diag(severity, code, message, line, col, evidence, detail=None):
    return Diagnostic(severity, code, message, line, col, LAYER_SEMANTIC,
                      evidence=evidence,
                      classification=_SEVERITY_CLASSIFICATION[severity],
                      detail=detail)


# Project finding hints are attached through the shared HINTS registry.
def _register_project_hints() -> None:
    from necro import diagnostics as _d
    _d.HINTS.update(PROJECT_HINTS)


_register_project_hints()


# =========================================================================
# discovery scan: COPY / CALL statement shapes in the content area
# =========================================================================

def discover_references(file_id: str, text: str) -> List[dict]:
    """Source-grounded discovery of COPY/CALL statement shapes. Records a
    reference only when the shape matches; returns deterministic order."""
    lines = text.split("\n")
    refs: List[dict] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if not _indicator_ok(line):
            i += 1
            continue
        content = _content(line)

        m = COPY_KW_RE.search(content)
        if m:
            col = 8 + m.start()
            # gather the statement text up to the first period, spanning a
            # small window of continuation lines
            stmt_parts = [content[m.start():]]
            stmt_lines = [i + 1]
            j = i
            ended = False
            while j < n and len(stmt_lines) <= _MAX_STATEMENT_WINDOW:
                seg = stmt_parts[-1] if j == i else _content(lines[j])
                if j > i:
                    stmt_parts.append(_content(lines[j]))
                    stmt_lines.append(j + 1)
                if j > i and not _indicator_ok(lines[j]):
                    j += 1
                    continue
                if "." in seg:
                    ended = True
                    break
                j += 1
            stmt = " ".join(p.strip() for p in stmt_parts if p.strip())
            stmt_clean = stmt.split(".")[0].strip()
            dm = COPY_RE.match(stmt_clean)
            if dm:
                form = "simple"
                if dm.group("lib"):
                    form = "library"
                if REPLACING_RE.match((dm.group("rest") or "").strip()):
                    form = "replacing"
                refs.append({
                    "kind": "copy",
                    "file": file_id,
                    "target": dm.group("name").upper(),
                    "library": dm.group("lib").upper() if dm.group("lib") else None,
                    "form": form,
                    "terminated": ended,
                    "line": i + 1,
                    "col": col,
                    "text": content.strip()[:80],
                    "statement_lines": stmt_lines,
                })
            i += 1
            continue

        m = CALL_LIT_RE.match(content.strip())
        if m:
            refs.append({
                "kind": "call", "file": file_id,
                "target": m.group("target").strip().upper(),
                "target_form": "literal",
                "line": i + 1, "col": 8 + (len(content) - len(content.lstrip())),
                "text": content.strip()[:80],
            })
            i += 1
            continue
        m = CALL_ID_RE.match(content.strip())
        if m:
            refs.append({
                "kind": "call", "file": file_id,
                "target": m.group("target").upper(),
                "target_form": "identifier",
                "line": i + 1, "col": 8 + (len(content) - len(content.lstrip())),
                "text": content.strip()[:80],
            })
        i += 1
    return refs


# =========================================================================
# resolution + graph
# =========================================================================

def _resolve_copy(target: str, by_stem: Dict[str, List[str]]) -> List[str]:
    """COPY resolution: exact stem match, preferring copybook files (.cpy)
    when any exist — a program sharing the copybook's name is not the
    natural COPY target. Deterministic and similarity-free."""
    cands = by_stem.get(target, [])
    copybooks = [c for c in cands if _kind_for(c) == "copybook"]
    return sorted(copybooks) if copybooks else sorted(cands)


def _resolve_call(target: str, program_stems: Dict[str, List[str]]) -> List[str]:
    return sorted(program_stems.get(target, []))


def _tarjan_scc(nodes: List[str], adj: Dict[str, List[str]]) -> List[List[str]]:
    """Iterative Tarjan SCC over sorted adjacency — deterministic output."""
    index_counter = [0]
    stack: List[str] = []
    on_stack = set()
    index: Dict[str, int] = {}
    lowlink: Dict[str, int] = {}
    result: List[List[str]] = []

    for root in nodes:
        if root in index:
            continue
        work = [(root, 0)]
        while work:
            node, pi = work[-1]
            if pi == 0:
                index[node] = lowlink[node] = index_counter[0]
                index_counter[0] += 1
                stack.append(node)
                on_stack.add(node)
            recurse = False
            successors = adj.get(node, [])
            while pi < len(successors):
                succ = successors[pi]
                pi += 1
                if succ not in index:
                    work[-1] = (node, pi)
                    work.append((succ, 0))
                    recurse = True
                    break
                elif succ in on_stack:
                    lowlink[node] = min(lowlink[node], index[succ])
            if recurse:
                continue
            if lowlink[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    comp.append(w)
                    if w == node:
                        break
                result.append(sorted(comp))
            work.pop()
            if work:
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])
    return sorted(result)


def analyze_project(name: str, entries: List[dict]) -> dict:
    """entries: [{"path": relpath, "content": str} | {"path": relpath,
    "error": reason}] — build the full project envelope (schema_version 1)."""
    findings: List[Diagnostic] = []
    files: List[dict] = []
    contents: Dict[str, str] = {}
    skipped: List[dict] = []

    # ---- ingestion ------------------------------------------------------
    seen_paths = set()
    for e in entries:
        raw = e.get("path", "")
        safe = _safe_relpath(raw)
        if safe is None:
            findings.append(_diag(
                SEVERITY_ERROR, DEP_PATH_REJECTED,
                f"Path {raw!r} is not a safe project-relative path.",
                None, None, f"Rejected during ingestion: {raw!r}"))
            skipped.append({"path": raw, "reason": "unsafe path",
                            "code": DEP_PATH_REJECTED})
            continue
        if safe in seen_paths:
            skipped.append({"path": safe, "reason": "duplicate path entry",
                            "code": DEP_PATH_REJECTED})
            continue
        seen_paths.add(safe)
        kind = _kind_for(safe)
        if kind is None:
            findings.append(_diag(
                SEVERITY_INFO, DEP_EXT_UNSUPPORTED,
                f"File {safe} has an unsupported extension; it was indexed "
                f"but not analyzed.",
                None, None, f"Discovered during project ingestion: {safe}"))
            skipped.append({"path": safe, "reason": "unsupported extension",
                            "code": DEP_EXT_UNSUPPORTED})
            continue
        if "error" in e:
            findings.append(_diag(
                SEVERITY_ERROR, DEP_FILE_UNREADABLE,
                f"File {safe} could not be read: {e['error']}",
                None, None, f"Ingestion error for {safe}: {e['error']}"))
            skipped.append({"path": safe, "reason": f"unreadable: {e['error']}",
                            "code": DEP_FILE_UNREADABLE})
            continue
        text = e.get("content")
        if not isinstance(text, str):
            findings.append(_diag(
                SEVERITY_ERROR, DEP_FILE_UNREADABLE,
                f"File {safe} has no readable content.",
                None, None, f"Ingestion error for {safe}: no content"))
            skipped.append({"path": safe, "reason": "no content",
                            "code": DEP_FILE_UNREADABLE})
            continue
        contents[safe] = text
        files.append({
            "file_id": safe,
            "path": safe,
            "kind": kind,
            "bytes": len(text.encode("utf-8", errors="surrogateescape")),
            "lines": text.split("\n").__len__(),
        })
    files.sort(key=lambda f: f["file_id"])

    # duplicate basenames (visibility; ambiguity matters when referenced)
    by_base: Dict[str, List[str]] = {}
    for f in files:
        by_base.setdefault(_basename(f["file_id"]).upper(), []).append(f["file_id"])
    for base in sorted(by_base):
        if len(by_base[base]) > 1:
            findings.append(_diag(
                SEVERITY_INFO, DEP_DUPLICATE_BASENAME,
                f"{len(by_base[base])} files share the basename {base}.",
                None, None,
                "Discovered during project ingestion: " + ", ".join(by_base[base]),
                detail={"basename": base, "files": by_base[base]}))

    # stems -> file ids
    by_stem: Dict[str, List[str]] = {}
    for f in files:
        by_stem.setdefault(_stem(f["file_id"]), []).append(f["file_id"])
    program_stems = {}
    for s, v in by_stem.items():
        progs = sorted(fid for fid in v if _kind_for(fid) == "program")
        if progs:
            program_stems[s] = progs

    # ---- discovery + resolution ------------------------------------------
    references: List[dict] = []
    edges: List[dict] = []
    for f in files:
        fid = f["file_id"]
        for ref in discover_references(fid, contents[fid]):
            references.append(ref)
            if ref["kind"] == "copy":
                cands = _resolve_copy(ref["target"], by_stem)
                if len(cands) == 1:
                    resolution = "resolved"
                    to = cands[0]
                elif len(cands) == 0:
                    resolution = "missing"
                    to = None
                else:
                    resolution = "ambiguous"
                    to = None
                edges.append({
                    "kind": "copy", "from": fid, "to": to,
                    "target": ref["target"], "library": ref["library"],
                    "form": ref["form"],
                    "terminated": ref["terminated"],
                    "resolution": resolution, "candidates": cands,
                    "line": ref["line"], "col": ref["col"],
                    "text": ref["text"],
                })
            else:  # call
                if ref["target_form"] == "identifier":
                    edges.append({
                        "kind": "call", "from": fid, "to": None,
                        "target": ref["target"], "target_form": "identifier",
                        "resolution": "dynamic", "candidates": [],
                        "line": ref["line"], "col": ref["col"],
                        "text": ref["text"],
                    })
                else:
                    cands = _resolve_call(ref["target"], program_stems)
                    if len(cands) == 1:
                        edges.append({
                            "kind": "call", "from": fid, "to": cands[0],
                            "target": ref["target"], "target_form": "literal",
                            "resolution": "resolved", "candidates": cands,
                            "line": ref["line"], "col": ref["col"],
                            "text": ref["text"],
                        })
                    elif len(cands) == 0:
                        edges.append({
                            "kind": "call", "from": fid, "to": None,
                            "target": ref["target"], "target_form": "literal",
                            "resolution": "unresolved", "candidates": [],
                            "line": ref["line"], "col": ref["col"],
                            "text": ref["text"],
                        })
                    else:
                        edges.append({
                            "kind": "call", "from": fid, "to": None,
                            "target": ref["target"], "target_form": "literal",
                            "resolution": "ambiguous", "candidates": cands,
                            "line": ref["line"], "col": ref["col"],
                            "text": ref["text"],
                        })
    references.sort(key=lambda r: (r["file"], r["line"], r["kind"]))
    edges.sort(key=lambda e: (e["from"], e["line"], e["kind"], e["target"]))

    # ---- project-level findings from edges -------------------------------
    for e in edges:
        loc = f"{e['from']} line {e['line']}"
        if e["kind"] == "copy":
            if e["resolution"] == "missing":
                findings.append(_diag(
                    SEVERITY_ERROR, DEP_COPYBOOK_MISSING,
                    f"COPY {e['target']} at {loc} has no matching copybook "
                    f"in the project.",
                    e["line"], e["col"], f"{loc}: {e['text']}",
                    detail={"file": e["from"], "target": e["target"]}))
            elif e["resolution"] == "ambiguous":
                findings.append(_diag(
                    SEVERITY_WARNING, DEP_COPYBOOK_AMBIGUOUS,
                    f"COPY {e['target']} at {loc} matches "
                    f"{len(e['candidates'])} candidate files; the reference "
                    f"is ambiguous.",
                    e["line"], e["col"], f"{loc}: {e['text']}",
                    detail={"file": e["from"], "target": e["target"],
                            "candidates": e["candidates"]}))
            if e["form"] == "replacing":
                findings.append(_diag(
                    SEVERITY_INFO, DEP_COPY_REPLACING_UNSUPPORTED,
                    f"COPY {e['target']} at {loc} uses REPLACING; the "
                    f"dependency is recorded but REPLACING semantics are "
                    f"outside the analyzed subset.",
                    e["line"], e["col"], f"{loc}: {e['text']}",
                    detail={"file": e["from"], "target": e["target"]}))
            elif not e["terminated"]:
                findings.append(_diag(
                    SEVERITY_INFO, DEP_COPY_REPLACING_UNSUPPORTED,
                    f"COPY {e['target']} at {loc} has no terminating "
                    f"period within the scanned window; the dependency is "
                    f"recorded, the statement is malformed.",
                    e["line"], e["col"], f"{loc}: {e['text']}",
                    detail={"file": e["from"], "target": e["target"]}))
        else:
            if e["resolution"] == "dynamic":
                findings.append(_diag(
                    SEVERITY_WARNING, DEP_CALL_DYNAMIC,
                    f"CALL {e['target']} at {loc} targets an identifier; "
                    f"the call target cannot be established statically.",
                    e["line"], e["col"], f"{loc}: {e['text']}",
                    detail={"file": e["from"], "target": e["target"]}))
            elif e["resolution"] == "unresolved":
                findings.append(_diag(
                    SEVERITY_WARNING, DEP_CALL_STATIC_UNRESOLVED,
                    f"CALL \"{e['target']}\" at {loc} names no program in "
                    f"the project.",
                    e["line"], e["col"], f"{loc}: {e['text']}",
                    detail={"file": e["from"], "target": e["target"]}))
            elif e["resolution"] == "ambiguous":
                findings.append(_diag(
                    SEVERITY_WARNING, DEP_COPYBOOK_AMBIGUOUS,
                    f"CALL \"{e['target']}\" at {loc} matches "
                    f"{len(e['candidates'])} programs; the call is "
                    f"ambiguous.",
                    e["line"], e["col"], f"{loc}: {e['text']}",
                    detail={"file": e["from"], "target": e["target"],
                            "candidates": e["candidates"]}))

    # ---- cycles over resolved COPY edges ---------------------------------
    adj: Dict[str, List[str]] = {f["file_id"]: [] for f in files}
    for e in edges:
        if e["kind"] == "copy" and e["resolution"] == "resolved":
            adj[e["from"]].append(e["to"])
    for k in adj:
        adj[k] = sorted(set(adj[k]))
    cycles = [c for c in _tarjan_scc(sorted(adj), adj)
              if len(c) > 1 or (len(c) == 1 and c[0] in adj.get(c[0], []))]
    for c in cycles:
        findings.append(_diag(
            SEVERITY_WARNING, DEP_CYCLE,
            f"Cyclic copybook inclusion: {' -> '.join(c + [c[0]])}.",
            None, None,
            "Established from resolved COPY edges: "
            + "; ".join(f"{a} -> {b}" for a in c
                        for b in adj[a] if b in c)
            + ".", detail={"members": c}))

    # ---- per-file analysis (frozen-subset single-file envelope) ----------
    per_file: Dict[str, dict] = {}
    for f in files:
        fid = f["file_id"]
        if f["kind"] == "copybook":
            per_file[fid] = {
                "status": "copybook",
                "reason": "copybooks contribute dependency evidence; they "
                          "are not analyzed as programs",
            }
            continue
        result = analyze(contents[fid], _basename(fid))
        if result["summary"]["ok"]:
            status = "analyzed"
            reason = None
        else:
            status = "rejected"
            reason = (f"single-file analysis rejected at "
                      f"{result['summary']['failed_layer']} layer: "
                      + "; ".join(d["code"] for d in result["diagnostics"][:3]))
        per_file[fid] = {"status": status, "reason": reason,
                         "result": result}

    findings.sort(key=lambda d: (d.code, d.line is None, d.line or 0,
                                 d.col or 0))

    # ---- coverage + summary ------------------------------------------------
    analyzed = [fid for fid, p in per_file.items() if p["status"] == "analyzed"]
    rejected = [fid for fid, p in per_file.items() if p["status"] == "rejected"]
    res_counts = {"resolved": 0, "missing": 0, "ambiguous": 0,
                  "dynamic": 0, "unresolved": 0}
    for e in edges:
        res_counts[e["resolution"]] += 1
    severity_counts = {"error": 0, "warning": 0, "info": 0}
    for d in findings:
        severity_counts[d.severity] += 1

    coverage = {
        "files_total": len(files) + len(skipped),
        "files_indexed": len(files),
        "files_analyzed": len(analyzed),
        "files_rejected": len(rejected),
        "files_copybook": sum(1 for f in files if f["kind"] == "copybook"),
        "files_skipped": len(skipped),
        "dependencies_total": len(edges),
        "dependencies_resolved": res_counts["resolved"],
        "dependencies_unresolved": (res_counts["missing"]
                                    + res_counts["unresolved"]
                                    + res_counts["dynamic"]),
        "dependencies_ambiguous": res_counts["ambiguous"],
        "cycles": len(cycles),
        "findings": {
            "error": severity_counts["error"],
            "warning": severity_counts["warning"],
            "info": severity_counts["info"],
        },
    }
    summary = {
        "ok": severity_counts["error"] == 0,
        "errors": severity_counts["error"],
        "warnings": severity_counts["warning"],
        "infos": severity_counts["info"],
        "programs": sum(1 for f in files if f["kind"] == "program"),
        "copybooks": sum(1 for f in files if f["kind"] == "copybook"),
    }

    return {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "project": {"name": name},
        "files": files,
        "skipped": skipped,
        "references": references,
        "edges": edges,
        "cycles": cycles,
        "per_file": {fid: per_file[fid] for fid in sorted(per_file)},
        "findings": [_fdiag_json(d) for d in findings],
        "coverage": coverage,
        "assumptions": PROJECT_ASSUMPTIONS,
        "summary": summary,
    }


def _fdiag_json(d: Diagnostic) -> dict:
    j = d.to_json()
    return j


# =========================================================================
# impact analysis
# =========================================================================

def impact(project: dict, file_id: str) -> dict:
    """Impact for one file: direct dependencies/dependants (resolved edges
    only), transitive dependants, and unresolved relationships touching it.
    Dependency impact is source-reference impact, not runtime proof."""
    resolved_out: List[dict] = []
    resolved_in: List[dict] = []
    unresolved: List[dict] = []
    for e in project["edges"]:
        if e["from"] == file_id:
            (resolved_out if e["resolution"] == "resolved" else unresolved).append(e)
        elif e["to"] == file_id:
            (resolved_in if e["resolution"] == "resolved" else unresolved).append(e)

    # transitive dependants over resolved edges (reverse reachability)
    rev: Dict[str, List[str]] = {}
    for e in project["edges"]:
        if e["resolution"] == "resolved" and e["to"]:
            rev.setdefault(e["to"], []).append(e["from"])
    for k in rev:
        rev[k] = sorted(set(rev[k]))
    seen = set()
    frontier = [file_id]
    while frontier:
        nxt = []
        for node in frontier:
            for dep in rev.get(node, []):
                if dep not in seen and dep != file_id:
                    seen.add(dep)
                    nxt.append(dep)
        frontier = sorted(nxt)
    transitive = sorted(seen)

    return {
        "file": file_id,
        "direct_dependencies": [
            {"to": e["to"], "kind": e["kind"], "line": e["line"],
             "evidence": e["text"]} for e in resolved_out],
        "direct_dependants": [
            {"from": e["from"], "kind": e["kind"], "line": e["line"],
             "evidence": e["text"]} for e in resolved_in],
        "transitive_dependants": transitive,
        "unresolved_relationships": [
            {"kind": e["kind"], "resolution": e["resolution"],
             "target": e["target"], "from": e["from"], "to": e["to"],
             "line": e["line"], "evidence": e["text"]}
            for e in sorted(unresolved, key=lambda x: (x["from"], x["line"]))],
        "note": "Dependency impact reflects source references, not proof "
                "of runtime impact.",
    }


# =========================================================================
# directory ingestion helper (CLI)
# =========================================================================

def ingest_directory(root: str) -> Tuple[str, List[dict]]:
    """Read a directory deterministically; returns (name, entries).
    Unreadable files become entries with an 'error' key — never silently
    skipped."""
    import os
    root = os.path.abspath(root)
    name = os.path.basename(root) or root
    entries: List[dict] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            try:
                with open(full, "r", encoding="utf-8", errors="strict") as fh:
                    entries.append({"path": rel, "content": fh.read()})
            except (OSError, UnicodeDecodeError) as exc:
                entries.append({"path": rel, "error": f"{type(exc).__name__}"})
    return name, entries
