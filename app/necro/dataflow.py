"""NecroSpec statement-level data-flow analysis (Milestone 6).

Builds a deterministic, evidence-backed model of supported data
operations (MOVE, COMPUTE, ADD, SUBTRACT, MULTIPLY, DIVIDE) and their
guarding conditions (IF/ELSE/END-IF), for BOTH kinds of programs:

  * parsed (frozen-subset) programs: operations are extracted from the
    parser's statement trees — parser-backed, and the frozen grammar is
    not touched. Arithmetic capacity/precision/sign risks come from the
    existing layer-5 engine; operations link to those findings.
  * non-subset programs (COPY users, rejected at Grammar): the same
    statement shapes are read by a fixed-format source-evidence scanner
    (single-sentence scope, quote/decimal-period aware). Arithmetic
    risks reuse the layer-5 machinery verbatim — semantic.expr_cap,
    _receiver_risks, _division_zero, explain — over a name view built
    from the Milestone-5 logical model. Identical thresholds, codes,
    severities and hints; findings cite the receiver's original
    declaration location (copybook provenance preserved).

Everything unknown stays unknown: unresolvable operands, unsupported
USAGE, unsized declarations, unknown-precision DIVIDE quotients and
guard-scoped statements that the scanner cannot attribute are recorded
as unresolved/unsupported with evidence — never treated as zero, never
silently established. Static data-flow edges are source structure, not
proof of runtime execution.
"""
import hashlib
import re
from typing import Dict, List, Optional, Tuple

from .diagnostics import (Diagnostic, SEVERITY_ERROR, SEVERITY_INFO,
                          SEVERITY_WARNING)
from .logical import _FIGURATIVE_RE, scan_moves, resolve_name, _ref
from .project import _content, _indicator_ok
from .semantic import (Cap, SEM_DIVISOR_ZERO, _division_zero,
                       _is_zero_literal, _receiver_risks, explain, expr_cap)

DFA_ASSUMPTIONS = [
    {
        "id": "dataflow-not-execution",
        "topic": "Static data-flow edges",
        "detail": ("Data-flow nodes and edges are source structure; no "
                   "edge proves that an operation executes at run time."),
    },
    {
        "id": "single-sentence-scan",
        "topic": "Scanned statement scope",
        "detail": ("Scanned operations are read one sentence at a time "
                   "(verb to terminating period); statements spanning "
                   "unbounded text, EVALUATE selections and statements "
                   "whose scope cannot be established stay unsupported "
                   "with evidence."),
    },
    {
        "id": "guards-are-evidence",
        "topic": "Conditions are evidence, not control flow",
        "detail": ("IF/ELSE/END-IF associations are recorded as guard "
                   "evidence on operations; no full control-flow "
                   "reconstruction is attempted or claimed."),
    },
    {
        "id": "risk-propagation-limits",
        "topic": "Risk propagation limits",
        "detail": ("Capacity/precision/sign risks propagate only through "
                   "established declarations and operations; unknown "
                   "values are never treated as zero and risks are never "
                   "invented across unresolved relationships."),
    },
]

_WORD = r"[A-Za-z][A-Za-z0-9-]*"
_VERB_RE = re.compile(
    r"^(COMPUTE|ADD|SUBTRACT|MULTIPLY|DIVIDE|IF|EVALUATE|MOVE)\b",
    re.IGNORECASE)
_ARITH_VERBS = ("COMPUTE", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE")
_QUALIFIED_RE = re.compile(
    r"^(?P<name>%s)\s+(?:OF|IN)\s+(?P<parent>%s)$" % (_WORD, _WORD),
    re.IGNORECASE)
_IDENT_RE = re.compile(r"^%s$" % _WORD)
_NUM_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
_MAX_SCAN_LINES = 12
# a scanned statement ends at a period, or immediately before the next
# statement starter (COBOL implicit sentence termination); this is a
# documented scanner scope rule, never interpreted beyond its evidence
_STARTER_RE = re.compile(
    r"^(MOVE|COMPUTE|ADD|SUBTRACT|MULTIPLY|DIVIDE|IF|ELSE|END-IF|"
    r"EVALUATE|WHEN|END-EVALUATE|END-COMPUTE|END-ADD|END-SUBTRACT|"
    r"END-MULTIPLY|END-DIVIDE|DISPLAY|ACCEPT|CALL|CANCEL|GOBACK|"
    r"STOP|EXIT|CONTINUE|PERFORM|SET|INITIALIZE|INSPECT|STRING|"
    r"UNSTRING|OPEN|CLOSE|READ|WRITE|REWRITE|START)\b", re.IGNORECASE)


def _op_id(program: str, line, col, stype: str) -> str:
    basis = "op|%s|%s|%s|%s" % (program, line, col, stype)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def _cond_id(program: str, line, col) -> str:
    basis = "cond|%s|%s|%s" % (program, line, col)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


# =========================================================================
# name view for the layer-5 risk machinery
# =========================================================================

def build_name_view(model: dict) -> Dict[str, dict]:
    """NAME -> semantic-layer entry over ESTABLISHED logical declarations
    only. Fields mirror the parsed dictionary contract consumed by
    expr_cap/_receiver_risks/_describe."""
    from .ast_build import expand_pic
    view: Dict[str, dict] = {}
    for d in model["declarations"]:
        if d["status"] != "established" or not d.get("picture"):
            continue
        if d.get("children"):
            continue
        exp = expand_pic(d["picture"])
        if exp is None:
            continue
        usage = d.get("usage")
        view[d["name"].upper()] = {
            "name": d["name"],
            "line": d["line"],
            "picture": d["picture"],
            "usage": "COMP-3" if usage == "comp3" else "DISPLAY",
            "elementary": True,
            "signed": bool(exp["signed"]),
            "digits": exp["int_digits"] + exp["frac_digits"],
            "integer_digits": exp["int_digits"],
            "fractional_digits": exp["frac_digits"],
        }
    return view


def resolve_operand(model: dict, tok: dict) -> dict:
    """Resolve one operand token through the logical model."""
    r = resolve_name(model, tok["name"], tok.get("parent"))
    row = {"name": tok["name"], "qualified_by": tok.get("parent"),
           "resolution": r["status"]}
    if r["status"] == "resolved":
        row["decl"] = _ref(model["declarations"][
            next(i for i, d in enumerate(model["declarations"])
                 if d["decl_id"] == r["candidates"][0]["decl_id"])])
    elif r["status"] == "ambiguous":
        row["candidates"] = r["candidates"]
    return row


# =========================================================================
# sentence scanning (verb .. terminating period)
# =========================================================================

def _sentence_end_index(seg: str) -> int:
    """Index of the sentence-terminating period in a line's content, or
    -1. Quote-aware; a period ends the sentence only when followed by
    whitespace or end of text (numeric literals like 1.5 continue)."""
    quote = None
    i = 0
    while i < len(seg):
        ch = seg[i]
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "." and (i + 1 == len(seg) or seg[i + 1] in " \t"):
            return i
        elif ch == "*" and i + 1 < len(seg) and seg[i + 1] == ">":
            return i
        i += 1
    return -1


def _iter_sentences(file_id: str, text: str) -> Tuple[List[dict], List[dict]]:
    """Group content lines into sentences starting at a recognized verb.
    Returns (sentences, problems) where a sentence is
    {verb, line, col, text, lines:[(line,text)], ended}. MOVE sentences
    are included so multi-line MOVEs can be flagged; single-line MOVEs
    remain the authority of logical.scan_moves."""
    lines = text.split("\n")
    sentences: List[dict] = []
    problems: List[dict] = []
    i = 0
    n = len(lines)
    while i < n:
        if not _indicator_ok(lines[i]):
            i += 1
            continue
        stripped = _content(lines[i]).strip()
        # inline statements on control lines (IF / ELSE / END-IF) are
        # emitted as segment sentences with column positions so branch
        # attribution and evidence stay exact
        if re.match(r"^IF\b", stripped, re.IGNORECASE):
            parsed = parse_if_line(stripped)
            if parsed.get("error"):
                problems.append({
                    "structure": "inline IF", "file": file_id,
                    "line": i + 1, "reason": parsed["error"],
                    "text": stripped[:80]})
            else:
                for col, seg in (parsed["then"] + parsed["else"]
                                 + parsed["cont"]):
                    vm = _DATA_VERB_START_RE.match(seg)
                    sentences.append({
                        "verb": vm.group(1).upper(),
                        "line": i + 1, "col": col,
                        "text": seg,
                        "lines": [(i, seg)], "ended": True,
                        "inline": True})
            i += 1
            continue
        if re.match(r"^ELSE\b", stripped, re.IGNORECASE):
            for col, seg in parse_tail_line(stripped, "ELSE"):
                vm = _DATA_VERB_START_RE.match(seg)
                sentences.append({
                    "verb": vm.group(1).upper(), "line": i + 1,
                    "col": col, "text": seg,
                    "lines": [(i, seg)], "ended": True, "inline": True})
            i += 1
            continue
        if re.match(r"^END-IF\b", stripped, re.IGNORECASE):
            for col, seg in parse_tail_line(stripped, "END-IF"):
                vm = _DATA_VERB_START_RE.match(seg)
                sentences.append({
                    "verb": vm.group(1).upper(), "line": i + 1,
                    "col": col, "text": seg,
                    "lines": [(i, seg)], "ended": True, "inline": True})
            i += 1
            continue
        if _TRANSFER_RE.match(stripped):
            kw = stripped.split(None, 1)[0].upper()
            problems.append({
                "structure": kw + " transfer", "file": file_id,
                "line": i + 1,
                "reason": kw + " control transfer is outside the "
                          "supported decision structure; the "
                          "surrounding flow is not established",
                "text": stripped[:80]})
            i += 1
            continue
        m = _VERB_RE.match(stripped)
        if not m:
            i += 1
            continue
        # join continuation lines until the sentence period, the next
        # statement starter, or a scan-window cap
        parts = [(i, stripped)]
        end = _sentence_end_index(stripped)
        j = i
        while end < 0 and j + 1 < n and len(parts) < _MAX_SCAN_LINES:
            j += 1
            if not _indicator_ok(lines[j]):
                continue
            seg = _content(lines[j]).strip()
            if _STARTER_RE.match(seg) and j > i:
                j -= 1
                break
            parts.append((j, seg))
            end = _sentence_end_index(seg)
        if end >= 0:
            parts[-1] = (parts[-1][0], parts[-1][1][:end].strip())
        ended = end >= 0
        text_joined = " ".join(p[1] for p in parts if p[1]).strip()
        if not ended:
            # scope-by-next-starter produced exactly the statement lines
            # collected so far; a window overrun stays unsupported
            if j + 1 < n and len(parts) < _MAX_SCAN_LINES:
                ended = True
                if not (" ".join(p[1] for p in parts if p[1]).strip()):
                    i = j + 1
                    continue
            else:
                problems.append({
                    "structure": "unterminated %s sentence"
                                 % m.group(1).upper(),
                    "file": file_id, "line": i + 1,
                    "reason": "no sentence-ending period within the scan "
                              "window; statement not interpreted",
                    "text": text_joined[:80]})
        if ended and text_joined:
            sentences.append({
                "verb": m.group(1).upper(),
                "line": i + 1,
                "col": 8 + (len(_content(lines[i]))
                            - len(_content(lines[i]).lstrip())),
                "text": text_joined,
                "lines": parts,
                "ended": True,
                "inline": False,
            })
        i = j + 1
    return sentences, problems


# =========================================================================
# scanned arithmetic verbs
# =========================================================================

_OPERAND_TOKEN_RE = re.compile(
    r"[A-Za-z][A-Za-z0-9-]*(?:\s+(?:OF|IN)\s+[A-Za-z][A-Za-z0-9-]*)?"
    r"|[+-]?\d+(?:\.\d+)?|[^\s]", re.IGNORECASE)
_KW_SPLIT_RE = re.compile(
    r"\b(TO|FROM|GIVING|BY|INTO|REMAINDER|ROUNDED|ON|SIZE|ERROR|NOT)\b",
    re.IGNORECASE)


def _operand_token(tok: str) -> Optional[dict]:
    tok = tok.strip()
    m = _QUALIFIED_RE.match(tok)
    if m:
        return {"kind": "identifier", "name": m.group("name"),
                "parent": m.group("parent").upper(), "text": tok}
    if _IDENT_RE.match(tok):
        return {"kind": "identifier", "name": tok, "parent": None,
                "text": tok}
    if _NUM_RE.match(tok):
        return {"kind": "literal", "text": tok}
    return None


def _split_arith(body: str) -> Optional[dict]:
    """Split an arithmetic statement body into segments per COBOL
    keyword. Returns {to/from/giving/by/into/remainder: str,
    rounded: set-of-positions, size_error: bool, head: str} or None when
    the shape cannot be established."""
    segs: Dict[str, List[str]] = {}
    rounded: set = set()
    size_error = False
    current = "head"
    pos = 0
    for m in _KW_SPLIT_RE.finditer(body):
        segs.setdefault(current, []).append(body[pos:m.start()])
        kw = m.group(1).upper()
        if kw == "ON":
            rest = body[m.start():]
            if re.match(r"ON\s+SIZE\s+ERROR\b", rest, re.IGNORECASE):
                size_error = True
            pos = len(body)
            current = "__end__"
            break
        elif kw == "ROUNDED":
            rounded.add(current)
        elif kw == "NOT":
            # NOT ON SIZE ERROR — recorded as guarded too; the guarded
            # branch's statements are outside operand scope either way
            rest = body[m.start():]
            if re.match(r"NOT\s+ON\s+SIZE\s+ERROR\b", rest,
                        re.IGNORECASE):
                pos = len(body)
                current = "__end__"
                break
            return None
        elif kw in ("TO", "FROM", "GIVING", "BY", "INTO", "REMAINDER"):
            current = kw.lower()
        pos = m.end()
    if current != "__end__":
        segs.setdefault(current, []).append(body[pos:])
    out = {}
    for k, v in segs.items():
        out[k] = " ".join(" ".join(v).split())
    out["rounded"] = rounded
    out["size_error"] = size_error
    return out


def _operand_list(seg: str) -> Optional[List[dict]]:
    toks = _OPERAND_TOKEN_RE.findall(seg)
    out = []
    for t in toks:
        ot = _operand_token(t)
        if ot is None:
            return None
        out.append(ot)
    return out


def _targets(seg: str) -> Optional[List[dict]]:
    """Receiver list: NAME [ROUNDED] [NAME [ROUNDED] …]"""
    toks = _OPERAND_TOKEN_RE.findall(seg)
    out: List[dict] = []
    rounded_next = False
    for t in toks:
        up = t.upper()
        if up == "ROUNDED":
            if out:
                out[-1]["rounded"] = True
            rounded_next = False
            continue
        ot = _operand_token(t)
        if ot is None or ot["kind"] != "identifier":
            return None
        ot["rounded"] = rounded_next
        rounded_next = False
        out.append(ot)
    return out


def _move_op_from_segment(file_id: str, s: dict) -> Optional[dict]:
    """Operation record for an inline MOVE segment (IF/ELSE/END-IF
    lines). Reuses the logical scanner's operand parsing."""
    from .logical import _TOKEN_RE, _TO_SPLIT_RE, _parse_operand
    body = re.sub(r"^MOVE\b", "", s["text"], count=1,
                  flags=re.IGNORECASE).strip()
    parts = _TO_SPLIT_RE.split(body, maxsplit=1)
    if len(parts) != 2:
        return None
    src = _parse_operand(parts[0].strip())
    if src["kind"] in ("unsupported", "figurative-unsupported"):
        return None
    receivers = []
    for tok in _TOKEN_RE.findall(parts[1].strip()):
        od = _parse_operand(tok)
        if od["kind"] != "identifier":
            return None
        receivers.append(od)
    if not receivers:
        return None
    return {
        "op_id": None, "program": file_id, "source_file": file_id,
        "line": s["line"], "col": s["col"], "type": "MOVE",
        "origin": "scanned", "status": "partial",
        "source_operands": [{"role": "source", "kind": src["kind"],
                             **({"name": src["name"],
                                 "parent": src.get("parent")}
                                if src["kind"] == "identifier"
                                else {"text": src.get("text")})}],
        "receivers": [{"name": t["name"], "parent": t.get("parent"),
                       "rounded": False} for t in receivers],
        "options": {"rounded": False, "size_error": False,
                    "mode": None, "giving": False, "remainder": None},
        "guards": [], "evidence": s["text"][:120], "expression": None,
    }


def scan_arithmetic(file_id: str, text: str,
                    suppressed: Optional[set] = None) -> Tuple[
                        List[dict], List[dict]]:
    """Scan supported arithmetic statement shapes. Returns (raw_ops,
    unsupported). Lines inside unsupported constructs (EVALUATE bodies)
    are excluded via `suppressed`. Raw ops carry parsed structure;
    resolution and semantic analysis happen against the logical model
    later."""
    sentences, problems = _iter_sentences(file_id, text)
    unsupported = list(problems)
    ops: List[dict] = []
    for s in sentences:
        if suppressed and s["line"] in suppressed:
            continue
        verb = s["verb"]
        body = s["text"]
        body = re.sub(r"^%s\b" % verb, "", body, count=1,
                      flags=re.IGNORECASE).strip()
        if verb == "MOVE":
            if s.get("inline"):
                op = _move_op_from_segment(file_id, s)
                if op is None:
                    unsupported.append({
                        "structure": "inline MOVE", "file": file_id,
                        "line": s["line"],
                        "reason": "inline MOVE operands cannot be "
                                  "interpreted",
                        "text": s["text"][:80]})
                else:
                    ops.append(op)
                continue
            if len(s["lines"]) == 1:
                continue      # scan_moves is the MOVE authority
            # a MOVE sentence spanning lines is not interpreted
            unsupported.append({
                "structure": "multi-line MOVE", "file": file_id,
                "line": s["line"],
                "reason": "MOVE sentences spanning lines are not "
                          "interpreted by the line-based MOVE scanner",
                "text": s["text"][:80]})
            continue
        if verb in ("IF", "EVALUATE"):
            continue          # handled by scan_conditions
        if verb == "COMPUTE":
            op = _parse_compute(file_id, s, body)
        elif verb == "ADD":
            op = _parse_add(file_id, s, body)
        elif verb == "SUBTRACT":
            op = _parse_subtract(file_id, s, body)
        elif verb == "MULTIPLY":
            op = _parse_multiply(file_id, s, body)
        else:
            op = _parse_divide(file_id, s, body)
        if op is None:
            unsupported.append({
                "structure": "%s statement" % verb, "file": file_id,
                "line": s["line"],
                "reason": "statement shape cannot be established by the "
                          "scanner; operands and receivers not "
                          "interpreted",
                "text": s["text"][:80]})
            continue
        ops.append(op)
    return ops, unsupported


def _base_op(file_id, s, verb) -> dict:
    return {
        "op_id": None,          # assigned after guards are known
        "program": file_id,
        "source_file": file_id,
        "line": s["line"], "col": s["col"],
        "type": verb,
        "origin": "scanned",
        "status": "unsupported",
        "source_operands": [],
        "receivers": [],
        "options": {"rounded": False, "size_error": False,
                    "mode": None, "giving": False, "remainder": None},
        "guards": [],
        "evidence": s["text"][:120],
        "expression": None,
    }


def _parse_compute(file_id, s, body: str) -> Optional[dict]:
    m = re.match(r"^(?P<dst>%s)\s*(?P<rounded>ROUNDED\s*)?=\s*(?P<expr>.+)$"
                 % _WORD, body, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    op = _base_op(file_id, s, "COMPUTE")
    expr_src = m.group("expr").strip()
    # explicit scope terminators belong to the sentence, not the
    # expression
    expr_src = re.sub(
        r"\bEND-(COMPUTE|ADD|SUBTRACT|MULTIPLY|DIVIDE|IF|EVALUATE)\b.*$",
        "", expr_src, flags=re.IGNORECASE | re.DOTALL).strip()
    ose = re.search(r"\bNOT\s+ON\s+SIZE\s+ERROR\b|\bON\s+SIZE\s+ERROR\b",
                    expr_src, re.IGNORECASE)
    if ose:
        expr_src = expr_src[:ose.start()].strip()
        op["options"]["size_error"] = True
    op["options"]["rounded"] = bool(m.group("rounded"))
    expr = parse_expression(expr_src)
    if expr is None:
        op["status"] = "unsupported"
        op["unsupported_reason"] = ("expression cannot be parsed "
                                    "(supported: + - * / **, parentheses, "
                                    "identifiers, numeric literals)")
        op["expression"] = {"text": expr_src[:80], "supported": False}
        return op
    op["expression"] = {"text": expr_src[:120], "supported": True,
                        "ast": expr}
    op["source_operands"] = _expr_operands(expr)
    op["receivers"] = [{"name": m.group("dst"), "rounded":
                        bool(m.group("rounded"))}]
    op["status"] = "partial"
    return op


def _expr_operands(node: dict) -> List[dict]:
    out: List[dict] = []

    def walk(n, role):
        if n["kind"] == "identifier":
            out.append({"role": role, "kind": "identifier",
                        "name": n["name"], "parent": n.get("parent")})
        elif n["kind"] == "literal":
            out.append({"role": role, "kind": "literal", "text": n["text"]})
        elif n["kind"] == "binary":
            walk(n["left"], role)
            walk(n["right"], role)
    walk(node, "operand")
    return out


_EXPR_TOKEN_RE = re.compile(
    r"(?P<ident>[A-Za-z][A-Za-z0-9-]*)"
    r"|(?P<num>\d+(?:\.\d+)?)"
    r"|(?P<op>\*\*|[+\-*/()])")


def parse_expression(src: str) -> Optional[dict]:
    """Parse an arithmetic expression to a pseudo-AST compatible with
    semantic.expr_cap (kinds: identifier/literal/binary). Returns None
    when the expression uses unsupported forms."""
    toks: List[Tuple[str, str]] = []
    pos = 0
    for m in _EXPR_TOKEN_RE.finditer(src):
        if src[pos:m.start()].strip():
            return None            # unparsable gap (function call, etc.)
        if m.group("ident"):
            if m.group("ident").upper() in ("SPACE", "SPACES", "ZERO",
                                            "ZEROS", "ZEROES"):
                toks.append(("fig", m.group("ident")))
            else:
                toks.append(("ident", m.group("ident")))
        elif m.group("num"):
            toks.append(("num", m.group("num")))
        else:
            toks.append(("op", m.group("op")))
        pos = m.end()
    if src[pos:].strip():
        return None
    if not toks:
        return None
    # shunting-yard to RPN, then tree
    prec = {"+": 1, "-": 1, "*": 2, "/": 2, "**": 3}
    output: List[Tuple[str, str]] = []
    stack: List[Tuple[str, str]] = []
    prev = None
    for kind, val in toks:
        if kind in ("ident", "num", "fig"):
            output.append((kind, val))
        elif val == "(":
            stack.append(("op", "("))
        elif val == ")":
            while stack and stack[-1][1] != "(":
                output.append(stack.pop())
            if not stack:
                return None
            stack.pop()
        else:
            if val in ("+", "-") and prev is None or \
                    (prev and prev[0] == "op" and prev[1] not in (")",)):
                # unary sign
                output.append(("num", "0" if val == "+" else "u-"))
                # represent unary minus as 0 - x via synthetic tokens
                stack_op = ("op", "-") if val == "-" else None
                if stack_op:
                    stack.append(stack_op)
                prev = ("syn", val)
                continue
            while stack and stack[-1][1] != "(" and \
                    prec.get(stack[-1][1], 0) >= prec.get(val, 0):
                output.append(stack.pop())
            stack.append(("op", val))
        prev = (kind, val) if kind != "op" or val != ")" else prev
    while stack:
        if stack[-1][1] == "(":
            return None
        output.append(stack.pop())

    def is_val(t):
        return t[0] in ("ident", "num", "fig")

    st: List[dict] = []
    consumed_u = False
    for t in output:
        if t == ("num", "u-") and not is_val(t):
            continue
        if is_val(t):
            if t[0] == "ident":
                st.append({"kind": "identifier", "name": t[1]})
            elif t[0] == "fig":
                st.append({"kind": "figurative", "text": t[1].upper()})
            else:
                st.append({"kind": "literal", "text": t[1]})
        else:
            if t[1] == "-" and not consumed_u and len(st) == 1:
                # unary minus applied to a single operand
                st[-1] = {"kind": "binary", "op": "-",
                          "left": {"kind": "literal", "text": "0"},
                          "right": st[-1]}
                consumed_u = True
                continue
            if len(st) < 2:
                return None
            r = st.pop()
            l = st.pop()
            st.append({"kind": "binary", "op": t[1], "left": l,
                       "right": r})
    if len(st) != 1:
        return None
    return st[0]


def _parse_add(file_id, s, body: str) -> Optional[dict]:
    parts = _split_arith(body)
    if parts is None:
        return None
    ops_in = _operand_list(parts.get("head", ""))
    if not ops_in:
        return None
    op = _base_op(file_id, s, "ADD")
    op["options"]["size_error"] = parts["size_error"]
    receivers = []
    if parts.get("giving"):
        op["options"]["giving"] = True
        receivers = _targets(parts["giving"]) or []
    elif parts.get("to"):
        op["options"]["mode"] = "TO"
        receivers = _targets(parts["to"]) or []
    else:
        return None
    if not receivers:
        return None
    op["source_operands"] = [{"role": "operand", **o} for o in ops_in]
    if parts.get("to"):
        # ADD a TO b: b is both an implicit operand and receiver
        for t in receivers:
            op["source_operands"].append({
                "role": "operand", "kind": "identifier",
                "name": t["name"], "parent": t.get("parent")})
    op["receivers"] = [{"name": t["name"], "parent": t.get("parent"),
                        "rounded": t.get("rounded", False)
                        or "giving" in parts["rounded"]
                        or "to" in parts["rounded"]}
                       for t in receivers]
    op["status"] = "partial"
    return op


def _parse_subtract(file_id, s, body: str) -> Optional[dict]:
    parts = _split_arith(body)
    if parts is None or not parts.get("from"):
        return None
    subs = _operand_list(parts.get("head", ""))
    if not subs:
        return None
    op = _base_op(file_id, s, "SUBTRACT")
    op["options"]["size_error"] = parts["size_error"]
    op["options"]["mode"] = "FROM"
    op["source_operands"] = [{"role": "subtrahend", **o} for o in subs]
    if parts.get("giving"):
        op["options"]["giving"] = True
        mins = _operand_list(parts["from"])
        if not mins or len(mins) != 1 or mins[0]["kind"] != "identifier":
            return None
        op["source_operands"].append({"role": "minuend", **mins[0]})
        targets = _targets(parts.get("giving", "")) or []
        if not targets:
            return None
        op["receivers"] = [{"name": t["name"], "parent": t.get("parent"),
                            "rounded": t.get("rounded", False)}
                           for t in targets]
    else:
        targets = _targets(parts["from"]) or []
        if not targets:
            return None
        op["receivers"] = [{"name": t["name"], "parent": t.get("parent"),
                            "rounded": t.get("rounded", False)}
                           for t in targets]
        for t in op["receivers"]:
            op["source_operands"].append({
                "role": "minuend", "kind": "identifier",
                "name": t["name"], "parent": t.get("parent")})
    op["status"] = "partial"
    return op


def _parse_multiply(file_id, s, body: str) -> Optional[dict]:
    parts = _split_arith(body)
    if parts is None or not parts.get("by"):
        return None
    lefts = _operand_list(parts.get("head", ""))
    rights = _operand_list(parts["by"])
    if not lefts or len(lefts) != 1 or not rights:
        return None
    op = _base_op(file_id, s, "MULTIPLY")
    op["options"]["size_error"] = parts["size_error"]
    op["options"]["mode"] = "BY"
    op["source_operands"] = [{"role": "left", **lefts[0]}]
    if parts.get("giving"):
        op["options"]["giving"] = True
        op["source_operands"].append({"role": "right", **rights[0]})
        targets = _targets(parts.get("giving", "")) or []
        if not targets:
            return None
        op["receivers"] = [{"name": t["name"], "parent": t.get("parent"),
                            "rounded": t.get("rounded", False)}
                           for t in targets]
    else:
        # MULTIPLY a BY b: b receives the product
        if len(rights) != 1 or rights[0]["kind"] != "identifier":
            return None
        op["source_operands"].append({"role": "right", **rights[0]})
        op["receivers"] = [{"name": rights[0]["name"],
                            "parent": rights[0].get("parent"),
                            "rounded": "by" in parts["rounded"]}]
    op["status"] = "partial"
    return op


def _parse_divide(file_id, s, body: str) -> Optional[dict]:
    parts = _split_arith(body)
    if parts is None:
        return None
    if not parts.get("into") and not parts.get("by"):
        return None
    mode = "INTO" if parts.get("into") else "BY"
    second_seg = parts.get("into") or parts.get("by")
    firsts = _operand_list(parts.get("head", ""))
    seconds = _operand_list(second_seg)
    if not firsts or len(firsts) != 1 or not seconds:
        return None
    op = _base_op(file_id, s, "DIVIDE")
    op["options"]["size_error"] = parts["size_error"]
    op["options"]["mode"] = mode
    op["source_operands"] = [{"role": "dividend" if mode == "BY" else
                              "divisor", **firsts[0]}]
    if parts.get("giving"):
        op["options"]["giving"] = True
        op["source_operands"].append({
            "role": "dividend" if mode == "INTO" else "divisor",
            **seconds[0]})
        targets = _targets(parts.get("giving", "")) or []
        if not targets:
            return None
        op["receivers"] = [{"name": t["name"], "parent": t.get("parent"),
                            "rounded": t.get("rounded", False)}
                           for t in targets]
        if parts.get("remainder"):
            rems = _operand_list(parts["remainder"])
            if rems and len(rems) == 1 and \
                    rems[0]["kind"] == "identifier":
                op["options"]["remainder"] = rems[0]["name"]
                op["source_operands"].append({
                    "role": "remainder", **rems[0]})
    else:
        # DIVIDE a INTO b: b receives the quotient
        if len(seconds) != 1 or seconds[0]["kind"] != "identifier":
            return None
        op["source_operands"].append({"role": "dividend", **seconds[0]})
        op["receivers"] = [{"name": seconds[0]["name"],
                            "parent": seconds[0].get("parent"),
                            "rounded": ("into" if mode == "INTO"
                                        else "by") in parts["rounded"]}]
    op["status"] = "partial"
    return op


# =========================================================================
# scanned conditions (IF / ELSE / END-IF; EVALUATE recorded unsupported)
# =========================================================================

_COND_OP_RE = re.compile(
    r"^(NOT\s+)?(=|<>|<=|>=|<|>|EQUAL TO|GREATER THAN|LESS THAN)$",
    re.IGNORECASE)

# ---- inline statement segments on IF / ELSE / END-IF lines --------------

_COND_HEAD_RE = re.compile(
    r"^IF\s+(?P<left>[A-Za-z][A-Za-z0-9-]*|[-+]?\d+(?:\.\d+)?"
    r"|'[^']*'|\"[^\"]*\")\s+"
    r"(?P<not>NOT\s+)?(?P<op>=|<>|<=|>=|<|>)\s+"
    r"(?P<right>[A-Za-z][A-Za-z0-9-]*|[-+]?\d+(?:\.\d+)?"
    r"|'[^']*'|\"[^\"]*\")", re.IGNORECASE)
_DATA_VERB_START_RE = re.compile(
    r"\b(MOVE|COMPUTE|ADD|SUBTRACT|MULTIPLY|DIVIDE)\b", re.IGNORECASE)
_INLINE_NESTED_RE = re.compile(r"\bIF\b", re.IGNORECASE)
_TRANSFER_RE = re.compile(r"^(GO\s+TO|ALTER|PERFORM)\b", re.IGNORECASE)


def _find_kw_positions(seg: str, kw: str) -> int:
    """First word-boundary occurrence of kw outside string literals,
    or -1."""
    quote = None
    i = 0
    pat = re.compile(r"\b%s\b" % kw, re.IGNORECASE)
    while i < len(seg):
        ch = seg[i]
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        else:
            m = pat.match(seg, i)
            if m:
                return i
        i += 1
    return -1


def _period_position(seg: str) -> int:
    """Position of the sentence-terminating period (quote-aware, decimal
    safe), or -1."""
    quote = None
    i = 0
    while i < len(seg):
        ch = seg[i]
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "." and (i + 1 == len(seg) or seg[i + 1] in " \t"):
            return i
        elif ch == "*" and i + 1 < len(seg) and seg[i + 1] == ">":
            return i
        i += 1
    return -1


def _verb_segments(region: str, base_col: int) -> Tuple[List[Tuple[int, str]], Optional[str]]:
    """Split a text region into verb-led statement segments.
    Returns ([(col, text)], error)."""
    segs: List[Tuple[int, str]] = []
    starts = [m.start() for m in
              _DATA_VERB_START_RE.finditer(region)]
    if not starts:
        return [], None
    for idx, st in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(region)
        text = region[st:end].strip()
        if text:
            segs.append((base_col + st, text))
    return segs, None


def parse_if_line(stripped: str) -> dict:
    """Parse one content line starting with IF into its condition plus
    inline THEN / ELSE / continuation statement segments (column-
    preserving). Returns {error} when the construct cannot be
    established (e.g. nested inline IF)."""
    m = _COND_HEAD_RE.match(stripped)
    if not m:
        return {"error": "condition form cannot be established"}
    left = _cond_operand(m.group("left"))
    right = _cond_operand(m.group("right"))
    if left is None or right is None:
        return {"error": "condition form cannot be established"}
    cond = {"left": left, "right": right,
            "op": ("NOT " if m.group("not") else "") + m.group("op")}
    cond_src = stripped[m.start():m.end()]
    rest = stripped[m.end():]
    else_pos = _find_kw_positions(rest, "ELSE")
    endif_pos = _find_kw_positions(rest, "END-IF")
    period_pos = _period_position(rest)
    limit = len(rest)
    for pos in (else_pos, endif_pos, period_pos):
        if pos >= 0:
            limit = min(limit, pos)
    then_region = rest[:limit]
    result = {
        "cond": cond, "cond_text": cond_src,
        "cond_col": 8 + m.start("left"),
        "then": [], "else": [], "cont": [],
        "else_present": False, "endif_col": None,
        "error": None,
    }
    # a nested inline IF inside the THEN region cannot be branched
    # reliably on one line: refuse rather than guess
    if _INLINE_NESTED_RE.search(then_region):
        return {"error": "nested inline IF is not interpreted"}
    # all output columns use the scanner's source-column convention
    # (stripped-line offset + 8), matching inline sentence cols
    then_segs, err = _verb_segments(then_region, m.end() + 8)
    if err:
        return {"error": err}
    result["then"] = then_segs
    if else_pos >= 0:
        result["else_present"] = True
        e_limit = endif_pos if endif_pos > else_pos else \
            (period_pos if period_pos > else_pos else len(rest))
        else_region = rest[else_pos + 4:e_limit]
        if _INLINE_NESTED_RE.search(else_region):
            return {"error": "nested inline IF is not interpreted"}
        else_segs, err = _verb_segments(else_region,
                                        m.end() + else_pos + 4 + 8)
        if err:
            return {"error": err}
        result["else"] = else_segs
    if endif_pos >= 0:
        result["endif_col"] = m.end() + endif_pos + 8
        c_limit = period_pos if period_pos > endif_pos else len(rest)
        cont_region = rest[endif_pos + 6:c_limit]
        cont_segs, err = _verb_segments(cont_region,
                                        m.end() + endif_pos + 6 + 8)
        if err:
            return {"error": err}
        result["cont"] = cont_segs
    return result


def parse_tail_line(stripped: str, keyword: str) -> List[Tuple[int, str]]:
    """Inline statement segments after ELSE or END-IF at line start."""
    klen = len(keyword)
    if not stripped[:klen].upper() == keyword.upper():
        return []
    rest = stripped[klen:]
    period_pos = _period_position(rest)
    if period_pos >= 0:
        rest = rest[:period_pos]
    segs, _ = _verb_segments(rest, klen + 8)
    return segs


_COND_OPERAND_RE = re.compile(
    r"^(?P<q>%s\s+(?:OF|IN)\s+%s)(?=\s|$)|^(?P<str>\"[^\"]*\"|'[^']*')"
    r"|^(?P<ident>%s)(?=\s|$)|^(?P<num>[+-]?\d+(?:\.\d+)?)(?=\s|$)"
    % (_WORD, _WORD, _WORD), re.IGNORECASE)


def _cond_operand(tok: str) -> Optional[dict]:
    """Condition operand: identifier (possibly OF/IN-qualified), numeric
    literal, or string literal."""
    tok = tok.strip()
    if _FIGURATIVE_RE.match(tok):
        return {"kind": "figurative", "text": tok.upper()}
    m = _COND_OPERAND_RE.match(tok)
    if not m:
        return None
    if m.group("q"):
        parts = m.group("q").split()
        return {"kind": "identifier", "name": parts[0],
                "parent": parts[-1].upper(), "text": tok}
    if m.group("str"):
        return {"kind": "literal", "text": m.group("str")}
    if m.group("ident"):
        return {"kind": "identifier", "name": m.group("ident"),
                "parent": None, "text": tok}
    return {"kind": "literal", "text": m.group("num")}


def _parse_condition(src: str) -> Optional[dict]:
    toks = src.strip()
    m = re.match(
        r"^(?P<left>[^=<>]+\S)\s+(?P<not>NOT\s+)?(?P<op>=|<>|<=|>=|<|>)\s+"
        r"(?P<right>\S.*)$", toks)
    if not m:
        return None
    left = _cond_operand(m.group("left").strip())
    right = _cond_operand(m.group("right").strip())
    if left is None or right is None:
        return None
    return {"left": left, "right": right,
            "op": ("NOT " if m.group("not") else "") + m.group("op")}


def scan_conditions(file_id: str, text: str) -> Tuple[List[dict],
                                                      Dict[int, List[dict]],
                                                      List[dict], set]:
    """Scan IF/ELSE/END-IF scoping. Returns (conditions, guards_by_line,
    unsupported, suppressed_lines). Guards map a statement line to the
    open conditions with their branch. EVALUATE constructs and
    unterminated IFs are recorded unsupported; statements inside an
    EVALUATE body are suppressed (their controlling context was never
    established, so they must not appear as established operations).
    A period closes all open scopes (COBOL sentence rule)."""
    conditions: List[dict] = []
    unsupported: List[dict] = []
    guards: Dict[int, List[dict]] = {}
    suppressed: set = set()
    lines = text.split("\n")
    stack: List[dict] = []
    eval_depth = 0
    i = 0
    n = len(lines)
    while i < n:
        if not _indicator_ok(lines[i]):
            i += 1
            continue
        stripped = _content(lines[i]).strip()
        up = stripped.upper()
        # sentence boundary: line ends with a period outside quotes
        line_ends_sentence = _sentence_end_index(stripped) >= 0
        m_if = re.match(r"^IF\b", stripped, re.IGNORECASE)
        if m_if:
            cond_src = stripped[2:]
            end = _sentence_end_index(cond_src)
            cond_line = cond_src[:end].strip() if end >= 0 else cond_src
            parsed = _parse_condition(cond_line)
            if parsed is None:
                unsupported.append({
                    "structure": "IF condition", "file": file_id,
                    "line": i + 1,
                    "reason": "condition form cannot be established "
                              "(supported: operand (=|<>|<|>|<=|>=|NOT …) "
                              "operand)",
                    "text": stripped[:80]})
            else:
                cond = {
                    "cond_id": _cond_id(file_id, i + 1, 8),
                    "program": file_id, "source_file": file_id,
                    "line": i + 1, "col": 8,
                    "op": parsed["op"],
                    "left": parsed["left"], "right": parsed["right"],
                    "origin": "scanned",
                    "evidence": stripped[:120],
                    "status": "established",
                }
                conditions.append(cond)
                stack.append({"cond": cond, "branch": "then"})
                open_sentence = True
            i += 1
            continue
        if re.match(r"^ELSE\b", stripped, re.IGNORECASE):
            if stack:
                stack[-1]["branch"] = "else"
            else:
                unsupported.append({
                    "structure": "ELSE", "file": file_id, "line": i + 1,
                    "reason": "ELSE without an open IF; branch not "
                              "attributable",
                    "text": stripped[:80]})
            i += 1
            continue
        if re.match(r"^END-IF\b", stripped, re.IGNORECASE):
            if stack:
                stack.pop()
            else:
                unsupported.append({
                    "structure": "END-IF", "file": file_id, "line": i + 1,
                    "reason": "END-IF without an open IF",
                    "text": stripped[:80]})
            i += 1
            continue
        if re.match(r"^EVALUATE\b", stripped, re.IGNORECASE):
            eval_depth += 1
            unsupported.append({
                "structure": "EVALUATE", "file": file_id, "line": i + 1,
                "reason": "EVALUATE selection is not supported; subjects "
                          "and WHEN branches are not interpreted and "
                          "statements in its body are not attributed",
                "text": stripped[:80]})
            i += 1
            continue
        if re.match(r"^END-EVALUATE\b", stripped, re.IGNORECASE):
            eval_depth = max(0, eval_depth - 1)
            i += 1
            continue
        m_verb = _VERB_RE.match(stripped)
        if m_verb:
            if eval_depth > 0:
                suppressed.add(i + 1)
            elif stack:
                guards[i + 1] = [{"cond_id": e["cond"]["cond_id"],
                                  "branch": e["branch"],
                                  "line": e["cond"]["line"]}
                                 for e in stack]
        if line_ends_sentence:
            stack.clear()
        i += 1
    if stack:
        unsupported.append({
            "structure": "unterminated IF", "file": file_id,
            "line": stack[-1]["cond"]["line"],
            "reason": "IF scope never closed by END-IF or a sentence "
                      "period; guard scope not established",
            "text": stack[-1]["cond"]["evidence"][:80]})
    return conditions, guards, unsupported, suppressed


# =========================================================================
# parsed-program operations (from the frozen-grammar AST)
# =========================================================================

def _receiver_from_target(model: dict, tg: dict, role: str) -> dict:
    """Receiver row from a parsed statement TARGET dict
    ({name, rounded, span}) — not an operand node."""
    row = resolve_operand(model, {"name": tg["name"], "parent": None})
    return {"role": role, "kind": "identifier", "name": tg["name"],
            "parent": None, "rounded": bool(tg.get("rounded")),
            "span": tg.get("span"), **row}


def _operand_from_node(model: dict, node: dict, role: str) -> dict:
    kind = node.get("kind")
    if kind == "identifier":
        row = resolve_operand(model, {"name": node["name"],
                                      "parent": None})
        row.update({"role": role, "kind": "identifier",
                    "span": node.get("span")})
        return row
    if kind == "literal":
        return {"role": role, "kind": "literal", "text": node.get("text")}
    if kind == "figurative":
        return {"role": role, "kind": "figurative", "text": node.get("text")}
    if kind == "binary":
        return {"role": role, "kind": "expression"}
    return {"role": role, "kind": "unsupported"}


def _expr_string(node: dict) -> str:
    k = node.get("kind")
    if k in ("identifier", "literal", "figurative"):
        return node.get("name") or node.get("text") or ""
    if k == "binary":
        return "(%s %s %s)" % (_expr_string(node["left"]), node["op"],
                               _expr_string(node["right"]))
    return "?"


def _status_for(model: dict, op: dict) -> str:
    """established / partial / unresolved / unsupported from operand and
    receiver resolutions + declaration statuses."""
    statuses = []
    for o in op["source_operands"]:
        if o.get("kind") in ("literal", "figurative", "expression"):
            continue
        if o.get("resolution") == "unresolved":
            statuses.append("unresolved")
        elif o.get("resolution") == "ambiguous":
            statuses.append("unresolved")
        elif (o.get("decl") or {}).get("status") == "unsupported":
            statuses.append("partial")
    for t in op["receivers"]:
        if t.get("resolution") == "unresolved":
            statuses.append("unresolved")
        elif t.get("resolution") == "ambiguous":
            statuses.append("unresolved")
        elif (t.get("decl") or {}).get("status") == "unsupported":
            statuses.append("partial")
        elif (t.get("decl") or {}).get("status") == "partial":
            statuses.append("partial")
    if "unresolved" in statuses:
        return "unresolved"
    if "partial" in statuses:
        return "partial"
    return "established"


def ops_from_ast(result: dict, file_id: str, model: dict) -> Tuple[
        List[dict], List[dict]]:
    """Extract operations + conditions from a parsed program's AST,
    resolving operands through the logical model. Guards reflect the
    IF/ELSE nesting the parser established."""
    ops: List[dict] = []
    conditions: List[dict] = []

    def cond_from_ast(st: dict) -> dict:
        c = st["condition"]
        left = _operand_from_node(model, c["left"], "subject")
        right = _operand_from_node(model, c["right"], "object")
        return {
            "cond_id": _cond_id(file_id, st["span"]["line"],
                                st["span"]["col"]),
            "program": file_id, "source_file": file_id,
            "line": st["span"]["line"], "col": st["span"]["col"],
            "op": c.get("op"),
            "left_operand": left, "right_operand": right,
            "origin": "parsed",
            "evidence": "IF at line %d (%s)" % (st["span"]["line"],
                                                c.get("op")),
            "status": "established",
        }

    def walk(stmts: List[dict], guards: List[dict]) -> None:
        for st in stmts:
            t = st.get("type")
            if t == "If":
                cond = cond_from_ast(st)
                conditions.append(cond)
                guard = [{"cond_id": cond["cond_id"], "branch": "then",
                          "line": cond["line"]}]
                walk(st.get("then") or [], guards + guard)
                walk(st.get("else") or [],
                     guards + [{"cond_id": cond["cond_id"],
                                "branch": "else",
                                "line": cond["line"]}])
                continue
            if t not in ("Move", "Compute", "Add", "Subtract", "Multiply",
                         "Divide"):
                continue
            op = {
                "op_id": None,
                "program": file_id, "source_file": file_id,
                "line": st["span"]["line"], "col": st["span"]["col"],
                "type": t.upper(),
                "origin": "parsed",
                "status": "established",
                "source_operands": [],
                "receivers": [],
                "options": {"rounded": False, "size_error":
                            bool(st.get("size_error")),
                            "mode": st.get("mode") or st.get("form"),
                            "giving": bool(st.get("mode") == "GIVING"
                                           or st.get("form") == "giving"),
                            "remainder": None},
                "guards": list(guards),
                "evidence": "%s at line %d" % (t.upper(),
                                               st["span"]["line"]),
                "expression": None,
            }
            if t == "Move":
                op["source_operands"] = [
                    _operand_from_node(model, st["source"], "source")]
                op["receivers"] = [
                    _receiver_from_target(model, tg2, "receiver")
                    for tg2 in st["targets"]]
            elif t == "Compute":
                op["expression"] = {"text": _expr_string(st["expr"]),
                                    "supported": True, "ast": st["expr"]}
                op["source_operands"] = _expr_operands(st["expr"])
                op["receivers"] = [
                    _receiver_from_target(model, st["target"], "receiver")]
            elif t == "Add":
                op["source_operands"] = [
                    _operand_from_node(model, a, "operand")
                    for a in st["operands"]]
                op["receivers"] = [
                    _receiver_from_target(model, st["target"], "receiver")]
            elif t == "Subtract":
                op["source_operands"] = [
                    _operand_from_node(model, a, "subtrahend")
                    for a in st["subtrahends"]]
                if st.get("minuend") is not None:
                    op["source_operands"].append(
                        _operand_from_node(model, st["minuend"],
                                           "minuend"))
                op["receivers"] = [
                    _receiver_from_target(model, st["target"], "receiver")]
            elif t == "Multiply":
                op["source_operands"] = [
                    _operand_from_node(model, st["left"], "left"),
                    _operand_from_node(model, st["right"], "right")]
                op["receivers"] = [
                    _receiver_from_target(model, st["target"], "receiver")]
            elif t == "Divide":
                divisor, dividend = ((st["first"], st["second"])
                                     if st["mode"] == "INTO"
                                     else (st["second"], st["first"]))
                op["source_operands"] = [
                    _operand_from_node(model, divisor, "divisor"),
                    _operand_from_node(model, dividend, "dividend")]
                op["receivers"] = [
                    _receiver_from_target(model, st["target"], "receiver")]
            # resolve operand/receiver decls
            for o in op["source_operands"]:
                if o.get("kind") == "identifier":
                    o.update({k: v for k, v in resolve_operand(
                        model, {"name": o["name"],
                                "parent": o.get("parent")}).items()
                        if k in ("resolution", "decl", "candidates")})
            for tg in op["receivers"]:
                tg.update({k: v for k, v in resolve_operand(
                    model, {"name": tg["name"],
                            "parent": tg.get("parent")}).items()
                    if k in ("resolution", "decl", "candidates")})
            op["status"] = _status_for(model, op)
            ops.append(op)

    for sentence in (result["ast"]["procedure_division"].get("sentences")
                     or []):
        walk(sentence.get("statements") or [], [])
    return ops, conditions


# =========================================================================
# semantic analysis of scanned arithmetic (reuses layer-5 machinery)
# =========================================================================

def analyze_scanned_arithmetic(model: dict, ops: List[dict],
                               refs_sink: List[dict]) -> List[Diagnostic]:
    """Capacity/precision/sign/divisor-zero analysis for scanned
    arithmetic, using the layer-5 engine over the logical model."""
    view = build_name_view(model)
    by_name = view
    decls_by_id = {d["decl_id"]: d for d in model["declarations"]}
    findings: List[Diagnostic] = []
    for op in ops:
        if op["status"] == "unsupported" or op["type"] not in _ARITH_VERBS:
            continue
        if op["type"] == "COMPUTE" and \
                not (op.get("expression") or {}).get("supported"):
            continue
        # operand resolution (decl + resolution recorded on the op) and
        # reference-table rows
        for o in op["source_operands"]:
            if o.get("kind") == "identifier":
                row = resolve_operand(model, o)
                o["resolution"] = row["resolution"]
                o["decl"] = row.get("decl")
                o["candidates"] = row.get("candidates")
                refs_sink.append({
                    "name": o["name"], "qualified_by": o.get("parent"),
                    "role": "operand", "statement_line": op["line"],
                    "status": row["resolution"],
                    **({"source_file": row["decl"]["source_file"],
                        "line": row["decl"]["line"],
                        "origin": row["decl"]["origin"],
                        "decl_status": row["decl"]["status"],
                        "via_copybooks":
                        row["decl"]["via_copybooks"],
                        "decl_id": row["decl"]["decl_id"]}
                       if row.get("decl") else {}),
                    **({"candidates": row["candidates"]}
                       if "candidates" in row else {})})
        for tg in op["receivers"]:
            row = resolve_operand(model, {"name": tg["name"],
                                          "parent": tg.get("parent")})
            tg["resolution"] = row["resolution"]
            tg["decl"] = row.get("decl")
            tg["candidates"] = row.get("candidates")
            refs_sink.append({
                "name": tg["name"], "qualified_by": tg.get("parent"),
                "role": "receiver", "statement_line": op["line"],
                "status": row["resolution"],
                **({"source_file": row["decl"]["source_file"],
                    "line": row["decl"]["line"],
                    "origin": row["decl"]["origin"],
                    "decl_status": row["decl"]["status"],
                    "via_copybooks": row["decl"]["via_copybooks"],
                    "decl_id": row["decl"]["decl_id"]}
                   if row.get("decl") else {}),
                **({"candidates": row["candidates"]}
                   if "candidates" in row else {})})
        op["status"] = _status_for(model, op)
        # per-receiver risks
        for tg in op["receivers"]:
            if tg.get("resolution") != "resolved":
                continue
            decl = decls_by_id[tg["decl"]["decl_id"]]
            entry = by_name.get(tg["name"].upper())
            target = {"name": tg["name"],
                      "span": {"line": op["line"], "col": op["col"]}}
            risks: list = []
            if op["type"] == "COMPUTE":
                cap = expr_cap(op["expression"]["ast"], by_name)
                _receiver_risks("COMPUTE", op["line"], op["col"],
                                target, cap, bool(tg.get("rounded")),
                                op["options"]["size_error"], entry,
                                risks, origin=op["evidence"][:60])
                _division_zero(op["expression"]["ast"], risks,
                               {"line": op["line"], "col": op["col"]},
                               statement="COMPUTE")
            elif op["type"] == "ADD":
                caps = [expr_cap({"kind": "identifier", "name": o["name"],
                                  "span": target["span"]}, by_name)
                        if o["kind"] == "identifier"
                        else expr_cap({"kind": "literal", "text":
                                       o.get("text", "0")}, by_name)
                        for o in op["source_operands"]]
                known = [c for c in caps if not c.unknown]
                if op["options"]["size_error"]:
                    _receiver_risks("ADD", op["line"], op["col"], target,
                                    Cap(None, None, False, unknown=True),
                                    False, True, entry, risks)
                elif known and entry:
                    cap = Cap(max(c.int_d for c in known) + 1,
                              max(c.frac_d for c in known),
                              any(c.signed for c in caps))
                    _receiver_risks("ADD", op["line"], op["col"], target,
                                    cap, bool(tg.get("rounded")), False,
                                    entry, risks)
            elif op["type"] == "SUBTRACT":
                subs = [expr_cap({"kind": "identifier", "name": o["name"],
                                  "span": target["span"]}, by_name)
                        if o["kind"] == "identifier"
                        else expr_cap({"kind": "literal", "text":
                                       o.get("text", "0")}, by_name)
                        for o in op["source_operands"]
                        if o["role"] == "subtrahend"]
                mins = [expr_cap({"kind": "identifier", "name": o["name"],
                                  "span": target["span"]}, by_name)
                        for o in op["source_operands"]
                        if o["role"] == "minuend"
                        and o["kind"] == "identifier"]
                known_sub = [c for c in subs if not c.unknown]
                ints, fracs, signed = [], [], False
                for c in mins:
                    if not c.unknown:
                        ints.append(c.int_d)
                        fracs.append(c.frac_d)
                    signed = signed or c.signed
                if known_sub:
                    ints.append(max(c.int_d for c in known_sub)
                                + (len(known_sub) - 1))
                    fracs.append(max(c.frac_d for c in known_sub))
                signed = signed or any(c.signed for c in subs) or \
                    bool(subs)
                if op["options"]["size_error"]:
                    _receiver_risks("SUBTRACT", op["line"], op["col"],
                                    target,
                                    Cap(None, None, False, unknown=True),
                                    False, True, entry, risks)
                elif ints and entry:
                    _receiver_risks("SUBTRACT", op["line"], op["col"],
                                    target, Cap(max(ints), max(fracs),
                                                signed),
                                    bool(tg.get("rounded")), False,
                                    entry, risks)
            elif op["type"] == "MULTIPLY":
                caps = []
                for o in op["source_operands"]:
                    if o["role"] in ("left", "right"):
                        caps.append(expr_cap(
                            {"kind": "identifier", "name": o["name"],
                             "span": target["span"]}
                            if o["kind"] == "identifier"
                            else {"kind": "literal",
                                  "text": o.get("text", "0")}, by_name))
                lc = caps[0] if len(caps) > 0 else Cap(None, None, True,
                                                       unknown=True)
                rc = caps[1] if len(caps) > 1 else Cap(None, None, True,
                                                       unknown=True)
                if op["options"]["size_error"]:
                    _receiver_risks("MULTIPLY", op["line"], op["col"],
                                    target,
                                    Cap(None, None, False, unknown=True),
                                    False, True, entry, risks)
                elif not lc.unknown and not rc.unknown and entry:
                    _receiver_risks("MULTIPLY", op["line"], op["col"],
                                    target,
                                    Cap(lc.int_d + rc.int_d,
                                        lc.frac_d + rc.frac_d,
                                        lc.signed or rc.signed),
                                    bool(tg.get("rounded")), False,
                                    entry, risks)
            elif op["type"] == "DIVIDE":
                divisor = next((o for o in op["source_operands"]
                                if o["role"] == "divisor"), None)
                if divisor and divisor["kind"] == "literal" and \
                        _is_zero_literal({"kind": "literal",
                                          "text": divisor.get("text",
                                                              "")}):
                    risks.append(__import__("necro.semantic",
                                            fromlist=["Risk"]).Risk(
                        SEM_DIVISOR_ZERO, SEVERITY_ERROR, op["line"],
                        op["col"],
                        {"statement": "DIVIDE",
                         "mode": op["options"]["mode"],
                         "divisor_literal": "0"},
                        {"mode": op["options"]["mode"]}))
                if op["options"]["size_error"] and entry:
                    _receiver_risks("DIVIDE", op["line"], op["col"],
                                    target,
                                    Cap(None, None, False, unknown=True),
                                    bool(tg.get("rounded")), True,
                                    entry, risks)
                # quotient precision is never established: no claims
            # render + enrich + relocate to the receiver's declaration
            for risk in risks:
                diag = explain(risk)
                det = diag.detail or {}
                det.update({
                    "program": model["program"],
                    "statement_line": op["line"],
                    "statement_col": op["col"],
                    "statement_type": op["type"],
                    "op_id": op["op_id"],
                    "receiver": decl["name"],
                    "receiver_file": decl["source_file"],
                    "receiver_line": decl["line"],
                    "receiver_origin": decl["origin"],
                    "via_copybooks": decl["via_copybooks"],
                })
                diag.detail = det
                diag.line = decl["line"]
                diag.col = decl["col"]
                prov = ("receiver declared in %s:L%s (%s origin)"
                        % (decl["source_file"], decl["line"],
                           decl["origin"]))
                diag.evidence = ("%s; %s" % (diag.evidence, prov))
                findings.append(diag)
    return findings


def move_op_from_scan(model: dict, mv: dict) -> dict:
    """Convert a logical.scan_moves MOVE into an operation record
    (reuses Milestone 5's scanner — no competing MOVE implementation)."""
    src = mv["source"]
    if src["kind"] == "identifier":
        src_row = {"role": "source", "kind": "identifier",
                   "name": src["name"], "parent": src.get("parent"),
                   **{k: v for k, v in resolve_operand(model, src).items()
                      if k in ("resolution", "decl", "candidates")}}
    else:
        src_row = {"role": "source", "kind": src["kind"],
                   "text": src.get("text"), "resolution": "literal"
                   if src["kind"] == "literal" else src["kind"]}
    receivers = []
    for dst in mv["receivers"]:
        receivers.append({
            "name": dst["name"], "parent": dst.get("parent"),
            "rounded": False,
            **{k: v for k, v in resolve_operand(model, dst).items()
               if k in ("resolution", "decl", "candidates")}})
    op = {
        "op_id": None,
        "program": mv["file"], "source_file": mv["file"],
        "line": mv["line"], "col": mv["col"],
        "type": "MOVE",
        "origin": "scanned",
        "status": "partial",
        "source_operands": [src_row],
        "receivers": receivers,
        "options": {"rounded": False, "size_error": False,
                    "mode": None, "giving": False, "remainder": None},
        "guards": [],
        "evidence": mv["text"][:120],
        "expression": None,
    }
    op["status"] = _status_for(model, op)
    return op


def cross_program_links(mappings: List[dict],
                        flow_by_program: Dict[str, dict]) -> List[dict]:
    """Connect CALL USING arguments to receiving parameters at operation
    level: caller operations writing the argument, callee operations
    reading the parameter. Links where a declaration could not be
    established are recorded as unresolved — tracing stops there and
    says so."""
    links: List[dict] = []

    def op_writes(flow: dict, decl_id: str) -> List[dict]:
        return [e for e in flow["edges"]
                if e["kind"] == "receiver"
                and e["to"] == "d:" + decl_id]

    def op_reads(flow: dict, decl_id: str) -> List[dict]:
        return [e for e in flow["edges"]
                if e["kind"] == "operand"
                and e["from"] == "d:" + decl_id
                and e["to"].startswith("o:")]

    for m in mappings:
        if m.get("status") == "unresolved" or not m.get("to"):
            continue
        for pos in m.get("positions", []):
            cd = pos.get("caller_decl") or {}
            rd = pos.get("receiver_decl") or {}
            caller_flow = (flow_by_program.get(m["from"]) or {}).get(
                "graph", flow_by_program.get(m["from"]) or {"edges": []})
            callee_flow = (flow_by_program.get(m["to"]) or {}).get(
                "graph", flow_by_program.get(m["to"]) or {"edges": []})
            base = {
                "caller": m["from"], "callee": m["to"],
                "argument": pos.get("caller", {}).get("name"),
                "parameter": pos.get("receiver", {}).get("name"),
                "call": {"target": m["target"], "line": m["line"],
                         "evidence": m["text"]},
                "mapping_status": m["status"],
                "position": pos.get("position"),
            }
            if cd.get("decl_id") and rd.get("decl_id"):
                links.append({**base,
                              "status": "established",
                              "from_decl": cd["decl_id"],
                              "to_decl": rd["decl_id"],
                              "caller_writes": [
                                  {"op_id": e["from"][2:],
                                   "line": e.get("line"),
                                   "evidence": e.get("evidence")}
                                  for e in op_writes(caller_flow,
                                                     cd["decl_id"])],
                              "callee_reads": [
                                  {"op_id": e["to"][2:],
                                   "line": e.get("line"),
                                   "evidence": e.get("evidence")}
                                  for e in op_reads(callee_flow,
                                                    rd["decl_id"])],
                              })
            else:
                links.append({**base,
                              "status": "unresolved_declaration",
                              "from_decl": cd.get("decl_id"),
                              "to_decl": rd.get("decl_id"),
                              "reason": "argument or parameter "
                                        "declaration not established; "
                                        "data-flow tracing stops here",
                              "caller_writes": [],
                              "callee_reads": []})
    return links


# =========================================================================
# data-flow graph
# =========================================================================

def build_graph(program: str, model: dict, ops: List[dict],
                conditions: List[dict]) -> dict:
    nodes: List[dict] = []
    edges: List[dict] = []
    seen = set()
    for d in model["declarations"]:
        nid = "d:" + d["decl_id"]
        if nid in seen:
            continue
        seen.add(nid)
        nodes.append({"id": nid, "kind": "declaration",
                      "ref": d["decl_id"], "label": d["name"],
                      "origin": d["origin"],
                      "source_file": d["source_file"],
                      "line": d["line"]})
    for op in ops:
        oid = "o:" + (op["op_id"] or "")
        nodes.append({"id": oid, "kind": "operation", "ref": op["op_id"],
                      "label": op["type"], "origin": op["origin"],
                      "source_file": op["source_file"],
                      "line": op["line"]})
        for i, o in enumerate(op["source_operands"]):
            if o.get("kind") == "identifier" and \
                    o.get("resolution") == "resolved":
                edges.append({
                    "from": "d:" + o["decl"]["decl_id"], "to": oid,
                    "kind": "operand", "role": o.get("role"),
                    "line": op["line"],
                    "evidence": op["evidence"][:80]})
            elif o.get("kind") in ("literal", "figurative"):
                lid = "l:%s:%d" % (op["op_id"], i)
                nodes.append({"id": lid, "kind": "literal",
                              "ref": None, "label": o.get("text", ""),
                              "origin": "literal",
                              "source_file": op["source_file"],
                              "line": op["line"]})
                edges.append({"from": lid, "to": oid, "kind": "operand",
                              "role": o.get("role"), "line": op["line"],
                              "evidence": op["evidence"][:80]})
        for tg in op["receivers"]:
            if tg.get("resolution") == "resolved" and tg.get("decl"):
                edges.append({
                    "from": oid, "to": "d:" + tg["decl"]["decl_id"],
                    "kind": "receiver", "role": "writes",
                    "line": op["line"],
                    "rounded": bool(tg.get("rounded")),
                    "evidence": op["evidence"][:80]})
    for c in conditions:
        cid = "c:" + c["cond_id"]
        nodes.append({"id": cid, "kind": "condition", "ref": c["cond_id"],
                      "label": "IF %s" % c.get("op"), "origin":
                      c.get("origin"),
                      "source_file": c["source_file"], "line": c["line"]})
        for side in ("left", "right"):
            o = c.get("%s_operand" % side)
            if o and o.get("kind") == "identifier" and \
                    o.get("resolution") == "resolved":
                edges.append({"from": "d:" + o["decl"]["decl_id"],
                              "to": cid, "kind": "condition",
                              "role": side, "line": c["line"],
                              "evidence": c["evidence"][:80]})
        for op in ops:
            for g in op.get("guards", []):
                if g["cond_id"] == c["cond_id"]:
                    edges.append({"from": cid,
                                  "to": "o:" + (op["op_id"] or ""),
                                  "kind": "guard",
                                  "role": g["branch"],
                                  "line": c["line"],
                                  "evidence": c["evidence"][:80]})
    return {"nodes": nodes, "edges": edges}


# =========================================================================
# queries
# =========================================================================

def field_flow(flow: dict, decl_id: str) -> dict:
    """Answer the five data-flow questions for one declaration:
    producers (writes), consumers (reads), contributors to producers,
    guards on writes, and subsequent uses. Accepts a program's dataflow
    section (uses its graph) or a bare graph. Static structure only."""
    graph = flow.get("graph", flow)
    edges = graph["edges"]
    nodes = {n["id"]: n for n in graph["nodes"]}
    did = "d:" + decl_id
    producer_edges = [e for e in edges
                      if e["kind"] == "receiver" and e["to"] == did]
    consumer_edges = [e for e in edges
                      if e["kind"] == "operand" and e["to"].startswith("o:")
                      and any(oe["from"] == did for oe in producer_edges)
                      or (e["kind"] == "operand"
                          and e["to"].startswith("o:")
                          and e["from"] == did)]
    # distinct consumer edges: reads of this decl by any operation
    consumer_edges = [e for e in edges
                      if e["kind"] == "operand" and e["from"] == did]
    cond_edges = [e for e in edges
                  if e["kind"] == "condition" and e["from"] == did]
    producers = []
    for e in producer_edges:
        op_node = nodes.get(e["from"])
        contributors = [
            {"from": oe["from"], "label": nodes.get(oe["from"], {})
             .get("label"), "role": oe.get("role"),
             "line": oe.get("line")}
            for oe in edges
            if oe["kind"] == "operand" and oe["to"] == e["from"]]
        guards = [ge for ge in edges
                  if ge["kind"] == "guard" and ge["to"] == e["from"]]
        producers.append({
            "op_id": e["from"][2:], "label":
            (op_node or {}).get("label"),
            "line": e.get("line"), "rounded": e.get("rounded", False),
            "evidence": e.get("evidence"),
            "contributors": contributors,
            "guards": [{"cond_id": g["from"][2:], "branch": g["role"],
                        "line": g.get("line")} for g in guards],
        })
    consumers = [{
        "op_id": e["to"][2:], "label": (nodes.get(e["to"]) or {})
        .get("label"), "role": e.get("role"), "line": e.get("line"),
        "evidence": e.get("evidence")} for e in consumer_edges]
    conditions_on = [{
        "cond_id": e["to"][2:], "line": e.get("line"),
        "evidence": e.get("evidence")} for e in cond_edges]
    return {"decl_id": decl_id,
            "producers": producers,
            "consumers": consumers,
            "conditions": conditions_on,
            "note": "static source structure; not proof of runtime "
                    "execution"}
