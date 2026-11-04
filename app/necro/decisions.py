"""NecroSpec decision-path analysis (Milestone 7).

Builds an evidence-backed decision structure over the M6 operation and
condition models, for BOTH analysis paths:

  * parsed (frozen-subset) programs: decisions come from the parser's
    IF AST nodes — actual nesting, branch statement lists and spans.
    The frozen grammar is not touched.
  * non-subset programs: the source-evidence scanner tracks IF / ELSE /
    END-IF scoping line by line, with inline statements on control
    lines attributed by their column ranges (shared splitter with the
    sentence scanner). Statements inside EVALUATE bodies and unterminated
    IF scopes are never promoted to established decisions.

A decision record answers: which condition is evaluated, which operands
participate, which operations belong to THEN and to ELSE (if the source
has an ELSE — none is ever invented), how decisions nest, where the
branches converge, and which supported operation follows the decision.
Summaries are source-backed descriptions only; no business meaning is
inferred and no runtime reachability is claimed.
"""
import hashlib
import re
from typing import Dict, List, Optional, Tuple

from .dataflow import (_TRANSFER_RE, parse_if_line, parse_tail_line)
from .project import _content, _indicator_ok


def _decision_id(program: str, line, col) -> str:
    basis = "dec|%s|%s|%s" % (program, line, col)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


# =========================================================================
# scanner path
# =========================================================================

def scan_decisions(file_id: str, text: str) -> Tuple[
        List[dict], List[dict], Dict[int, List[dict]], List[dict],
        set, List[dict]]:
    """Scan IF / ELSE / END-IF decision structure.

    Returns (conditions, decisions, guards_by_line, guard_spans,
    suppressed_lines, unsupported).

    conditions  — same record shape as the M6 condition scan.
    decisions   — one record per END-IF-terminated IF, with branch
                  membership (by line ranges, resolved against the
                  operation list by the caller), nesting and convergence
                  evidence.
    guards_by_line — block-statement guard attribution (M6 contract).
    guard_spans — inline-statement guard attribution by column range
                  ({line, col_start, col_end, cond_id, branch}).
    suppressed  — statement lines inside unsupported EVALUATE bodies.
    unsupported — EVALUATE constructs, unterminated IFs, orphan
                  ELSE/END-IF, unparseable conditions, nested inline IF.
    """
    conditions: List[dict] = []
    decisions: List[dict] = []
    guards: Dict[int, List[dict]] = {}
    spans: List[dict] = []
    suppressed: set = set()
    unsupported: List[dict] = []

    # frame: open IF awaiting END-IF
    frames: List[dict] = []

    def snapshot() -> List[dict]:
        return [{"cond_id": f["cond_id"], "branch": f["branch"],
                 "line": f["line"]} for f in frames]

    def record_inline(segments, line: int, owner_branch_frames):
        for col, seg in segments:
            for f, branch in owner_branch_frames:
                spans.append({"line": line, "col_start": col,
                              "col_end": col + len(seg),
                              "cond_id": f["cond_id"],
                              "branch": branch})

    lines = text.split("\n")
    eval_depth = 0
    i = 0
    n = len(lines)
    while i < n:
        if not _indicator_ok(lines[i]):
            i += 1
            continue
        stripped = _content(lines[i]).strip()
        line_ends = _period_at_end(stripped)

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

        m_if = re.match(r"^IF\b", stripped, re.IGNORECASE)
        if m_if:
            # a line inside an EVALUATE body is not decision evidence
            if eval_depth == 0:
                parsed = parse_if_line(stripped)
                if parsed.get("error"):
                    unsupported.append({
                        "structure": "IF condition", "file": file_id,
                        "line": i + 1, "reason": parsed["error"],
                        "text": stripped[:80]})
                else:
                    cond_id = _cond_id_for(file_id, i + 1)
                    cond = {
                        "cond_id": cond_id,
                        "program": file_id, "source_file": file_id,
                        "line": i + 1, "col": parsed["cond_col"],
                        "op": parsed["cond"]["op"],
                        "left": parsed["cond"]["left"],
                        "right": parsed["cond"]["right"],
                        "origin": "scanned",
                        "evidence": stripped[:120],
                        "status": "established",
                    }
                    conditions.append(cond)
                    # enclosing frames: this whole IF line belongs to
                    # their current branch
                    enclosing = [(f, f["branch"]) for f in frames]
                    for f in frames:
                        (f["else_lines"] if f["branch"] == "else"
                         else f["then_lines"]).add(i + 1)
                    frame = {
                        "cond_id": cond_id, "line": i + 1,
                        "branch": "then", "then_lines": {i + 1},
                        "else_lines": set(), "else_present": False,
                        "nested": [], "parent": (frames[-1] if frames
                                                 else None),
                        "evidence": stripped[:120],
                        "cond": cond,
                    }
                    frames.append(frame)
                    record_inline(parsed["then"], i + 1,
                                  [(frame, "then")] + enclosing)
                    if parsed["else"]:
                        # inline ELSE on the IF line: the ELSE keyword is
                        # part of this line, so flip the frame branch now
                        frame["branch"] = "else"
                        frame["else_present"] = True
                        frame["else_lines"].add(i + 1)
                    record_inline(parsed["else"], i + 1,
                                  [(frame, "else")] + enclosing)
                    # continuation segments belong to the enclosing
                    # scope, not to this new decision
                    if parsed.get("endif_col") is not None:
                        # END-IF on the same line: scope closes here
                        top = frames.pop()
                        finalized = _finalize_decision(file_id, top,
                                                       i + 1)
                        decisions.append(finalized)
                        if top["parent"] is not None:
                            top["parent"]["nested"].append(finalized)
                    record_inline(parsed["cont"], i + 1, enclosing)
            i += 1
            continue

        m_else = re.match(r"^ELSE\b", stripped, re.IGNORECASE)
        if m_else:
            if eval_depth == 0:
                if not frames:
                    unsupported.append({
                        "structure": "ELSE", "file": file_id,
                        "line": i + 1,
                        "reason": "ELSE without an open IF; branch not "
                                  "attributable",
                        "text": stripped[:80]})
                else:
                    top = frames[-1]
                    top["branch"] = "else"
                    top["else_present"] = True
                    top["else_lines"].add(i + 1)
                    enclosing = [(f, f["branch"]) for f in frames]
                    segs = parse_tail_line(stripped, "ELSE")
                    record_inline(segs, i + 1, enclosing)
            i += 1
            continue

        m_endif = re.match(r"^END-IF\b", stripped, re.IGNORECASE)
        if m_endif:
            if eval_depth == 0:
                if not frames:
                    unsupported.append({
                        "structure": "END-IF", "file": file_id,
                        "line": i + 1,
                        "reason": "END-IF without an open IF",
                        "text": stripped[:80]})
                else:
                    top = frames.pop()
                    finalized = _finalize_decision(file_id, top, i + 1)
                    # nested records are emitted flat (deterministic
                    # listing) while parent ids keep the hierarchy
                    decisions.append(finalized)
                    if top["parent"] is not None:
                        top["parent"]["nested"].append(finalized)
                    # continuation segments on the END-IF line belong to
                    # the enclosing scope's current branch
                    enclosing = [(f, f["branch"]) for f in frames]
                    segs = parse_tail_line(stripped, "END-IF")
                    record_inline(segs, i + 1, enclosing)
            i += 1
            continue

        m_verb = re.match(
            r"^(MOVE|COMPUTE|ADD|SUBTRACT|MULTIPLY|DIVIDE)\b", stripped,
            re.IGNORECASE)
        if m_verb and eval_depth > 0:
            suppressed.add(i + 1)
            i += 1
            continue
        if m_verb and frames:
            guards[i + 1] = snapshot()
            top = frames[-1]
            (top["else_lines"] if top["branch"] == "else"
             else top["then_lines"]).add(i + 1)
            i += 1
            continue

        if _TRANSFER_RE.match(stripped) and not re.match(
                r"^GOBACK\b", stripped, re.IGNORECASE):
            # recorded by the sentence scanner's problem list as well;
            # here it just must not close or alter decision scopes
            pass
        if line_ends:
            # sentence period closes all open IF scopes (COBOL rule):
            # those decisions stay unsupported — missing END-IF
            for f in frames:
                unsupported.append({
                    "structure": "unterminated IF", "file": file_id,
                    "line": f["line"],
                    "reason": "IF scope closed by a sentence period "
                              "without END-IF; branch scope not "
                              "established as a decision path",
                    "text": f["evidence"][:80]})
            frames.clear()
        i += 1

    for f in frames:
        unsupported.append({
            "structure": "unterminated IF", "file": file_id,
            "line": f["line"],
            "reason": "IF scope never closed by END-IF or a sentence "
                      "period; guard scope not established",
            "text": f["evidence"][:80]})
    return conditions, decisions, guards, spans, suppressed, unsupported


def _cond_id_for(program: str, line: int) -> str:
    basis = "cond|%s|%s|%s" % (program, line, 8)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def _period_at_end(stripped: str) -> bool:
    quote = None
    i = 0
    last = -1
    while i < len(stripped):
        ch = stripped[i]
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "." and (i + 1 == len(stripped)
                            or stripped[i + 1] in " \t"):
            last = i
        i += 1
    return last >= 0


def _finalize_decision(file_id: str, frame: dict, end_line: int) -> dict:
    return {
        "decision_id": _decision_id(file_id, frame["line"], 8),
        "program": file_id,
        "source_file": file_id,
        "line": frame["line"],
        "col": 8,
        "origin": "scanned",
        "condition_id": frame["cond_id"],
        "has_else": frame["else_present"],
        "then_lines": sorted(frame["then_lines"]),
        "else_lines": sorted(frame["else_lines"]),
        "nested_decisions": [c["decision_id"] for c in frame["nested"]],
        "parent_decision": (_decision_id(file_id, frame["parent"]["line"],
                                         8)
                            if frame["parent"] is not None else None),
        "end_line": end_line,
        "convergence": None,          # resolved against operations later
        "status": "established",
        "evidence": frame["evidence"],
    }


# =========================================================================
# parsed path
# =========================================================================

def decisions_from_ast(result: dict, file_id: str,
                       conditions: List[dict],
                       ops: List[dict]) -> List[dict]:
    """Decision records from the parser's IF AST (actual nesting and
    spans). Conditions and operations come from the M6 extraction and
    are referenced by id — nothing is re-parsed."""
    cond_by_span = {(c["line"], c["col"]): c["cond_id"]
                    for c in conditions}
    op_by_span = {(o["type"], o["line"], o["col"]): o["op_id"]
                  for o in ops}
    decisions: List[dict] = []

    def op_ids_in(stmts: List[dict]) -> List[str]:
        out = []
        for st in stmts:
            key = (st.get("type", "").upper(), st["span"]["line"],
                   st["span"]["col"])
            oid = op_by_span.get(key)
            if oid:
                out.append(oid)
        return out

    def walk(stmts: List[dict], parent: Optional[dict]) -> List[dict]:
        out: List[dict] = []
        for idx, st in enumerate(stmts):
            if st.get("type") != "If":
                continue
            cond_id = cond_by_span.get((st["span"]["line"],
                                        st["span"]["col"]))
            if cond_id is None:
                continue
            dec = {
                "decision_id": _decision_id(file_id, st["span"]["line"],
                                            st["span"]["col"]),
                "program": file_id,
                "source_file": file_id,
                "line": st["span"]["line"],
                "col": st["span"]["col"],
                "origin": "parsed",
                "condition_id": cond_id,
                "has_else": bool(st.get("else")),
                "then_ops": op_ids_in(st.get("then") or []),
                "else_ops": op_ids_in(st.get("else") or []),
                "nested_decisions": [],
                "parent_decision": parent["decision_id"] if parent
                else None,
                "end_line": max([s["span"]["line"]
                                 for s in (st.get("then") or [])
                                 + (st.get("else") or [])]
                                or [st["span"]["line"]]),
                "convergence": None,
                "status": "established",
                "evidence": "IF at line %d" % st["span"]["line"],
            }
            # convergence: the next statement in the same statement list
            nxt = stmts[idx + 1] if idx + 1 < len(stmts) else None
            if nxt is not None and nxt.get("type") != "If":
                oid = op_by_span.get((nxt["type"].upper(),
                                      nxt["span"]["line"],
                                      nxt["span"]["col"]))
                if oid:
                    dec["convergence"] = {
                        "kind": "operation", "op_id": oid,
                        "line": nxt["span"]["line"],
                        "evidence": "branches converge; %s at line %d "
                                    "follows the decision"
                                    % (nxt["type"].upper(),
                                       nxt["span"]["line"]),
                    }
            if parent is not None:
                parent["nested_decisions"].append(dec["decision_id"])
            out.append(dec)
            # nested decision records are emitted flat (deterministic
            # listing) while parent ids keep the hierarchy navigable
            out.extend(walk(st.get("then") or [], dec))
            out.extend(walk(st.get("else") or [], dec))
        return out

    flat: List[dict] = []
    for sentence in (result["ast"]["procedure_division"].get("sentences")
                     or []):
        flat.extend(walk(sentence.get("statements") or [], None))
    return flat


# =========================================================================
# branch membership, convergence, sequence, summaries
# =========================================================================

def assign_branches(decisions: List[dict], ops: List[dict],
                    guard_spans: Optional[List[dict]] = None) -> None:
    """Scanner path: assign each operation to the INNERMOST decision
    that controls it — inline statements via their guard spans (column
    ranges), block statements via branch line ranges. Parsed decisions
    carry explicit op ids and are left untouched."""
    guard_spans = guard_spans or []
    scanned = [d for d in decisions if d["origin"] == "scanned"]
    by_cond = {d["condition_id"]: d for d in scanned}
    for d in scanned:
        d["then_ops"] = []
        d["else_ops"] = []
    for o in sorted(ops, key=lambda x: (x["line"], x["col"])):
        cands = []
        # inline statements: guard spans are the precise evidence
        for sp in guard_spans:
            if (sp["line"] == o["line"] and sp["col_start"] is not None
                    and sp["col_start"] <= (o["col"] or 0) < sp["col_end"]
                    and sp["cond_id"] in by_cond):
                cands.append((by_cond[sp["cond_id"]], sp["branch"]))
        if cands:
            d, branch = max(cands, key=lambda t: t[0]["line"])
        else:
            for d in scanned:
                if o["line"] in d["then_lines"]:
                    cands.append((d, "then"))
                elif o["line"] in d["else_lines"]:
                    cands.append((d, "else"))
            if not cands:
                continue
            d, branch = max(cands, key=lambda t: t[0]["line"])
        (d["else_ops"] if branch == "else" else d["then_ops"]).append(
            o["op_id"])


def resolve_convergence(decisions: List[dict], ops: List[dict],
                        parsed: bool) -> None:
    """Scanner path: the first supported operation after END-IF is the
    convergence point (operations are in source order)."""
    if parsed:
        return
    ordered = sorted(ops, key=lambda x: (x["line"], x["col"]))
    for d in decisions:
        if d["origin"] != "scanned":
            continue
        following = [o for o in ordered if o["line"] > d["end_line"]]
        if following:
            o = following[0]
            d["convergence"] = {
                "kind": "operation", "op_id": o["op_id"],
                "line": o["line"],
                "evidence": "branches converge after END-IF at L%d; "
                            "%s at line %d follows the decision"
                            % (d["end_line"], o["type"], o["line"]),
            }
        else:
            d["convergence"] = {
                "kind": "scope-end", "op_id": None,
                "line": d["end_line"],
                "evidence": "branches converge after END-IF at L%d; "
                            "no supported operation follows the "
                            "decision" % d["end_line"],
            }


def build_summaries(decisions: List[dict], conditions: List[dict],
                    ops_by_id: Dict[str, dict]) -> None:
    """Evidence-only decision summaries: condition text, per-branch
    operation descriptions with the values they write, and the following
    operation. No business meaning is inferred."""
    cond_by_id = {c["cond_id"]: c for c in conditions}

    def side_label(x: dict) -> str:
        if x.get("kind") == "identifier":
            return x.get("name", "?")
        return x.get("text", "?")

    def op_desc(op_id: Optional[str]) -> Optional[str]:
        if not op_id:
            return None
        o = ops_by_id.get(op_id)
        if not o:
            return None
        writes = [t.get("name") or t.get("text") for t in
                  o.get("receivers", [])]
        desc = "%s at L%d" % (o["type"], o["line"])
        if writes:
            desc += " writes " + ", ".join(str(w) for w in writes)
        return desc

    for d in decisions:
        c = cond_by_id.get(d["condition_id"])
        cond_str = None
        if c:
            # parsed rows carry left_operand/right_operand; scanned
            # rows the lighter left/right — both are source evidence
            left = c.get("left") or c.get("left_operand") or {}
            right = c.get("right") or c.get("right_operand") or {}
            cond_str = "%s %s %s" % (side_label(left), c["op"],
                                     side_label(right))
        then = [t for t in (op_desc(oid) for oid in d["then_ops"])
                if t]
        els = ([t for t in (op_desc(oid) for oid in d["else_ops"])
                if t] if d["has_else"] else None)
        conv = None
        if d["convergence"] and d["convergence"]["kind"] == "operation":
            conv = op_desc(d["convergence"]["op_id"])
        d["summary"] = {
            "condition": cond_str,
            "then": then,
            "else": els,
            "after": conv,
        }
