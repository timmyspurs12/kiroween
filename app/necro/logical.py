"""NecroSpec logical program data model + copybook-aware semantics (M5).

Makes established copybook declarations available to the programs that
COPY them, WITHOUT textual expansion and WITHOUT touching the frozen
grammar/lexer/parser:

  * A program's effective declarations = its own declarations (parsed
    when the program is in the frozen subset, scanned otherwise) plus
    the declarations of directly and nested-included copybooks — but
    only where the COPY relationship was established against project
    files (never by name matching alone, never from ambiguous or
    missing references, never for COPY REPLACING, whose rewritten names
    cannot be established).
  * Every logical declaration keeps full provenance: original source
    file, line, column, origin ("program" | "copybook"), the COPY
    chain that brought it in, and an established / partial / unsupported
    status. This is not a fully expanded compiler symbol table.
  * Name resolution is by exact name and (where written) OF/IN
    qualification through parent groups. Duplicate names are never
    merged and never resolved by "first match": an unqualified or
    under-qualified reference to several candidates is reported
    ambiguous with its candidate evidence.
  * Semantic participation: for programs outside the frozen subset the
    parser cannot establish operations, so a narrowly-scoped
    source-evidence scanner reads one statement shape — MOVE src TO
    dst… — in the fixed content area and applies exactly the capacity /
    precision / sign / SPACES-to-numeric rules of the layer-5 engine
    (same thresholds, same codes, same severities, same shared hints).
    No other verb is interpreted. Findings involving a copybook-origin
    receiver cite the receiver's ORIGINAL copybook location, never an
    invented location in the consuming program.

All of this is project-mode analysis only; the single-file envelope and
per-file results are unchanged.
"""
import hashlib
import re
from typing import Dict, List, Optional, Tuple

from .ast_build import expand_pic
from .diagnostics import (Diagnostic, LAYER_SEMANTIC, SEVERITY_INFO,
                          SEVERITY_WARNING, _SEVERITY_CLASSIFICATION)
from .project import _content, _indicator_ok
from .semantic import (SEM_MOVE_SPACES_TO_NUMERIC, SEM_PRECISION_LOSS,
                       SEM_SIGN_DISCARD, SEM_TRUNCATION_HIGH)

# ---- stable copybook-aware diagnostic codes ([EXT]) ---------------------
XFS_REF_AMBIGUOUS = "XFS_REF_AMBIGUOUS"

XFS_ASSUMPTIONS = [
    {
        "id": "logical-model-not-symbol-table",
        "topic": "Logical data model",
        "detail": ("Effective declarations combine program source and "
                   "established COPY associations with provenance; this is "
                   "not a fully expanded COBOL compiler symbol table and "
                   "no text is expanded."),
    },
    {
        "id": "move-shape-only",
        "topic": "Scanned statement shape",
        "detail": ("For programs outside the frozen subset, semantic "
                   "participation is limited to MOVE statements read by a "
                   "fixed-format source scan; other verbs are not "
                   "interpreted and are not claimed as analysed."),
    },
    {
        "id": "no-replacing-integration",
        "topic": "COPY REPLACING excluded",
        "detail": ("Copybooks included with COPY REPLACING keep their "
                   "dependency edge but contribute no declarations, "
                   "because text-replaced names cannot be established."),
    },
    {
        "id": "unknown-usage-sizes",
        "topic": "Unknown storage",
        "detail": ("Declarations with unsupported USAGE (COMP, BINARY, "
                   "...) or unsupported clauses (REDEFINES, OCCURS, ...) "
                   "get no byte size and never contribute one; unknown "
                   "storage is never treated as zero."),
    },
]

_WORD = r"[A-Za-z][A-Za-z0-9-]*"
_MOVE_RE = re.compile(r"^MOVE\b", re.IGNORECASE)
# data-manipulating verbs whose effects cannot be established by this
# scanner; their statements are recorded as unsupported, never silently
# omitted (conditional bodies are outside the scanner's scope entirely)
_DATA_VERBS = re.compile(
    r"^(COMPUTE|ADD|SUBTRACT|MULTIPLY|DIVIDE|SET|INSPECT|STRING|"
    r"UNSTRING|INITIALIZE)\b", re.IGNORECASE)
# a token is a (possibly OF/IN-qualified) identifier or any other
# non-space run; qualified identifiers must not be split apart
_TOKEN_RE = re.compile(
    r"[A-Za-z][A-Za-z0-9-]*(?:\s+(?:OF|IN)\s+[A-Za-z][A-Za-z0-9-]*)?"
    r"|[^\s]+", re.IGNORECASE)
_TO_SPLIT_RE = re.compile(r"\s+TO\s+", re.IGNORECASE)
_QUALIFIED_RE = re.compile(
    r"^(?P<name>%s)\s+(?:OF|IN)\s+(?P<parent>%s)$" % (_WORD, _WORD),
    re.IGNORECASE)
_IDENT_RE = re.compile(r"^%s$" % _WORD)
_NUMERIC_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
_STRING_RE = re.compile(r"^\"[^\"]*\"$|^'[^']*'$")
_FIGURATIVE_RE = re.compile(r"^(SPACE|SPACES|ZERO|ZEROS|ZEROES)$",
                            re.IGNORECASE)
_FIG_UNSUPPORTED_RE = re.compile(
    r"^(HIGH-VALUES?|LOW-VALUES?|QUOTES?)$", re.IGNORECASE)


def _diag(severity, code, message, line, col, evidence, detail=None):
    return Diagnostic(severity, code, message, line, col, LAYER_SEMANTIC,
                      evidence=evidence,
                      classification=_SEVERITY_CLASSIFICATION[severity],
                      detail=detail)


# =========================================================================
# declaration status + sizing over declaration trees
# =========================================================================

def _tree_status(entry: dict) -> None:
    """Compute status / unsupported_reason / byte_length bottom-up over a
    declaration tree (scanned or parsed shape). Unknown storage is never
    treated as zero: an unsupported or unsized subordinate makes the
    group partial with no byte length."""
    kids = entry.get("children") or []
    for c in kids:
        _tree_status(c)
    # level-66/88 entries attach to an item without occupying storage;
    # they must not make the parent partial
    storage_kids = [c for c in kids if c.get("level") not in (66, 88)]
    child_bad = any(c.get("byte_length") is None or
                    c.get("status") in ("unsupported", "partial")
                    for c in storage_kids)
    if entry.get("unsupported_clause"):
        clause = entry["unsupported_clause"]
        reasons = {
            "REDEFINES": "REDEFINES clause: storage overlaps another "
                         "item; size and aliasing cannot be established",
            "OCCURS": "OCCURS clause: table stride cannot be established "
                      "without OCCURS support",
            "RENAMES": "RENAMES clause (level 66): regrouping is not "
                       "supported",
        }
        entry["status"] = "unsupported"
        entry["unsupported_reason"] = reasons.get(
            clause, f"{clause} clause is not supported")
        entry["byte_length"] = None
        return
    if entry.get("level") in (66, 88):
        entry["status"] = "unsupported"
        entry["unsupported_reason"] = (
            "condition-name (level 88); no storage of its own"
            if entry["level"] == 88 else
            "RENAMES (level 66); regrouping is not supported")
        entry["byte_length"] = None
        return
    usage = entry.get("usage")
    if usage and str(usage).startswith("unsupported:"):
        entry["status"] = "unsupported"
        entry["unsupported_reason"] = (
            "USAGE %s is not supported; storage size cannot be "
            "established" % str(usage).split(":", 1)[1])
        entry["byte_length"] = None
        return
    if storage_kids:
        if child_bad:
            entry["status"] = "partial"
            entry["unsupported_reason"] = (
                "contains unsupported or unsized subordinate items; "
                "group size cannot be established")
            entry["byte_length"] = None
            return
        total = sum(c["byte_length"] for c in storage_kids)
        entry["status"] = "established"
        entry["unsupported_reason"] = None
        entry["byte_length"] = total
        return
    # elementary
    if not entry.get("picture"):
        entry["status"] = "partial"
        entry["unsupported_reason"] = ("elementary item without an "
                                       "established PICTURE")
        entry["byte_length"] = None
        return
    from .xfile import _pic_size
    size = _pic_size(entry["picture"],
                     None if usage and usage.startswith("unsupported:")
                     else usage,
                     entry.get("sign"))
    if size is None:
        entry["status"] = "partial"
        entry["unsupported_reason"] = ("size cannot be established from "
                                       "the declared PICTURE/USAGE")
        entry["byte_length"] = None
        return
    entry["status"] = "established"
    entry["unsupported_reason"] = None
    entry["byte_length"] = size


def _decl_id(source_file: str, line, col, name: str) -> str:
    basis = "%s|%s|%s|%s" % (source_file, line, col, name.upper())
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def _flatten_tree(entry: dict, program: str, origin: str,
                  chain: List[str], parent,
                  out: List[dict], seen: set) -> None:
    le = {
        "decl_id": _decl_id(entry["file"], entry["line"], entry["col"],
                            entry["name"]),
        "name": entry["name"],
        "program": program,
        "source_file": entry["file"],
        "line": entry.get("line"),
        "col": entry.get("col"),
        "origin": origin,            # "program" | "copybook"
        "via_copybooks": list(chain),  # COPY chain (empty for own source)
        "parent": (parent["name"] if isinstance(parent, dict)
                   else parent),
        "parent_id": (parent.get("decl_id")
                      if isinstance(parent, dict) else None),
        "level": entry.get("level"),
        "section": entry.get("section"),
        "picture": entry.get("picture"),
        "usage": entry.get("usage"),
        "sign": entry.get("sign"),
        "value": entry.get("value"),
        "byte_length": entry.get("byte_length"),
        "status": entry.get("status", "established"),
        "unsupported_reason": entry.get("unsupported_reason"),
        "children": [c["name"] for c in (entry.get("children") or [])],
        "text": entry.get("text"),
    }
    if le["decl_id"] in seen:
        return        # duplicate declaration insertion prevented
    seen.add(le["decl_id"])
    out.append(le)
    for c in (entry.get("children") or []):
        _flatten_tree(c, program, origin, chain, le, out, seen)


def build_logical_model(program: str, trees: Dict[str, List[dict]],
                        assoc: Dict[str, List[dict]],
                        replacing: Dict[str, List[dict]],
                        dupe_copies: Optional[Dict[str, List[str]]] = None,
                        ) -> dict:
    """Effective declarations + reference index for one program."""
    entries: List[dict] = []
    seen: set = set()
    for root in trees.get(program, []):
        _flatten_tree(root, program, "program", [], None, entries, seen)

    unsupported_structures: List[dict] = []
    for cb in sorted((dupe_copies or {}).get(program, [])):
        unsupported_structures.append({
            "structure": "duplicate copybook inclusion",
            "file": cb,
            "line": None,
            "reason": "copybook included more than once; declarations "
                      "inserted exactly once",
        })
    for a in assoc.get(program, []):
        cb = a["copybook"]
        before = len(entries)
        for root in trees.get(cb, []):
            _flatten_tree(root, program, "copybook", list(a["chain"]),
                          None, entries, seen)
        if len(entries) == before:
            unsupported_structures.append({
                "structure": "duplicate copybook inclusion",
                "file": cb,
                "line": None,
                "reason": "all declarations already present in this "
                          "program's effective model; duplicate insertion "
                          "prevented",
            })
    for cb in replacing.get(program, []):
        unsupported_structures.append({
            "structure": "COPY REPLACING",
            "file": cb,
            "line": None,
            "reason": "text-replaced names cannot be established; the "
                      "copybook contributes no declarations",
        })

    by_name: Dict[str, List[dict]] = {}
    for e in entries:
        by_name.setdefault(e["name"].upper(), []).append(e)

    # ancestor group chains for OF/IN qualification (exact parent ids)
    by_id = {e["decl_id"]: e for e in entries}
    for e in entries:
        chain: List[str] = []
        cur = e
        guard = 0
        while cur.get("parent_id") is not None and guard < 50:
            guard += 1
            parent = by_id.get(cur["parent_id"])
            if parent is None:
                break
            chain.append(parent["name"].upper())
            cur = parent
        e["ancestor_groups"] = chain

    return {
        "program": program,
        "declarations": entries,
        "index": by_name,
        "unsupported_structures": unsupported_structures,
        "associations": assoc.get(program, []),
    }


def resolve_name(model: dict, name: str,
                 parent: Optional[str] = None) -> dict:
    """Resolve a (possibly OF/IN-qualified) reference. Never picks a
    first match among several candidates."""
    cands = list(model["index"].get(name.upper(), []))
    if parent:
        p = parent.upper()
        cands = [c for c in cands if p in c.get("ancestor_groups", [])]
    if not cands:
        return {"status": "unresolved", "candidates": []}
    if len(cands) > 1:
        return {"status": "ambiguous",
                "candidates": [_ref(c) for c in cands]}
    return {"status": "resolved", "candidates": [_ref(cands[0])]}


def _ref(e: dict) -> dict:
    return {"decl_id": e["decl_id"], "name": e["name"],
            "source_file": e["source_file"], "line": e["line"],
            "col": e["col"], "origin": e["origin"],
            "via_copybooks": e["via_copybooks"],
            "byte_length": e.get("byte_length"),
            "picture": e.get("picture"), "usage": e.get("usage"),
            "status": e.get("status"), "level": e.get("level"),
            "sign": e.get("sign"), "value": e.get("value"),
            "unsupported_reason": e.get("unsupported_reason")}


# =========================================================================
# MOVE statement scan (the only interpreted verb for non-subset programs)
# =========================================================================

def _sentence(content: str) -> str:
    """Cut a sentence at the first period or floating comment outside
    string literals (quote-aware)."""
    quote = None
    i = 0
    while i < len(content):
        ch = content[i]
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "." and (i + 1 == len(content)
                            or content[i + 1] in " \t"):
            # a period terminates the sentence only when not inside a
            # numeric literal (1.234 continues the sentence)
            return content[:i]
        elif ch == "*" and i + 1 < len(content) and content[i + 1] == ">":
            return content[:i]
        i += 1
    return content


def _parse_operand(tok: str) -> dict:
    tok = tok.strip()
    m = _QUALIFIED_RE.match(tok)
    if m:
        return {"kind": "identifier", "name": m.group("name"),
                "parent": m.group("parent").upper(), "text": tok}
    if _FIGURATIVE_RE.match(tok):
        return {"kind": "figurative", "text": tok.upper()}
    if _FIG_UNSUPPORTED_RE.match(tok):
        return {"kind": "figurative-unsupported", "text": tok.upper()}
    if _IDENT_RE.match(tok):
        return {"kind": "identifier", "name": tok, "parent": None,
                "text": tok}
    if _NUMERIC_RE.match(tok):
        return {"kind": "literal", "text": tok}
    if _STRING_RE.match(tok):
        return {"kind": "literal", "text": tok}
    return {"kind": "unsupported", "text": tok}


def scan_moves(file_id: str, text: str) -> Tuple[List[dict], List[dict]]:
    """Scan `MOVE <operand> TO <dst> [dst…]` sentences in the fixed
    content area. Returns (moves, unsupported) — every non-matching
    statement is recorded with evidence, never interpreted."""
    lines = text.split("\n")
    moves: List[dict] = []
    unsupported: List[dict] = []
    for i, line in enumerate(lines):
        if not _indicator_ok(line):
            continue
        content = _content(line)
        stripped = content.strip()
        if _DATA_VERBS.match(stripped):
            verb = stripped.split(None, 1)[0].upper()
            unsupported.append({
                "structure": verb + " statement", "file": file_id,
                "line": i + 1,
                "reason": verb + " is not interpreted by the MOVE-shape "
                          "scanner; its data effects are not established",
                "text": _sentence(stripped)[:80]})
            continue
        if not _MOVE_RE.match(stripped):
            continue
        sentence = _sentence(stripped).strip()
        if not sentence:
            continue
        body = sentence[4:].strip()          # drop MOVE
        parts = _TO_SPLIT_RE.split(body, maxsplit=1)
        if len(parts) != 2:
            unsupported.append({
                "structure": "MOVE without TO", "file": file_id,
                "line": i + 1,
                "reason": "only MOVE … TO … sentences are interpreted",
                "text": sentence[:80]})
            continue
        src_tok = parts[0].strip()
        dst_toks = [d for d in _TOKEN_RE.findall(parts[1].strip()) if d]
        src = _parse_operand(src_tok)
        if src["kind"] == "unsupported":
            unsupported.append({
                "structure": "MOVE operand %r" % src.get("text", ""),
                "file": file_id, "line": i + 1,
                "reason": "operand shape cannot be interpreted "
                          "(arithmetic expressions and other operand "
                          "forms are not supported)",
                "text": sentence[:80]})
            continue
        dst_list = []
        for d in dst_toks:
            od = _parse_operand(d)
            if od["kind"] != "identifier":
                unsupported.append({
                    "structure": "MOVE receiver %r" % d,
                    "file": file_id, "line": i + 1,
                    "reason": "receiving operands must be (possibly "
                              "qualified) identifiers",
                    "text": sentence[:80]})
                continue
            dst_list.append(od)
        if dst_list:
            moves.append({
                "file": file_id, "line": i + 1,
                "col": 8 + (len(content) - len(content.lstrip())),
                "source": src, "receivers": dst_list,
                "text": sentence[:80],
            })
    return moves, unsupported


# =========================================================================
# copybook-aware semantic analysis of scanned MOVEs
# =========================================================================

def _cap_of_literal(text: str) -> Tuple[int, int, bool]:
    t = text.lstrip("+-")
    signed = text[:1] in ("+", "-")
    if "." in t:
        i, f = t.split(".", 1)
        return (len(i) or 1), len(f), signed
    return len(t), 0, signed


def _digits_of(entry: dict) -> Tuple[Optional[int], Optional[int], bool]:
    """(int_digits, frac_digits, signed) established only from a
    supported PICTURE on an established declaration — same expansion
    rules as the semantic engine."""
    if entry.get("status") != "established" or not entry.get("picture"):
        return None, None, False
    exp = expand_pic(entry["picture"])
    if exp is None:
        return None, None, False
    return exp["int_digits"], exp["frac_digits"], exp["signed"]


def analyze_program_semantics(model: dict,
                              moves: List[dict]) -> Tuple[List[dict],
                                                         List[Diagnostic]]:
    """Resolve every MOVE operand through the logical model and apply
    the layer-5 MOVE rules. Returns (reference_rows, findings).
    Findings cite the receiver's original declaration location."""
    findings: List[Diagnostic] = []
    refs: List[dict] = []
    by_id = {e["decl_id"]: e for e in model["declarations"]}

    def record(tok: dict, role: str, line: int) -> None:
        r = resolve_name(model, tok["name"], tok.get("parent"))
        row = {"name": tok["name"], "qualified_by": tok.get("parent"),
               "role": role, "statement_line": line,
               "status": r["status"]}
        if r["status"] == "resolved":
            e = by_id[r["candidates"][0]["decl_id"]]
            row.update({"source_file": e["source_file"],
                        "line": e["line"], "origin": e["origin"],
                        "decl_status": e["status"],
                        "via_copybooks": e["via_copybooks"],
                        "decl_id": e["decl_id"]})
        elif r["status"] == "ambiguous":
            row["candidates"] = r["candidates"]
            findings.append(_diag(
                SEVERITY_WARNING, XFS_REF_AMBIGUOUS,
                "Reference %s at %s line %d matches %d declarations; "
                "the intended item cannot be established without "
                "qualification." % (tok["name"], model["program"], line,
                                    len(r["candidates"])),
                line, None,
                "Candidates: " + "; ".join(
                    "%s:L%s (%s)" % (c["source_file"], c["line"],
                                     c["origin"])
                    for c in r["candidates"]),
                detail={"program": model["program"],
                        "file": model["program"],
                        "reference": tok["name"],
                        "qualified_by": tok.get("parent"),
                        "statement_line": line,
                        "candidates": r["candidates"]}))
        refs.append(row)
        return r

    for mv in moves:
        src = mv["source"]
        src_digits = src_frac = None
        src_signed = False
        src_known = False
        src_origin = None
        if src["kind"] == "literal":
            if _NUMERIC_RE.match(src["text"]):
                src_digits, src_frac, src_signed = \
                    _cap_of_literal(src["text"])
                src_known = True
        elif src["kind"] == "identifier":
            r = record(src, "sender", mv["line"])
            if r["status"] == "resolved":
                e = by_id[r["candidates"][0]["decl_id"]]
                src_origin = e
                src_digits, src_frac, src_signed = _digits_of(e)
                src_known = src_digits is not None
        elif src["kind"] == "figurative":
            if src["text"] not in ("SPACE", "SPACES", "ZERO", "ZEROS",
                                   "ZEROES"):
                # figurative recognized but no supported rule
                refs.append({"name": src["text"], "qualified_by": None,
                             "role": "sender", "statement_line": mv["line"],
                             "status": "figurative-unsupported"})
                continue
        else:
            continue

        for dst in mv["receivers"]:
            r = record(dst, "receiver", mv["line"])
            if r["status"] != "resolved":
                continue
            entry = by_id[r["candidates"][0]["decl_id"]]
            r_digits, r_frac, r_signed = _digits_of(entry)
            if src["kind"] == "figurative":
                if src["text"] in ("SPACE", "SPACES") and \
                        r_digits is not None:
                    findings.append(_move_spaces(model, mv, entry))
                continue
            if not (src_known and r_digits is not None):
                continue     # no established bound on one side: no claim
            for risk in _capacity_risks(model, mv, entry, src_digits,
                                        src_frac, src_signed, r_digits,
                                        r_frac, r_signed, src_origin):
                findings.append(risk)
    refs.sort(key=lambda x: (x["statement_line"], x["role"], x["name"]))
    return refs, findings


def _origin_note(entry: dict) -> str:
    note = ("receiver declared in %s:L%s (%s origin"
            % (entry["source_file"], entry["line"], entry["origin"]))
    if entry["via_copybooks"]:
        note += ", via " + " > ".join(entry["via_copybooks"])
    return note + ")"


def _move_spaces(model, mv, entry) -> Diagnostic:
    return _diag(
        SEVERITY_WARNING, SEM_MOVE_SPACES_TO_NUMERIC,
        "MOVE SPACES at %s line %d targets %s, which is numeric "
        "(%s) — later arithmetic would read invalid data."
        % (model["program"], mv["line"], entry["name"],
           _pic_desc(entry)),
        entry["line"], entry["col"],
        "Statement %s:L%d: %s; %s" % (model["program"], mv["line"],
                                      mv["text"], _origin_note(entry)),
        detail={"program": model["program"],
                "statement_line": mv["line"],
                "file": entry["source_file"],
                "receiver": entry["name"],
                "receiver_file": entry["source_file"],
                "receiver_line": entry["line"],
                "receiver_origin": entry["origin"],
                "via_copybooks": entry["via_copybooks"]})


def _capacity_risks(model, mv, entry, s_int, s_frac, s_signed,
                    r_int, r_frac, r_signed, src_origin):
    det = {
        "program": model["program"],
        "statement_line": mv["line"],
        "file": entry["source_file"],
        "receiver": entry["name"],
        "receiver_file": entry["source_file"],
        "receiver_line": entry["line"],
        "receiver_origin": entry["origin"],
        "via_copybooks": entry["via_copybooks"],
        "receiver_int_digits": r_int,
        "receiver_frac_digits": r_frac,
        "receiver_signed": r_signed,
        "sender_int_digits": s_int,
        "sender_frac_digits": s_frac,
        "sender_signed": s_signed,
    }
    if src_origin is not None:
        det["sender_file"] = src_origin["source_file"]
        det["sender_line"] = src_origin["line"]
        det["sender_origin"] = src_origin["origin"]
    note = _origin_note(entry)
    stmt = "Statement %s:L%d: %s" % (model["program"], mv["line"],
                                     mv["text"])
    out = []
    if s_int > r_int:
        out.append(_diag(
            SEVERITY_WARNING, SEM_TRUNCATION_HIGH,
            "MOVE at %s line %d can send %d integer digits but %s holds "
            "%d — potential high-order truncation."
            % (model["program"], mv["line"], s_int, entry["name"],
               r_int),
            entry["line"], entry["col"],
            "%s; %s; sender bound %d integer + %d fractional digits"
            % (stmt, note, s_int, s_frac), detail=dict(det)))
    if s_frac > r_frac:
        out.append(_diag(
            SEVERITY_WARNING, SEM_PRECISION_LOSS,
            "MOVE at %s line %d can send %d fractional digits but %s "
            "holds %d — potential low-order truncation."
            % (model["program"], mv["line"], s_frac, entry["name"],
               r_frac),
            entry["line"], entry["col"],
            "%s; %s; sender bound %d integer + %d fractional digits"
            % (stmt, note, s_int, s_frac), detail=dict(det)))
    if s_signed and not r_signed:
        out.append(_diag(
            SEVERITY_WARNING, SEM_SIGN_DISCARD,
            "MOVE at %s line %d can send a signed value but %s (%s) has "
            "no sign position — the sign would be discarded."
            % (model["program"], mv["line"], entry["name"],
               _pic_desc(entry)),
            entry["line"], entry["col"],
            "%s; %s" % (stmt, note), detail=dict(det)))
    return out


def _pic_desc(entry: dict) -> str:
    pic = entry.get("picture")
    desc = "PIC %s" % pic if pic else "group item"
    if entry.get("usage") == "comp3":
        desc += " COMP-3"
    return desc
