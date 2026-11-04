"""NecroSpec rule-candidate analysis (Milestone 8).

Derives candidate business rules from the M7 decision-path model and
the M6 statement-level data-flow model. A candidate connects a
controlling condition, the data items it evaluates, the operations of
each established branch, the values those operations read and write,
established downstream uses and cross-program relationships, and the
original source evidence — with explicit unresolved elements.

A candidate is a STRUCTURE discovered in source. It is never a claim
about business intent: explanations quote only condition text, recorded
operations and resolved data items. Nothing here infers policies,
executes code, or claims complete business-rule extraction. Every
relationship reuses existing M4–M7 records by id — no second model.

Statuses:
  established_structure — condition and branch structure fully
                          established from source evidence.
  partial               — the structure is established but some
                          relevant relationship is unresolved (operand
                          resolution, operation status, argument
                          mapping).
  unsupported           — the source cannot establish a candidate
                          (condition without supported branch
                          operations, or a decision structure that
                          could not be established).
"""
import hashlib
from typing import Dict, List, Optional

from .dataflow import resolve_operand

RULE_ASSUMPTIONS = [
    {"id": "RULE_001",
     "topic": "candidates are structure, not business intent",
     "detail": "A rule candidate records source structure (a condition "
               "and the operations of its branches). It is not a "
               "statement of business intent, policy, or requirement; "
               "only a developer can decide what the rule means."},
    {"id": "RULE_002",
     "topic": "discovery is limited to established decisions",
     "detail": "Candidates derive only from M7 decisions with an "
               "established condition and at least one supported branch "
               "operation. Conditions without supported branch "
               "operations and unestablishable decision structures are "
               "recorded as unsupported, never promoted."},
    {"id": "RULE_003",
     "topic": "no numeric confidence",
     "detail": "Status classification is structural (established / "
               "partial / unsupported). No numeric confidence score is "
               "assigned because no defensible, tested methodology "
               "exists for scoring business-rule confidence from "
               "static source."},
    {"id": "RULE_004",
     "topic": "cross-program evidence stays qualified",
     "detail": "CALL USING relationships are attached only where the "
               "M4–M6 link is established; incomplete argument mappings "
               "and callees that never read a parameter keep their "
               "qualification and mark the candidate partial. Dynamic "
               "or unresolved CALLs are never attached."},
]


def _rule_id(program: str, decision_id: str) -> str:
    basis = "R|%s|%s" % (program, decision_id)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def _unsupported_id(program: str, line, structure: str) -> str:
    basis = "R|%s|U|%s|%s" % (program, line, structure)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def _label(row: dict) -> str:
    if row.get("kind") in ("literal", "figurative"):
        return row.get("text") or "?"
    return row.get("name") or "?"


def _resolve_item(model: Optional[dict], row: dict) -> dict:
    """One condition operand as a data-item row: reuse an existing
    resolution (parsed conditions carry one), resolve through the
    logical model (scanned conditions), or record the literal."""
    if row.get("kind") in ("literal", "figurative"):
        return {"kind": row["kind"], "text": row.get("text"),
                "resolution": "literal"}
    item = {"kind": "identifier", "name": row.get("name"),
            "qualified_by": row.get("parent"),
            "resolution": row.get("resolution") or "unresolved"}
    if item["resolution"] == "unresolved" and model is not None \
            and row.get("name"):
        r = resolve_operand(model, {"name": row["name"],
                                    "parent": row.get("parent")})
        item["resolution"] = r["resolution"]
        if r.get("decl"):
            item["decl"] = r["decl"]
        if r.get("candidates"):
            item["candidates"] = r["candidates"]
    if row.get("decl") and "decl" not in item:
        item["decl"] = row["decl"]
    if row.get("candidates") and "candidates" not in item:
        item["candidates"] = row["candidates"]
    return item


def _item_key(item: dict) -> tuple:
    decl = item.get("decl") or {}
    return (item.get("name") or item.get("text"),
            decl.get("decl_id") or decl.get("source_file"),
            item.get("kind"))


def _provenance(decl: Optional[dict]) -> dict:
    if not decl:
        return {}
    return {"source_file": decl.get("source_file"),
            "line": decl.get("line"),
            "origin": decl.get("origin"),
            "via_copybooks": decl.get("via_copybooks") or []}


def discover_rules(program: str, flow: dict, model: Optional[dict],
                   links: List[dict]) -> dict:
    """Build the rule-candidate section for one program from its M6/M7
    records (flow) plus the project's cross-program links."""
    decisions = flow.get("decisions") or []
    conditions = flow.get("conditions") or []
    ops = flow.get("operations") or []
    graph = flow.get("graph") or {"nodes": [], "edges": []}
    ops_by_id = {o["op_id"]: o for o in ops}
    cond_by_id = {c["cond_id"]: c for c in conditions}

    # downstream consumers per declaration (graph reads)
    node_label = {n["id"]: n.get("label") for n in graph.get("nodes", [])}
    consumers: Dict[str, List[dict]] = {}
    for e in graph.get("edges", []):
        if e["kind"] == "operand" and e["from"].startswith("d:") \
                and e["to"].startswith("o:"):
            consumers.setdefault(e["from"][2:], []).append({
                "op_id": e["to"][2:], "label": node_label.get(e["to"]),
                "line": e.get("line"), "evidence": e.get("evidence")})

    # links indexed by the operation that writes the argument
    links_by_op: Dict[str, List[dict]] = {}
    for l in links:
        if l.get("caller") != program:
            continue
        for w in l.get("caller_writes") or []:
            links_by_op.setdefault(w["op_id"], []).append(l)

    def op_ref(op_id: str) -> Optional[dict]:
        o = ops_by_id.get(op_id)
        if not o:
            return None
        return {"op_id": op_id, "type": o["type"], "line": o["line"],
                "col": o["col"], "status": o["status"],
                "evidence": o["evidence"],
                "summary": None,   # filled from the M7 summary below
                "reads": [{"name": x.get("name"), "text": x.get("text"),
                           "kind": x.get("kind"),
                           "resolution": x.get("resolution"),
                           "decl": x.get("decl")}
                          for x in o.get("source_operands", [])
                          if x.get("kind") != "unsupported"],
                "writes": [{"name": x.get("name"),
                            "resolution": x.get("resolution"),
                            "decl": x.get("decl")}
                           for x in o.get("receivers", [])]}

    candidates: List[dict] = []
    unsupported: List[dict] = []
    for d in decisions:
        cond = cond_by_id.get(d["condition_id"])
        branch_ids = list(d["then_ops"]) + list(d["else_ops"])
        supported = [oid for oid in branch_ids
                     if oid in ops_by_id and ops_by_id[oid]["status"]
                     in ("established", "partial")]
        if cond is None:
            unsupported.append({
                "rule_id": _rule_id(program, d["decision_id"]),
                "program": program, "source_file": program,
                "line": d["line"], "structure": "decision",
                "status": "unsupported",
                "reason": "the controlling condition record is not "
                          "established; no rule candidate can be "
                          "derived",
                "evidence": d.get("evidence") or ""})
            continue
        if not supported:
            unsupported.append({
                "rule_id": _rule_id(program, d["decision_id"]),
                "program": program, "source_file": program,
                "line": d["line"], "structure": "decision",
                "status": "unsupported",
                "reason": "no supported operation is attributed to any "
                          "branch; the source establishes a condition "
                          "without an established rule structure",
                "evidence": cond.get("evidence") or ""})
            continue

        # condition text and operands
        left = cond.get("left_operand") or cond.get("left") or {}
        right = cond.get("right_operand") or cond.get("right") or {}
        cond_text = "%s %s %s" % (_label(left), cond.get("op") or "?",
                                  _label(right))
        cond_items = []
        for side, row in (("left", left), ("right", right)):
            if row.get("kind") in ("literal", "figurative") \
                    or row.get("name"):
                item = _resolve_item(model, row)
                item["side"] = side
                cond_items.append(item)

        # branch operations (references into the M6 operation list)
        summ = d.get("summary") or {}
        then_desc = {oid: None for oid in d["then_ops"]}
        for i, desc in enumerate(summ.get("then") or []):
            if i < len(d["then_ops"]):
                then_desc[d["then_ops"][i]] = desc
        else_desc = {}
        if d["has_else"]:
            for i, desc in enumerate(summ.get("else") or []):
                if i < len(d["else_ops"]):
                    else_desc[d["else_ops"][i]] = desc
        then_refs = []
        for oid in d["then_ops"]:
            r = op_ref(oid)
            if r:
                r["summary"] = then_desc.get(oid)
                then_refs.append(r)
        else_refs = []
        for oid in d["else_ops"]:
            r = op_ref(oid)
            if r:
                r["summary"] = else_desc.get(oid)
                else_refs.append(r)

        # data items read / written (deduplicated, provenance kept)
        items_read: List[dict] = []
        seen = set()
        for item in cond_items:
            if item["kind"] != "identifier":
                continue
            k = _item_key(item)
            if k in seen:
                continue
            seen.add(k)
            items_read.append({"name": item.get("name"),
                               "role": "condition",
                               "resolution": item.get("resolution"),
                               "decl": item.get("decl"),
                               "candidates": item.get("candidates"),
                               **_provenance(item.get("decl"))})
        for r in then_refs + else_refs:
            for x in r["reads"]:
                if x.get("kind") not in (None, "identifier"):
                    continue
                k = _item_key(x)
                if k in seen:
                    continue
                seen.add(k)
                items_read.append({"name": x.get("name"),
                                   "role": "read",
                                   "resolution": x.get("resolution"),
                                   "decl": x.get("decl"),
                                   "candidates": x.get("candidates"),
                                   **_provenance(x.get("decl"))})
        items_written: List[dict] = []
        written_decl_ids = []
        seen_w = set()
        for r in then_refs + else_refs:
            for x in r["writes"]:
                k = _item_key(x)
                if k in seen_w:
                    continue
                seen_w.add(k)
                decl = x.get("decl")
                if decl and decl.get("decl_id"):
                    written_decl_ids.append(decl["decl_id"])
                items_written.append({"name": x.get("name"),
                                      "resolution": x.get("resolution"),
                                      "decl": decl,
                                      **_provenance(decl)})

        # downstream uses: reads of written items by later operations
        branch_set = set(branch_ids)
        downstream = []
        seen_d = set()
        for decl_id in written_decl_ids:
            for c in consumers.get(decl_id, []):
                if c["op_id"] in branch_set:
                    continue
                k = (decl_id, c["op_id"])
                if k in seen_d:
                    continue
                seen_d.add(k)
                downstream.append({"via_item": decl_id, **c})

        # cross-program relationships via established links
        xprog = []
        seen_x = set()
        for oid in branch_ids:
            for l in links_by_op.get(oid, []):
                key = (l["callee"], l.get("argument"),
                       l["call"]["line"])
                if key in seen_x:
                    continue
                seen_x.add(key)
                xprog.append({"callee": l["callee"],
                       "argument": l.get("argument"),
                       "parameter": l.get("parameter"),
                       "call_line": l["call"]["line"],
                       "call_evidence": l["call"]["evidence"],
                       "status": l["status"],
                       "mapping_status": l.get("mapping_status"),
                       "position": l.get("position"),
                       "written_by_op": oid,
                       "callee_reads": l.get("callee_reads") or [],
                       "reason": l.get("reason")})
                if l.get("status") != "established" or \
                        l.get("mapping_status") != "established":
                    xprog[-1]["qualification"] = (
                        "argument/parameter mapping is %s; the "
                        "relationship is not a complete data contract"
                        % (l.get("mapping_status")
                           if l.get("status") == "established"
                           else l.get("status")))
        # (de-duplicated by callee/argument/call line)

        # unresolved elements -> partial
        unresolved = []
        for item in cond_items:
            if item["kind"] == "identifier" \
                    and item.get("resolution") != "resolved":
                unresolved.append({
                    "element": "condition_operand",
                    "detail": "condition operand %s is %s"
                              % (item.get("name"),
                                 item.get("resolution")),
                    "line": d["line"]})
        for r in then_refs + else_refs:
            if r["status"] not in ("established",):
                unresolved.append({
                    "element": "branch_operation",
                    "detail": "%s at L%d has status %s"
                              % (r["type"], r["line"], r["status"]),
                    "line": r["line"]})
        for x in xprog:
            if x.get("qualification"):
                unresolved.append({
                    "element": "argument_mapping",
                    "detail": "CALL %s at L%d: argument %s → parameter "
                              "%s mapping is %s"
                              % (x["callee"], x["call_line"],
                                 x["argument"], x["parameter"],
                                 x["mapping_status"]),
                    "line": x["call_line"]})
        status = ("partial" if unresolved
                  else "established_structure")

        # explanation: source-derived sentences only, every clause
        # traceable to the condition line, op ids or decl ids above
        parts = ["IF %s at L%d controls a THEN branch containing %s."
                 % (cond_text, d["line"],
                    "; ".join(t for t in (r["summary"] for r in
                                          then_refs) if t)
                 or "no supported operation")]
        if d["has_else"]:
            parts.append(" The ELSE branch contains %s."
                         % ("; ".join(t for t in (r["summary"] for r in
                                                  else_refs) if t)
                            or "no supported operation"))
        read_names = [i["name"] for i in cond_items
                      if i["kind"] == "identifier"]
        if read_names:
            parts.append(" The condition reads %s."
                         % ", ".join(read_names))
        if items_written:
            parts.append(" The branch writes %s."
                         % ", ".join(i["name"] or "?" for i in
                                     items_written))
        if summ.get("after"):
            parts.append(" After the decision, %s." % summ["after"])
        for x in xprog:
            parts.append(" The branch result %s is passed to %s at L%d "
                         "(parameter %s); %s."
                         % (x["argument"], x["callee"], x["call_line"],
                            x["parameter"], x["qualification"]
                            or "the link is established"))
        for u in unresolved:
            if u["element"] == "condition_operand":
                parts.append(" %s" % u["detail"][0].upper()
                             + u["detail"][1:] + ".")

        candidates.append({
            "rule_id": _rule_id(program, d["decision_id"]),
            "program": program, "source_file": program,
            "line": d["line"], "end_line": d.get("end_line"),
            "origin": d.get("origin"),
            "decision_id": d["decision_id"],
            "condition_id": d["condition_id"],
            "condition_text": cond_text,
            "condition_operands": cond_items,
            "has_else": d["has_else"],
            "then_ops": [r["op_id"] for r in then_refs],
            "else_ops": [r["op_id"] for r in else_refs],
            "items_read": items_read,
            "items_written": items_written,
            "downstream_uses": downstream,
            "cross_program": xprog,
            "unresolved_elements": unresolved,
            "status": status,
            "explanation": "".join(parts),
            "trace": {"condition_line": cond.get("line"),
                      "condition_evidence": cond.get("evidence"),
                      "op_ids": branch_ids,
                      "decl_ids": written_decl_ids
                      + [i["decl"]["decl_id"] for i in items_read
                         if i.get("decl")],
                      "summary": summ},
        })

    # decision structures that never became candidates
    rule_structures = {"unterminated IF", "EVALUATE", "ELSE", "END-IF",
                       "inline IF"}
    for u in flow.get("unsupported_statements") or []:
        if u.get("structure") in rule_structures:
            unsupported.append({
                "rule_id": _unsupported_id(program, u.get("line"),
                                           u["structure"]),
                "program": program, "source_file": program,
                "line": u.get("line"), "structure": u["structure"],
                "status": "unsupported",
                "reason": u.get("reason"),
                "evidence": u.get("text") or ""})
    candidates.sort(key=lambda c: (c["line"], c["rule_id"]))
    unsupported.sort(key=lambda c: (c["line"], c["rule_id"]))
    cov = {
        "candidates_total": len(candidates),
        "candidates_established_structure": sum(
            1 for c in candidates
            if c["status"] == "established_structure"),
        "candidates_partial": sum(1 for c in candidates
                                  if c["status"] == "partial"),
        "unsupported_total": len(unsupported),
    }
    return {"program": program, "candidates": candidates,
            "unsupported": unsupported, "coverage": cov}
