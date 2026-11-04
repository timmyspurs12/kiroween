"""NecroSpec cross-file data understanding (Milestone 4).

Builds an evidence-backed model of CALL USING argument → receiving-parameter
relationships between statically identified programs, plus a copybook
declaration index.

Architecture boundaries (unchanged from Milestone 3):
  * CALL is outside the frozen program grammar, so CALL sites and the
    PROCEDURE DIVISION USING lists of non-subset programs are read by a
    fixed-format source-evidence scan (content area cols 8-72, comment
    lines skipped, statement windows capped) — never by altering the
    grammar. Programs within the frozen subset keep parser-backed
    interfaces (higher confidence, recorded as such).
  * Declarations in non-subset programs and copybooks are read by a
    declaration scan of the same kind; multi-line entries and unsupported
    clauses (REDEFINES, OCCURS, ...) are recorded as unsupported rather
    than interpreted. Parsed declarations always take precedence when
    available.
  * Correspondence between caller arguments and receiving parameters is
    POSITIONAL only — names are never used to infer correspondence.
  * An argument without an explicit BY marker is recorded as BY REFERENCE
    with explicit=false (standard COBOL defaulting); BY CONTENT / BY VALUE
    are recorded when written.
  * Relationship statuses: "established", "incomplete" (positional
    correspondence exists but counts differ), "unresolved" (dynamic or
    unresolved target), "unsupported" (scanned shape not interpretable).
    Nothing here proves a CALL path executes; this is static source
    structure only.

All codes are [EXT] agent-stable extensions and reuse the existing
Diagnostic model (classification, finding_id, detail, evidence).
"""
import re
from typing import Dict, List, Optional, Tuple

from .ast_build import expand_pic
from .lexer import RESERVED_WORDS
from .diagnostics import (Diagnostic, LAYER_SEMANTIC, SEVERITY_INFO,
                          SEVERITY_WARNING, _SEVERITY_CLASSIFICATION)
from .project import _MAX_STATEMENT_WINDOW, _content, _indicator_ok

# ---- stable cross-file diagnostic codes ([EXT]) -------------------------
XFD_ARG_COUNT_MISMATCH = "XFD_ARG_COUNT_MISMATCH"
XFD_PARAM_SIZE_MISMATCH = "XFD_PARAM_SIZE_MISMATCH"
XFD_PARAM_DECL_UNRESOLVED = "XFD_PARAM_DECL_UNRESOLVED"
XFD_PARAM_DECL_AMBIGUOUS = "XFD_PARAM_DECL_AMBIGUOUS"

from . import diagnostics as _diagmod  # noqa: E402

_diagmod.HINTS.update({
    XFD_ARG_COUNT_MISMATCH:
        "Make the CALL USING argument list match the receiving program's "
        "PROCEDURE DIVISION USING parameters in number and order.",
    XFD_PARAM_SIZE_MISMATCH:
        "Align the caller argument's PICTURE/group size with the receiving "
        "parameter, or document why the size difference is intended; with "
        "BY REFERENCE the callee reads and writes the caller's storage "
        "using the receiver's layout.",
    XFD_PARAM_DECL_UNRESOLVED:
        "Ensure the receiving parameter is declared in the receiver's "
        "LINKAGE SECTION (directly or via a COPY included in the project).",
    XFD_PARAM_DECL_AMBIGUOUS:
        "Qualify the argument (item OF group) or rename one of the "
        "duplicate declarations so the passed item is unambiguous.",
})

XFD_ASSUMPTIONS = [
    {
        "id": "positional-args",
        "topic": "CALL USING correspondence",
        "detail": ("Caller arguments correspond to receiving parameters by "
                   "position only; identifiers are never used to infer "
                   "correspondence or business meaning."),
    },
    {
        "id": "by-reference-default",
        "topic": "Passing style default",
        "detail": ("A CALL USING argument without an explicit BY marker is "
                   "recorded as BY REFERENCE with explicit=false, per "
                   "standard COBOL defaulting."),
    },
    {
        "id": "scanned-declarations",
        "topic": "Scanned declarations",
        "detail": ("Declarations in non-subset programs and copybooks are "
                   "read by a fixed-format source scan, not the frozen "
                   "grammar; single-line entries only, and unsupported "
                   "clauses (REDEFINES, OCCURS, ...) are recorded as "
                   "unsupported instead of interpreted."),
    },
    {
        "id": "copybooks-not-integrated",
        "topic": "Copybook declarations are indexed, not integrated",
        "detail": ("Copybook declarations are associated with copying "
                   "programs for cross-file inspection; per-file semantic "
                   "analysis still does not see them (no textual COPY "
                   "expansion)."),
    },
    {
        "id": "static-structure-only",
        "topic": "Static structure only",
        "detail": ("Cross-file mappings describe source structure; no "
                   "claim is made that a CALL path executes at run time."),
    },
]

_WORD = r"[A-Za-z][A-Za-z0-9-]*"
_CALL_RE = re.compile(
    r"CALL\s+(?:\"(?P<lit>[^\"]*)\"|(?P<ident>%s))" % _WORD, re.IGNORECASE)
_PROC_DIV_RE = re.compile(
    r"PROCEDURE\s+DIVISION(?:\s+USING\s+(?P<params>[^.]*))?",
    re.IGNORECASE)
_SECTION_RE = re.compile(
    r"^(WORKING-STORAGE|LINKAGE|FILE|LOCAL-STORAGE)\s+SECTION\b",
    re.IGNORECASE)
_ENTRY_RE = re.compile(
    r"^\s*(?P<level>\d{1,2})\s+(?P<name>%s)\s*(?P<rest>[^.]*)\.?\s*$" % _WORD)
_PIC_RE = re.compile(r"\bPIC(?:TURE)?\s+(?:IS\s+)?(?P<pic>[A-Za-z0-9()]+)",
                     re.IGNORECASE)
_USAGE_COMP3_RE = re.compile(r"\b(?:COMP-3|COMPUTATIONAL-3|PACKED-DECIMAL)\b",
                             re.IGNORECASE)
_USAGE_DISPLAY_RE = re.compile(r"\bDISPLAY\b", re.IGNORECASE)
_USAGE_OTHER_RE = re.compile(
    r"\b(COMP|COMPUTATIONAL(?:-[1-5X])?|BINARY|INDEX|POINTER)\b",
    re.IGNORECASE)
_SIGN_SEP_RE = re.compile(
    r"SIGN\s+IS\s+(?P<pos>LEADING|TRAILING)\s+SEPARATE", re.IGNORECASE)
_VALUE_RE = re.compile(r"\bVALUE\s+(?P<val>[^.]+)", re.IGNORECASE)
_UNSUPPORTED_RE = re.compile(
    r"\b(REDEFINES|OCCURS|RENAMES|JUSTIFIED|SYNCHRONIZED|BLANK)\b",
    re.IGNORECASE)
_BY_RE = re.compile(r"\bBY\s+(?P<mode>REFERENCE|CONTENT|VALUE)\b",
                    re.IGNORECASE)
_ARG_TOKEN_RE = re.compile(r"\"(?P<lit>[^\"]*)\"|(?P<word>[^\"\s]+)")


def _diag(severity, code, message, line, col, evidence, detail=None):
    return Diagnostic(severity, code, message, line, col, LAYER_SEMANTIC,
                      evidence=evidence,
                      classification=_SEVERITY_CLASSIFICATION[severity],
                      detail=detail)


# =========================================================================
# declaration scan (non-subset programs + copybooks)
# =========================================================================

_PIC_SYM_RE = re.compile(r"([XA90SV])(?:\((\d+)\))?")


def _pic_size(pic: str, usage: Optional[str],
              sign: Optional[str]) -> Optional[int]:
    """Byte size from a PIC string using the established subset rules
    (same math as the semantic layer's validated byte lengths).
    Alphanumeric X/A pictures: one byte per character position."""
    raw = pic or ""
    m = _PIC_SYM_RE.match(raw)
    sym = m.group(1).upper() if m else ""
    if sym in ("X", "A"):
        count = 0
        for sm in _PIC_SYM_RE.finditer(raw):
            c = sm.group(1).upper()
            if c in ("X", "A"):
                count += int(sm.group(2) or 1)
        return count if count > 0 else None
    exp = expand_pic(raw)
    if exp is None:
        return None
    digits = exp["int_digits"] + exp["frac_digits"]
    if usage == "comp3":
        return (digits + 2) // 2  # sign nibble, ceil
    if exp["signed"] and sign:
        return digits + 1
    return digits


def scan_declarations(file_id: str, text: str) -> List[dict]:
    """Scan fixed-format data-description entries in the content area.
    Single-line entries only; anything the scan cannot interpret is
    recorded with an 'unsupported' marker rather than guessed."""
    lines = text.split("\n")
    section = None
    raw: List[dict] = []
    for i, line in enumerate(lines):
        if not _indicator_ok(line):
            continue
        content = _content(line)
        sm = _SECTION_RE.match(content.strip())
        if sm:
            section = sm.group(1).upper()
            continue
        em = _ENTRY_RE.match(content)
        if not em:
            continue
        rest = em.group("rest") or ""
        unsup = _UNSUPPORTED_RE.search(rest)
        pic = None
        pm = _PIC_RE.search(rest)
        if pm:
            pic = pm.group("pic").upper()
        usage = None
        if _USAGE_COMP3_RE.search(rest):
            usage = "comp3"
        elif _USAGE_DISPLAY_RE.search(rest):
            usage = "display"
        elif True:
            om = _USAGE_OTHER_RE.search(rest)
            if om:
                # unsupported USAGE: recorded, never sized (unknown
                # storage is never treated as zero)
                usage = "unsupported:" + om.group(1).upper()
        sign = None
        gm = _SIGN_SEP_RE.search(rest)
        if gm:
            sign = gm.group("pos").upper()
        value = None
        vm = _VALUE_RE.search(rest)
        if vm:
            value = vm.group("val").strip()[:40]
        raw.append({
            "file": file_id,
            "name": em.group("name"),
            "level": int(em.group("level")),
            "section": section,
            "line": i + 1,
            "col": 8 + (len(content) - len(content.lstrip())),
            "picture": pic,
            "usage": usage,
            "sign": sign,
            "value": value,
            "terminated": content.rstrip().endswith("."),
            "unsupported_clause": unsup.group(1).upper() if unsup else None,
            "text": content.strip()[:80],
        })

    # hierarchy + sizes (deterministic stack build, same rules as parser)
    out: List[dict] = []
    stack: List[dict] = []
    for e in raw:
        while stack and stack[-1]["level"] >= e["level"]:
            stack.pop()
        e["children"] = []
        e["parent"] = stack[-1]["name"] if stack else None
        if stack:
            stack[-1]["children"].append(e)
        else:
            out.append(e)
        stack.append(e)

    def size_of(e: dict) -> Optional[int]:
        if e["unsupported_clause"]:
            return None
        if e["children"]:
            total = 0
            for c in e["children"]:
                cs = size_of(c)
                if cs is None:
                    return None
                total += cs
            return total
        if e["picture"] is None:
            return None
        return _pic_size(e["picture"], e["usage"], e["sign"])

    def finalize(entries: List[dict]) -> None:
        for e in entries:
            e["byte_length"] = size_of(e)
            e["origin"] = "scanned"
            finalize(e["children"])
    finalize(out)
    return out


def _flatten(entries: List[dict]) -> List[dict]:
    out: List[dict] = []

    def walk(es):
        for e in es:
            out.append(e)
            walk(e["children"])
    walk(entries)
    return out


# =========================================================================
# CALL-site and PROCEDURE DIVISION USING scans
# =========================================================================

def _statement_window(lines: List[str], start: int,
                      anchor_col: int) -> Tuple[str, List[Tuple[int, int, str]]]:
    """Collect statement text from (start, anchor_col) to the first period,
    within a bounded line window. Returns the joined text and per-token
    mapping support: [(line_no, offset_in_stmt, line_text)] so tokens can be
    located back to source lines."""
    parts: List[Tuple[int, str]] = []
    j = start
    ended = False
    while j < len(lines) and len(parts) <= _MAX_STATEMENT_WINDOW:
        if j == start:
            seg = _content(lines[j])[anchor_col:]
        else:
            if not _indicator_ok(lines[j]):
                j += 1
                continue
            seg = _content(lines[j])
        if j > start:
            parts.append((j, seg))
        else:
            parts.append((j, seg))
        if "." in seg:
            ended = True
            seg = seg.split(".", 1)[0]
            parts[-1] = (j, seg)
            break
        j += 1
    # join with offsets: map each token to its source line
    pieces: List[str] = []
    mapping: List[Tuple[int, int, str]] = []  # (line, stmt_offset, line_text)
    off = 0
    for idx, (lineno, seg) in enumerate(parts):
        if idx > 0:
            pieces.append(" ")
            off += 1
        mapping.append((lineno, off, seg))
        pieces.append(seg)
        off += len(seg)
    return "".join(pieces), mapping, ended


def _locate(mapping, stmt_off: int) -> Tuple[int, int]:
    for lineno, off, seg in mapping:
        if off <= stmt_off < off + len(seg) + 1:
            # column within the original line's content area
            return lineno + 1, 8 + (stmt_off - off)
    return (mapping[0][0] + 1, 8) if mapping else (None, None)


def scan_calls(file_id: str, text: str) -> List[dict]:
    """Scan CALL statements: target (literal or identifier), USING argument
    list with passing styles and exact token locations."""
    lines = text.split("\n")
    calls: List[dict] = []
    for i, line in enumerate(lines):
        if not _indicator_ok(line):
            continue
        content = _content(line)
        m = re.search(r"\bCALL\b", content, re.IGNORECASE)
        if not m:
            continue
        stmt, mapping, ended = _statement_window(lines, i, m.start())
        tm = _CALL_RE.match(stmt)
        if not tm:
            continue
        target = (tm.group("lit") if tm.group("lit") is not None
                  else tm.group("ident")).upper()
        form = "literal" if tm.group("lit") is not None else "identifier"
        rest = stmt[tm.end():]
        args: List[dict] = []
        um = re.search(r"\bUSING\b", rest, re.IGNORECASE)
        if um:
            arg_region = rest[um.end():]
            passing = "by reference"
            explicit = False
            for tok in _ARG_TOKEN_RE.finditer(arg_region):
                if tok.group("lit") is not None:
                    word = tok.group("lit")
                    is_literal = True
                else:
                    word = tok.group("word") or ""
                    is_literal = False
                upper = word.upper()
                # a COBOL reserved word cannot be an argument (USER_IDENT
                # excludes reserved words), so it terminates the USING list
                if not is_literal:
                    if upper == "BY":
                        continue
                    mm = re.fullmatch(r"(REFERENCE|CONTENT|VALUE)",
                                      upper)
                    if mm:
                        passing = "by " + mm.group(1).lower()
                        explicit = True
                        continue
                    if upper in RESERVED_WORDS:
                        break
                stmt_off = um.end() + tok.start()
                ln, col = _locate(mapping, stmt_off)
                args.append({
                    "name": word,
                    "form": ("literal" if is_literal else "identifier"),
                    "passing": passing,
                    "passing_explicit": explicit,
                    "line": ln,
                    "col": col,
                })
        ln, col = _locate(mapping, 0)
        calls.append({
            "file": file_id,
            "target": target,
            "target_form": form,
            "args": args,
            "line": i + 1,
            "col": col,
            "terminated": ended,
            "text": _content(lines[i]).strip()[:80],
        })
    return calls


def scan_proc_using(file_id: str, text: str) -> Optional[dict]:
    """Scan `PROCEDURE DIVISION [USING params].` for non-subset programs.
    Returns {params: [{name, line, col}], line} or None when absent."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if not _indicator_ok(line):
            continue
        content = _content(line)
        m = _PROC_DIV_RE.search(content)
        if not m:
            continue
        params: List[dict] = []
        if m.group("params"):
            region = m.group("params")
            base_off = m.start("params")
            for tok in re.finditer(_WORD, region):
                params.append({
                    "name": tok.group(0).upper(),
                    "line": i + 1,
                    "col": 8 + base_off + tok.start(),
                })
        return {"params": params, "line": i + 1,
                "text": content.strip()[:80]}
    return None


# =========================================================================
# cross-file analysis
# =========================================================================

def _copybook_associations(edges: List[dict]) -> Dict[str, List[dict]]:
    """program -> [{copybook, via}] for resolved COPY edges, including
    nested copybook->copybook inclusion (cycle-guarded, chains recorded)."""
    direct: Dict[str, List[Tuple[str, str]]] = {}
    for e in edges:
        if e["kind"] == "copy" and e["resolution"] == "resolved" and e["to"]:
            if e.get("form") == "replacing":
                # COPY REPLACING: text-replaced names cannot be
                # established, so this copybook contributes nothing
                continue
            direct.setdefault(e["from"], []).append((e["to"], "direct"))
            # copybooks including copybooks
            direct.setdefault(e["to"], [])  # ensure key exists
    assoc: Dict[str, List[dict]] = {}

    def collect(root: str) -> List[dict]:
        """DFS from one file over resolved COPY edges: every reachable
        copybook with its chain, cycle-guarded, first (shortest) chain
        kept, self never included."""
        out: List[dict] = []
        seen_keys = set()

        def dfs(node: str, chain: Tuple[str, ...], visited: frozenset):
            for (cb, _) in direct.get(node, []):
                if cb in visited or cb == root:
                    continue
                entry = {"copybook": cb,
                         "via": "nested" if chain else "direct",
                         "chain": list(chain + (cb,))}
                key = (cb, tuple(entry["chain"]))
                if key not in seen_keys:
                    seen_keys.add(key)
                    out.append(entry)
                dfs(cb, chain + (cb,), visited | {cb})
        dfs(root, (), frozenset({root}) if root else frozenset())
        return out

    for root in sorted(direct):
        entries = collect(root)
        entries.sort(key=lambda a: (len(a["chain"]), a["copybook"]))
        assoc[root] = entries
    return assoc


def _parsed_tree(result: dict, file_id: str) -> List[dict]:
    """Symbols tree of a parsed program in scanned-entry shape
    (hierarchy preserved; origins marked parsed)."""
    def conv(e: dict) -> dict:
        usage = e.get("usage")
        if usage not in (None, "comp3", "display"):
            usage = "unsupported:%s" % usage
        return {
            "file": file_id,
            "name": e["name"],
            "level": e.get("level"),
            "section": e.get("section"),
            "line": e.get("line"),
            "col": e.get("col"),
            "picture": e.get("picture"),
            "usage": usage,
            "sign": e.get("sign"),
            "value": e.get("value"),
            "byte_length": e.get("byte_length"),
            "origin": "parsed",
            "unsupported_clause": None,
            "children": [conv(c) for c in (e.get("children") or [])],
            "text": None,
        }
    return [conv(root) for root in (result.get("symbols") or [])]


def collect_declarations(files: List[dict], contents: Dict[str, str],
                         edges: List[dict],
                         per_file: Dict[str, dict]) -> dict:
    """Declaration trees + flat index + COPY associations for the whole
    project (shared by cross-file mapping and the logical data model).
    trees: file -> declaration tree roots (parsed when analyzed, scanned
    otherwise); decls: file -> flat {NAME: entry}; assoc: program ->
    associated copybooks (REPLACING excluded); replacing: program ->
    copybooks included with COPY REPLACING (no declarations)."""
    trees: Dict[str, List[dict]] = {}
    decls: Dict[str, Dict[str, dict]] = {}
    for fid in sorted(contents):
        pf = per_file.get(fid) or {}
        if pf.get("status") == "analyzed" and pf.get("result"):
            roots = _parsed_tree(pf["result"], fid)
        else:
            roots = scan_declarations(fid, contents[fid])
        trees[fid] = roots
        decls[fid] = {d["name"].upper(): d for d in _flatten(roots)}
    assoc = _copybook_associations(edges)
    replacing: Dict[str, List[dict]] = {}
    for e in edges:
        if (e["kind"] == "copy" and e["resolution"] == "resolved"
                and e["to"] and e.get("form") == "replacing"):
            replacing.setdefault(e["from"], [])
            if e["to"] not in replacing[e["from"]]:
                replacing[e["from"]].append(e["to"])
    for k in replacing:
        replacing[k].sort()
    by_ident = {}
    for roots in trees.values():
        for d in _flatten(roots):
            by_ident[(d["file"], d["name"].upper(), d.get("line"),
                      d.get("col"))] = d
    # programs that COPY the same copybook more than once (declaration
    # insertion must happen exactly once)
    copy_counts: Dict[Tuple[str, str], int] = {}
    for e in edges:
        if (e["kind"] == "copy" and e["resolution"] == "resolved"
                and e["to"] and e.get("form") != "replacing"):
            key = (e["from"], e["to"])
            copy_counts[key] = copy_counts.get(key, 0) + 1
    dupe_copies: Dict[str, List[str]] = {}
    for (frm, to), n in copy_counts.items():
        if n > 1:
            dupe_copies.setdefault(frm, []).append(to)
    for k in dupe_copies:
        dupe_copies[k].sort()
    return {"trees": trees, "decls": decls, "assoc": assoc,
            "replacing": replacing, "by_ident": by_ident,
            "dupe_copies": dupe_copies}


def analyze_cross_file(files: List[dict], contents: Dict[str, str],
                       edges: List[dict],
                       per_file: Dict[str, dict],
                       rel: Optional[dict] = None,
                       models: Optional[dict] = None,
                       ) -> Tuple[dict, List[Diagnostic]]:
    """Build the cross-file section (interfaces, mappings, copybook
    declarations) and its findings. Deterministic. When `models` (the
    logical per-program data models) are supplied, argument/parameter
    declarations resolve through them: ambiguity is reported, never
    silently resolved by first match."""
    findings: List[Diagnostic] = []
    by_id = {f["file_id"]: f for f in files}
    programs = sorted(f["file_id"] for f in files if f["kind"] == "program")
    copybooks = sorted(f["file_id"] for f in files if f["kind"] == "copybook")

    if rel is None:
        rel = collect_declarations(files, contents, edges, per_file)
    decls = rel["decls"]
    assoc = rel["assoc"]

    def resolve_decl(fid: str, name: str) -> Tuple[Optional[dict],
                                                   Optional[dict]]:
        """(decl_ref, ambiguity) via the logical model when available."""
        if models is not None and fid in models:
            from necro.logical import resolve_name
            r = resolve_name(models[fid], name)
            if r["status"] == "resolved":
                d = _decl_ref(decls.get(fid, {}).get(name.upper()))
                if d is None:
                    for a in assoc.get(fid, []):
                        d = _decl_ref(decls.get(a["copybook"], {})
                                      .get(name.upper()))
                        if d is not None:
                            break
                if d is not None:
                    d = dict(d)
                    d["decl_id"] = r["candidates"][0]["decl_id"]
                    d["origin_kind"] = r["candidates"][0]["origin"]
                    d["via_copybooks"] = \
                        r["candidates"][0]["via_copybooks"]
                return d, None
            if r["status"] == "ambiguous":
                return None, {"candidates": r["candidates"]}
            return None, None
        # legacy first-match fallback (no logical models supplied)
        d = decls.get(fid, {}).get(name.upper())
        if d:
            return _decl_ref(d), None
        for a in assoc.get(fid, []):
            d = decls.get(a["copybook"], {}).get(name.upper())
            if d:
                return _decl_ref(d), None
        return None, None

    def lookup_decl(fid: str, name: str) -> Optional[dict]:
        d = decls.get(fid, {}).get(name.upper())
        if d:
            return d
        # fall back to declarations from associated copybooks (deterministic
        # order; first match wins and its defining file is recorded)
        for a in assoc.get(fid, []):
            d = decls.get(a["copybook"], {}).get(name.upper())
            if d:
                return d
        return None

    # ---- interfaces --------------------------------------------------------
    interfaces: Dict[str, dict] = {}
    for fid in programs:
        pf = per_file.get(fid) or {}
        result = pf.get("result") if pf.get("status") == "analyzed" else None
        if result:
            params = [{"name": p, "line": None, "col": None}
                      for p in (result["ast"]["procedure_division"]["using"] or [])]
            origin = "parsed"
        else:
            scanned = scan_proc_using(fid, contents[fid])
            params = scanned["params"] if scanned else []
            origin = "scanned"
        param_rows = []
        for p in params:
            d, amb = resolve_decl(fid, p["name"])
            row = {
                "name": p["name"],
                "line": p["line"],
                "col": p["col"],
                "declaration": d,
            }
            if amb is not None:
                row["ambiguous_candidates"] = amb["candidates"]
            param_rows.append(row)
        interfaces[fid] = {
            "file": fid,
            "origin": origin,
            "params": param_rows,
            "copybooks": assoc.get(fid, []),
        }

    # ---- mappings -----------------------------------------------------------
    call_scans: Dict[str, List[dict]] = {}
    for fid in programs:
        if per_file.get(fid, {}).get("status") != "analyzed":
            call_scans[fid] = scan_calls(fid, contents[fid])

    mappings: List[dict] = []
    for e in edges:
        if e["kind"] != "call":
            continue
        base = {
            "from": e["from"], "to": e["to"], "target": e["target"],
            "line": e["line"], "col": e["col"], "text": e["text"],
        }
        if e["resolution"] != "resolved":
            mappings.append({**base, "status": "unresolved",
                             "reason": e["resolution"], "positions": []})
            continue
        receiver = e["to"]
        args = []
        for c in call_scans.get(e["from"], []):
            if c["target"] == e["target"] and c["line"] == e["line"]:
                args = c["args"]
                break
        params = interfaces.get(receiver, {}).get("params", [])
        n = max(len(args), len(params))
        positions = []
        pos_statuses = []
        for idx in range(n):
            arg = args[idx] if idx < len(args) else None
            prm = params[idx] if idx < len(params) else None
            if arg is None:
                positions.append({
                    "position": idx + 1, "status": "unmatched-parameter",
                    "receiver": {"name": prm["name"], "line": prm["line"],
                                 "col": prm["col"]},
                    "receiver_decl": prm["declaration"],
                })
                pos_statuses.append("incomplete")
                continue
            if prm is None:
                positions.append({
                    "position": idx + 1, "status": "unmatched-argument",
                    "caller": arg,
                })
                pos_statuses.append("incomplete")
                continue
            a_decl, a_amb = resolve_decl(e["from"], arg["name"])
            if a_amb is not None:
                findings.append(_diag(
                    SEVERITY_WARNING, XFD_PARAM_DECL_AMBIGUOUS,
                    (f"CALL argument {arg['name']} at {e['from']} line "
                     f"{e['line']} matches {len(a_amb['candidates'])} "
                     f"declarations in {e['from']}'s effective model; the "
                     f"passed item cannot be established without "
                     f"qualification."),
                    e["line"], e["col"],
                    "Candidates: " + "; ".join(
                        f"{c['source_file']}:L{c['line']} ({c['origin']})"
                        for c in a_amb["candidates"]),
                    detail={"caller_file": e["from"],
                            "receiver_file": receiver,
                            "caller_item": arg["name"],
                            "candidates": a_amb["candidates"]}))
                pos_statuses.append("incomplete")
            r_decl = prm["declaration"]
            row = {
                "position": idx + 1,
                "status": "established",
                "caller": arg,
                "caller_decl": a_decl,
                "caller_ambiguous_candidates":
                    (a_amb or {}).get("candidates"),
                "receiver": {"name": prm["name"], "line": prm["line"],
                             "col": prm["col"]},
                "receiver_decl": r_decl,
            }
            # representation comparison only with both sizes established
            a_size = a_decl.get("byte_length") if a_decl else None
            r_size = (r_decl or {}).get("byte_length")
            row["size_caller"] = a_size
            row["size_receiver"] = r_size
            if a_size is not None and r_size is not None and a_size != r_size:
                row["size_status"] = "mismatch"
                pos_statuses.append("incomplete")
                findings.append(_diag(
                    SEVERITY_WARNING, XFD_PARAM_SIZE_MISMATCH,
                    (f"CALL {e['target']} at {e['from']} line {e['line']}: "
                     f"argument {arg['name']} occupies {a_size} byte(s) but "
                     f"receiving parameter {prm['name']} occupies "
                     f"{r_size} byte(s) — with "
                     f"{arg['passing']} passing the callee accesses the "
                     f"caller's storage using the receiver's layout."),
                    e["line"], e["col"],
                    f"Caller: {e['from']}:{arg['line'] if arg else '?'} "
                    f"({(a_decl or {}).get('origin')} declaration); "
                    f"receiver: {receiver}:{(prm['line'])} "
                    f"({(r_decl or {}).get('origin')} declaration); "
                    f"{arg['passing']}"
                    + (" (explicit)" if arg.get("passing_explicit")
                       else " (default, not written)"),
                    detail={"caller_file": e["from"],
                            "receiver_file": receiver,
                            "caller_item": arg["name"],
                            "receiver_item": prm["name"],
                            "caller_bytes": a_size,
                            "receiver_bytes": r_size,
                            "passing": arg["passing"]}))
            else:
                row["size_status"] = ("equal" if a_size is not None
                                      and r_size is not None else "unknown")
            if r_decl is None:
                findings.append(_diag(
                    SEVERITY_INFO, XFD_PARAM_DECL_UNRESOLVED,
                    (f"Receiving parameter {prm['name']} of {receiver} has "
                     f"no declaration found in the project (directly or via "
                     f"copybooks)."),
                    e["line"], e["col"],
                    f"Receiver {receiver} param {prm['name']} at line "
                    f"{prm['line']}; no matching declaration in the "
                    f"declaration index.",
                    detail={"receiver_file": receiver,
                            "receiver_item": prm["name"]}))
                pos_statuses.append("incomplete")
            positions.append(row)
        status = ("established" if all(s == "established"
                                       for s in pos_statuses)
                  else "incomplete")
        if len(args) != len(params):
            findings.append(_diag(
                SEVERITY_WARNING, XFD_ARG_COUNT_MISMATCH,
                (f"CALL {e['target']} at {e['from']} line {e['line']} passes "
                 f"{len(args)} argument(s) but {receiver} declares "
                 f"{len(params)} parameter(s)."),
                e["line"], e["col"],
                f"Caller arguments at {e['from']}:{e['line']} "
                f"({', '.join(a['name'] for a in args) or 'none'}); "
                f"receiver parameters at {receiver} "
                f"({', '.join(p['name'] for p in params) or 'none'})",
                detail={"caller_file": e["from"], "receiver_file": receiver,
                        "argument_count": len(args),
                        "parameter_count": len(params)}))
        mappings.append({**base, "status": status,
                         "reason": None, "positions": positions})

    # order deterministically
    mappings.sort(key=lambda m: (m["from"], m["line"], m["target"]))
    findings.sort(key=lambda d: (d.code, d.line is None, d.line or 0,
                                 d.col or 0))

    status_counts = {"established": 0, "incomplete": 0, "unresolved": 0}
    for m in mappings:
        status_counts[m["status"]] += 1

    cross_file = {
        "schema_note": "cross-file section (project schema v2)",
        "interfaces": {fid: interfaces[fid] for fid in sorted(interfaces)},
        "mappings": mappings,
        "copybook_declarations": {
            cb: [{"name": d["name"], "level": d["level"],
                  "picture": d["picture"], "usage": d["usage"],
                  "byte_length": d["byte_length"], "line": d["line"],
                  "col": d["col"],
                  "unsupported_clause": d["unsupported_clause"]}
                 for d in sorted(decls.get(cb, {}).values(),
                                 key=lambda x: (x["line"], x["col"]))]
            for cb in copybooks
        },
        "assumptions": XFD_ASSUMPTIONS,
        "coverage": {
            "call_edges": sum(1 for e in edges if e["kind"] == "call"),
            "mappings_total": len(mappings),
            "mappings_established": status_counts["established"],
            "mappings_incomplete": status_counts["incomplete"],
            "mappings_unresolved": status_counts["unresolved"],
            "interfaces_documented": len(interfaces),
            "copybooks_indexed": len(copybooks),
        },
    }
    return cross_file, findings


def _decl_ref(d: Optional[dict]) -> Optional[dict]:
    if not d:
        return None
    return {
        "file": d.get("file"),
        "name": d["name"],
        "level": d.get("level"),
        "section": d.get("section"),
        "line": d.get("line"),
        "col": d.get("col"),
        "picture": d.get("picture"),
        "usage": d.get("usage"),
        "byte_length": d.get("byte_length"),
        "origin": d.get("origin"),
        "unsupported_clause": d.get("unsupported_clause"),
    }
