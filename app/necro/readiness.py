"""Evidence-backed migration-planning readiness derived from M1–M9 records.

This module classifies readiness for *detailed planning only*. It does not
approve migration, infer runtime behavior, or run another source analyzer.
All classifications are deterministic rule results over existing project
records. No confidence, health, cost, effort, or risk score is produced.

Classification rules (also recorded as a project assumption):
  * not_assessable: a physical program lacks either the logical model or
    dataflow records needed to assemble the required assessment dimensions;
  * investigation_required: evidence exists, but the parser rejected the
    file, an analysis dimension is unsupported/incomplete, or a recorded
    risk, unresolved dependency, or incomplete interface remains;
  * ready_for_planning: per-file analysis was accepted and supplemental
    source/dataflow records exist, with none of the above blockers recorded.
    This means only that detailed planning may begin within the represented
    analysis scope; it is not migration approval or equivalence evidence.

Every blocker is linked to its originating record. Work packages are
coalesced only for the same exact CALL statement, dependency edge/cycle,
parser-rejected program, unsupported construct, declaration, operation,
rule candidate, or finding id. Similar-looking records are not merged.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

STATES = ("ready_for_planning", "investigation_required", "not_assessable")

CLASSIFICATION_RULES = [
    "not_assessable: the program lacks either its logical model or dataflow records, so the required assessment dimensions cannot be assembled; parser rejection with both supplemental models remains investigation_required.",
    "investigation_required: evidence exists, but the frozen parser rejected the program, an unsupported or incomplete construct is recorded, or a risk, unresolved dependency/data relation, or incomplete CALL USING mapping affects it.",
    "ready_for_planning: per-file analysis was accepted and supplemental logical/dataflow records exist, and no blockers from the preceding rules are present. This is permission to begin detailed planning only, not migration approval or runtime-equivalence evidence.",
    "Absence of findings or rule candidates is not treated as proof of absence of risk or business logic; zero-candidate programs retain a non-blocking verification question and explicit scope limitations.",
    "The project is ready only when every indexed program is ready_for_planning and there are no skipped inputs. No project score or weighted aggregation is calculated.",
]

LIMITATIONS = [
    "Assessment is limited to records produced by the frozen grammar and existing M1–M9 scanners; rejected and unsupported source is not silently treated as understood.",
    "Static dependency and CALL USING evidence does not establish runtime execution, interface compatibility, or runtime data contracts.",
    "Rule candidates are source structure, not verified business requirements; zero candidates does not prove that business logic is absent.",
    "Copybooks are not textually expanded; copybook-origin declarations and cycles retain their existing qualifications.",
    "No numerical confidence, readiness, risk, cost, schedule, or effort score is computed.",
]


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _ref_key(ref: dict) -> str:
    return _stable_json(ref)


def _sorted_refs(refs: Iterable[dict]) -> List[dict]:
    unique = {_ref_key(ref): ref for ref in refs if isinstance(ref, dict)}
    return [unique[k] for k in sorted(unique)]


def _id(prefix: str, key: Any) -> str:
    return prefix + hashlib.sha1(_stable_json(key).encode("utf-8")).hexdigest()[:12]


def _file_ref(file_id: str, status: Optional[str] = None,
              reason: Optional[str] = None) -> dict:
    ref = {"kind": "program_analysis", "file": file_id}
    if status is not None:
        ref["status"] = status
    if reason:
        ref["reason"] = reason
    return ref


def _finding_ref(f: dict, source_context: Optional[str] = None) -> dict:
    detail = f.get("detail") or {}
    file_id = (detail.get("program") or detail.get("caller_file")
               or detail.get("file") or source_context)
    line = detail.get("statement_line") or f.get("line")
    return {
        "kind": "finding", "finding_id": f.get("finding_id"),
        "code": f.get("code"), "classification": f.get("classification"),
        "file": file_id, "line": line, "col": f.get("col"),
        "message": f.get("message"), "evidence": f.get("evidence"),
        "hint": f.get("hint"),
    }


def _edge_ref(e: dict) -> dict:
    return {
        "kind": "dependency_edge", "from": e.get("from"),
        "to": e.get("to"), "target": e.get("target"),
        "dependency_kind": e.get("kind"),
        "resolution": e.get("resolution"), "line": e.get("line"),
        "col": e.get("col"), "evidence": e.get("text"),
        "candidates": sorted(e.get("candidates") or []),
    }


def _mapping_ref(m: dict) -> dict:
    return {
        "kind": "call_using_mapping", "caller": m.get("from"),
        "callee": m.get("to"), "target": m.get("target"),
        "line": m.get("line"), "col": m.get("col"),
        "status": m.get("status"), "reason": m.get("reason"),
        "evidence": m.get("text"),
        "positions": [{
            "position": p.get("position"),
            "status": p.get("status"),
            "argument": (p.get("caller") or {}).get("name"),
            "parameter": (p.get("receiver") or {}).get("name"),
            "caller_decl_id": (p.get("caller_decl") or {}).get("decl_id"),
            "receiver_decl_id": (p.get("receiver_decl") or {}).get("decl_id"),
            "size_status": p.get("size_status"),
        } for p in (m.get("positions") or [])],
    }


def _mapping_prerequisites(m: dict) -> List[dict]:
    refs = []
    for p in (m.get("positions") or []):
        for side, decl in (("caller", p.get("caller_decl") or {}),
                           ("receiver", p.get("receiver_decl") or {})):
            if not decl.get("decl_id"):
                continue
            refs.append({
                "kind": "logical_declaration", "side": side,
                "file": decl.get("file"), "line": decl.get("line"),
                "decl_id": decl.get("decl_id"), "name": decl.get("name"),
                "declaration_status": decl.get("status") or "unknown",
                "storage_size_status": ("recorded" if decl.get("byte_length") is not None
                                        else "not_established"),
                "byte_length": decl.get("byte_length"),
                "picture": decl.get("picture"), "usage": decl.get("usage"),
            })
    return _sorted_refs(refs)


def _operation_ref(program: str, op: dict) -> dict:
    return {"kind": "operation", "program": program,
            "op_id": op.get("op_id"), "line": op.get("line"),
            "status": op.get("status"), "type": op.get("type"),
            "evidence": op.get("evidence")}


def _question(question: str, why: str, verify: str,
              refs: Iterable[dict], blocking: bool = True) -> dict:
    return {"question": question, "why_it_matters": why,
            "verify": verify, "blocking_for_planning": blocking,
            "evidence_refs": _sorted_refs(refs)}


def build_readiness(files: List[dict], skipped: List[dict],
                    per_file: Dict[str, dict], edges: List[dict],
                    cycles: List[List[str]], cross_file: dict,
                    findings: List[dict], assumptions: List[dict]) -> dict:
    """Build deterministic readiness reports and deduplicated work packages."""
    programs = sorted(f["file_id"] for f in files
                      if f.get("kind") == "program" and f.get("file_id"))
    file_kind = {f.get("file_id"): f.get("kind") for f in files}
    xf = cross_file or {}
    logical = xf.get("logical") or {}
    dataflow = (xf.get("dataflow") or {}).get("programs") or {}
    mappings = xf.get("mappings") or []
    assumptions_by_id = {a.get("id"): a for a in assumptions if a.get("id")}
    all_assumption_ids = sorted(assumptions_by_id)

    # Reverse relationships let a problem in a shared copybook or called
    # program affect the programs that actually depend on it.
    reverse: Dict[str, List[str]] = defaultdict(list)
    for e in edges:
        if e.get("from") and e.get("to"):
            reverse[e["to"]].append(e["from"])
    for key in reverse:
        reverse[key] = sorted(set(reverse[key]))

    def affected_by(file_id: Optional[str]) -> List[str]:
        if not file_id:
            return []
        seen: Set[str] = set()
        roots: Set[str] = set()
        queue = deque([file_id])
        while queue:
            current = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            if file_kind.get(current) == "program":
                roots.add(current)
            for parent in reverse.get(current, []):
                queue.append(parent)
        return sorted(roots)

    def affected_by_many(file_ids: Iterable[Optional[str]]) -> List[str]:
        out: Set[str] = set()
        for file_id in file_ids:
            out.update(affected_by(file_id))
        return sorted(out)

    def direct_programs(file_ids: Iterable[Optional[str]]) -> List[str]:
        out: Set[str] = set()
        for file_id in file_ids:
            if not file_id:
                continue
            if file_kind.get(file_id) == "program":
                out.add(file_id)
            else:
                out.update(affected_by(file_id))
        return sorted(out)

    def dependency_path_refs(target: str) -> List[dict]:
        """Exact reverse-edge evidence connecting programs to a shared target."""
        refs = []
        queue = deque([target])
        visited = set()
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            for parent in reverse.get(current, []):
                refs.extend(_edge_ref(e) for e in edges
                            if e.get("from") == parent
                            and e.get("to") == current)
                queue.append(parent)
        return _sorted_refs(refs)

    def finding_programs(f: dict, source_context: Optional[str] = None) -> List[str]:
        d = f.get("detail") or {}
        # A semantic finding's `file` can be the receiver declaration's
        # copybook, while `program` identifies the operation that triggered
        # this specific finding. Do not spread one operation risk to every
        # program that includes that declaration. Cross-program XFD records
        # explicitly identify caller and receiver, so both sides are affected.
        if d.get("program"):
            return direct_programs((d["program"],))
        if d.get("caller_file"):
            return direct_programs((d.get("caller_file"),
                                    d.get("receiver_file")))
        return affected_by_many((d.get("file"), source_context))

    # Project findings and per-file Diagnostic records are separate existing
    # sources. Combine them for readiness, deduplicating only an exact same
    # finding in the same physical source context; same ids/messages in
    # different programs remain distinct records.
    diagnostic_rows: Dict[str, Tuple[dict, Optional[str]]] = {}
    for f in findings:
        d = f.get("detail") or {}
        context = d.get("program") or d.get("caller_file") or d.get("file")
        identity = (context, f.get("finding_id"), f.get("code"),
                    f.get("line"), f.get("message"))
        diagnostic_rows[_stable_json(identity)] = (f, context)
    for source_file, result in sorted(per_file.items()):
        for f in ((result.get("result") or {}).get("diagnostics") or []):
            identity = (source_file, f.get("finding_id"), f.get("code"),
                        f.get("line"), f.get("message"))
            diagnostic_rows.setdefault(_stable_json(identity), (f, source_file))
    assessment_findings = [diagnostic_rows[k] for k in sorted(diagnostic_rows)]

    # Per-program issues are deduplicated by exact evidence identity; work
    # packages use a coarser, explicit source-location key where two M1–M9
    # records describe the same CALL/dependency occurrence.
    program_issues: Dict[str, Dict[str, dict]] = {p: {} for p in programs}
    work: Dict[str, dict] = {}

    def add_issue(key: str, code: str, title: str, detail: str,
                  refs: Iterable[dict], affected: Iterable[str],
                  dimensions: Iterable[str], question: str, why: str,
                  verify: str, package_spec: Optional[dict] = None) -> None:
        refs = _sorted_refs(refs)
        affected = sorted(set(p for p in affected if p in program_issues))
        dim_list = sorted(set(dimensions))
        issue = {"code": code, "title": title, "detail": detail,
                 "evidence_refs": refs}
        for p in affected:
            prior = program_issues[p].get(key)
            if prior:
                prior["evidence_refs"] = _sorted_refs(
                    prior["evidence_refs"] + refs)
                if detail not in prior["detail"]:
                    prior["detail"] += " " + detail
            else:
                program_issues[p][key] = dict(issue)
        if package_spec is not None:
            existing = work.get(key)
            if existing:
                existing["evidence_refs"] = _sorted_refs(
                    existing["evidence_refs"] + refs)
                existing["affected_programs"] = sorted(
                    set(existing["affected_programs"] + affected))
                if package_spec.get("prerequisites"):
                    existing["prerequisites"] = _sorted_refs(
                        existing["prerequisites"]
                        + package_spec["prerequisites"])
                for field in ("reason", "expected_outcome", "completion_condition"):
                    value = package_spec.get(field)
                    if value and value not in existing[field]:
                        existing[field] += " " + value
            else:
                work[key] = {
                    "work_package_id": _id("wp-", key),
                    "category": package_spec["category"],
                    "title": package_spec["title"],
                    "affected_programs": affected,
                    "affected_dependency": package_spec.get("dependency"),
                    "reason": package_spec["reason"],
                    "evidence_refs": refs,
                    "prerequisites": _sorted_refs(
                        package_spec.get("prerequisites") or []),
                    "expected_outcome": package_spec["expected_outcome"],
                    "completion_condition": package_spec["completion_condition"],
                    "blocking_for_planning": True,
                    "deduplication_basis": package_spec["deduplication_basis"],
                }
        # keep dimension use explicit in issue detail for the assessment
        for p in affected:
            issue_row = program_issues[p][key]
            issue_row["dimensions"] = sorted(set(
                issue_row.get("dimensions", []) + dim_list))
            issue_row["unresolved_question"] = question
            issue_row["why_it_matters"] = why
            issue_row["verify"] = verify

    # CALL identity key: resolution edge + mapping + XFD finding at the same
    # source CALL are one actionable unit, with every original ref retained.
    call_key_by_line: Dict[Tuple[str, Optional[int]], str] = {}

    def call_key(file_id: str, line: Optional[int]) -> str:
        tup = (file_id, line)
        if tup not in call_key_by_line:
            call_key_by_line[tup] = "call|%s|%s" % (file_id, line)
        return call_key_by_line[tup]

    edge_issue_refs: Dict[str, List[dict]] = defaultdict(list)
    mapping_issue_refs: Dict[str, List[dict]] = defaultdict(list)

    # 1. Unsupported parser records grouped once per physical program.
    for fid in programs:
        pf = per_file.get(fid) or {}
        if pf.get("status") != "rejected":
            continue
        result = pf.get("result") or {}
        diagnostics = result.get("diagnostics") or []
        parser_refs = [{
            "kind": "parser_diagnostic", "finding_id": d.get("finding_id"),
            "code": d.get("code"), "classification": d.get("classification"),
            "severity": d.get("severity"), "layer": d.get("layer"),
            "file": fid, "line": d.get("line"), "col": d.get("col"),
            "message": d.get("message"), "context_line": d.get("context_line"),
        } for d in diagnostics]
        if not parser_refs:
            parser_refs = [_file_ref(fid, "rejected", pf.get("reason"))]
        refs = ([_file_ref(fid, "rejected", pf.get("reason"))] + parser_refs
                + dependency_path_refs(fid))
        question = "Which source constructs caused the frozen-subset parser rejection, and what behavior must planning account for?"
        add_issue(
            "parser|" + fid, "SOURCE_PARSER_REJECTED",
            "Review parser-rejected source scope",
            pf.get("reason") or "The per-file analysis did not accept this program.",
            refs, affected_by(fid), ["source_understanding", "business_logic"],
            question,
            "Unsupported source is not covered by the accepted parser result; a migration plan could otherwise omit behavior.",
            "Annotate each rejected source location and classify the construct/behavior using source, build, or design evidence; do not infer that the rejected content is irrelevant.",
            {"category": "source_understanding",
             "title": "Review rejected source in " + fid,
             "reason": pf.get("reason") or "The parser rejected this program.",
             "expected_outcome": "A source-backed inventory of rejected constructs and their relevance to the planned component.",
             "completion_condition": "Every parser diagnostic is linked to a reviewed source range and its behavior is either represented in planning or explicitly recorded as an unresolved dependency.",
             "dependency": {"program": fid},
             "deduplication_basis": "One package per physical program's parser-rejection record; diagnostic refs are retained inside the package."},
        )

    # A missing/unknown per-file status is itself an evidence gap, even if
    # a supplemental scan record happens to exist.
    for fid in programs:
        status = (per_file.get(fid) or {}).get("status")
        if status not in ("analyzed", "rejected"):
            refs = [_file_ref(fid, status, (per_file.get(fid) or {}).get("reason"))]
            add_issue(
                "status|" + fid, "SOURCE_STATUS_UNESTABLISHED",
                "Establish source-analysis status for " + fid,
                "The project envelope has no accepted/rejected per-file analysis status for this program.",
                refs, affected_by(fid), ["source_understanding"],
                "Was this exact source file accepted by the frozen parser, rejected, or not analyzed?",
                "Supplemental results cannot be interpreted as a complete parser status.",
                "Re-run the existing project analysis or recover the per-file analysis record, then review the resulting diagnostics.",
                {"category": "source_understanding",
                 "title": "Establish source-analysis status for " + fid,
                 "reason": "No stable per-file parser status is recorded.",
                 "expected_outcome": "A per-file status and its source diagnostics, with supplemental records kept separately.",
                 "completion_condition": "The source status is recovered and reconciled with existing supplemental records.",
                 "dependency": {"program": fid},
                 "deduplication_basis": "One package per physical program with missing/unknown per-file status."},
            )

    # A missing required supplement is an actionable evidence gap and makes
    # the individual state not_assessable; keep source-status evidence too.
    for fid in programs:
        missing_models = []
        if fid not in logical:
            missing_models.append("logical model")
        if fid not in dataflow:
            missing_models.append("dataflow model")
        if missing_models:
            refs = [_file_ref(fid, (per_file.get(fid) or {}).get("status"),
                              (per_file.get(fid) or {}).get("reason"))]
            refs.extend(dependency_path_refs(fid))
            detail = "Missing required existing record(s): " + ", ".join(missing_models) + "."
            add_issue(
                "records|" + fid, "REQUIRED_ANALYSIS_RECORD_MISSING",
                "Restore readiness evidence for " + fid, detail, refs,
                affected_by(fid), ["source_understanding", "data_integrity",
                                   "interface_dependency", "business_logic"],
                "Which existing analysis record is missing, and can it be regenerated for this exact source?",
                "Without the logical or dataflow record, the readiness dimensions cannot be assembled or checked.",
                "Re-run or restore the corresponding existing M1–M9 project record and confirm it belongs to this physical source file.",
                {"category": "source_understanding",
                 "title": "Restore readiness evidence for " + fid,
                 "reason": detail,
                 "expected_outcome": "The missing logical/dataflow analysis record is regenerated or the gap is explicitly documented.",
                 "completion_condition": "Both required supplemental records are present for this exact source, or the program remains explicitly not assessable.",
                 "dependency": {"program": fid, "missing_records": missing_models},
                 "deduplication_basis": "One package per physical program and missing M1–M9 record dimension."},
            )

    # 2. Unresolved/ambiguous/dynamic dependency edges. A CALL's edge,
    # mapping, and XFD findings share one work package per caller+line.
    for e in edges:
        resolution = e.get("resolution")
        if resolution not in ("missing", "unresolved", "dynamic", "ambiguous"):
            continue
        ref = _edge_ref(e)
        source = e.get("from")
        line = e.get("line")
        kind = e.get("kind")
        target = e.get("target") or e.get("to")
        affected = direct_programs((source,))
        issue_refs = ([ref] + dependency_path_refs(source)
                      if source and file_kind.get(source) != "program" else [ref])
        if kind == "call" and source:
            key = call_key(source, line)
            edge_issue_refs[key].append(ref)
            is_dynamic = resolution == "dynamic"
            title = ("Establish dynamic CALL target" if is_dynamic else
                     "Resolve CALL target " + str(target or "(unknown)"))
            reason = ("The CALL target is an identifier and cannot be established statically." if is_dynamic else
                      "The CALL target is " + str(resolution) + " in the indexed project.")
            verify = ("Trace assignments and control paths for the CALL identifier, then identify the concrete target(s) or record the external dispatch mechanism with evidence." if is_dynamic else
                      "Confirm the intended target against source, link/build configuration, or interface documentation; record whether it is in-project or external.")
            add_issue(
                key, "CALL_" + resolution.upper(), title, reason, [ref], affected,
                ["interface_dependency"],
                "What program or external component does this CALL reach?",
                "Changing or replacing a caller without knowing its target can miss a required component or interface.",
                verify,
                {"category": "interface_dependency", "title": title,
                 "reason": reason,
                 "expected_outcome": "An evidence-backed target identity and documented interface boundary, or an explicit external/unresolved disposition.",
                 "completion_condition": "The target is linked to source/configuration evidence or explicitly classified as external/unknown with the migration impact recorded.",
                 "dependency": {"caller": source, "target": target,
                                "line": line, "resolution": resolution},
                 "deduplication_basis": "One package per physical CALL statement (caller file + source line); matching M9 edge, mapping, and finding refs are attached to that package."},
            )
        else:
            key = "dependency|%s|%s|%s|%s" % (kind, source, target, line)
            edge_issue_refs[key].append(ref)
            if resolution == "ambiguous":
                title = "Disambiguate " + str(kind).upper() + " dependency " + str(target)
                reason = "The reference has multiple candidate files; the intended target is not established."
                verify = "Use explicit source/library/build evidence to determine the intended copybook or dependency; do not choose the first basename match."
                expected = "The intended dependency is established from project/build evidence, or the ambiguity is recorded as an external/unresolved boundary."
            elif resolution == "missing":
                title = "Locate missing " + str(kind).upper() + " dependency " + str(target)
                reason = "The referenced dependency is absent from the indexed project."
                verify = "Check the full source/library search path and build inputs to determine whether the dependency is absent, external, or misnamed."
                expected = "The dependency is linked to an indexed source or documented as external/out of scope with evidence."
            else:
                title = "Resolve dependency " + str(target)
                reason = "The dependency target is not resolved by the existing project index."
                verify = "Confirm the dependency target and its source location from project/build evidence."
                expected = "The target is established from evidence or explicitly retained as unresolved."
            add_issue(
                key, "DEPENDENCY_" + resolution.upper(), title, reason, issue_refs,
                affected, ["interface_dependency", "source_understanding"],
                "Which source or library member satisfies this dependency?",
                "A component that consumes an unknown/missing dependency may require different migration boundaries or sequencing.",
                verify,
                {"category": "interface_dependency", "title": title,
                 "reason": reason, "expected_outcome": expected,
                 "completion_condition": "The intended target and its project/external status are recorded with source or build evidence.",
                 "dependency": {"from": source, "to": e.get("to"),
                                "target": target, "kind": kind,
                                "line": line, "resolution": resolution},
                 "deduplication_basis": "One package per exact dependency edge occurrence (kind, source file, target, and line); message similarity does not merge distinct edges."},
            )

    # 3. Copybook cycles are package-level work items. Propagate their
    # readiness effect to programs that depend on any cycle member.
    cycle_findings = [(f, ctx) for f, ctx in assessment_findings
                      if f.get("code") == "DEP_CYCLE"]
    for cycle in sorted((sorted(c) for c in cycles), key=lambda c: tuple(c)):
        members = sorted(set(cycle))
        related = [e for e in edges if e.get("kind") == "copy"
                   and e.get("from") in members and e.get("to") in members]
        refs = [_edge_ref(e) for e in related]
        for member in members:
            refs.extend(dependency_path_refs(member))
        for f, context in cycle_findings:
            detail = f.get("detail") or {}
            if set(detail.get("members") or []) == set(members):
                refs.append(_finding_ref(f, context))
        affected = affected_by_many(members)
        key = "cycle|" + "|".join(members)
        add_issue(
            key, "COPYBOOK_CYCLE", "Review copybook inclusion cycle",
            "The indexed COPY graph contains a cycle: " + " → ".join(members) + ".",
            refs, affected, ["interface_dependency", "source_understanding"],
            "Is this copybook cycle intentional, and what expanded declaration behavior does the compiler/build produce?",
            "Cycle handling and declaration expansion cannot be treated as a verified linear dependency order.",
            "Review the participating COPY statements and compiler/build behavior; document the effective declarations or restructure the dependency before planning changes to affected programs.",
            {"category": "interface_dependency",
             "title": "Review copybook cycle: " + " ↔ ".join(members),
             "reason": "COPY dependencies form a strongly connected component.",
             "expected_outcome": "A source/build-backed description of the cycle's effective declarations and affected program boundaries.",
             "completion_condition": "Every cycle edge and affected program is reviewed, and the migration plan records the chosen handling of the cycle.",
             "dependency": {"members": members},
             "deduplication_basis": "One package per sorted strongly connected component; edge and DEP_CYCLE finding evidence is combined."},
        )

    # 4. Incomplete/unresolved CALL USING mapping records. Correlate them to
    # the exact CALL identity so an unresolved edge does not duplicate work.
    for m in mappings:
        if m.get("status") == "established":
            continue
        source, line = m.get("from"), m.get("line")
        if not source:
            continue
        key = call_key(source, line)
        ref = _mapping_ref(m)
        related_call_edges = [_edge_ref(e) for e in edges
                              if e.get("kind") == "call"
                              and e.get("from") == source
                              and e.get("line") == line]
        mapping_refs = [ref] + related_call_edges
        mapping_issue_refs[key].extend(mapping_refs)
        status = m.get("status") or "unknown"
        title = ("Verify incomplete CALL USING mapping" if status == "incomplete"
                 else "Establish unresolved CALL USING mapping")
        reason = "CALL USING correspondence is recorded as " + str(status) + "; positional association does not establish a verified runtime contract."
        verify = "Compare the caller's arguments and passing modes with the callee's receiving parameters using declarations, compiler/interface artifacts, and representative call evidence; resolve size/layout differences explicitly."
        add_issue(
            key, "CALL_USING_" + str(status).upper(), title, reason, mapping_refs,
            direct_programs((source, m.get("to"))), ["interface_dependency", "data_integrity"],
            "Do the caller arguments and receiving parameters have the intended number, order, storage layout, and passing semantics?",
            "Changing either side without establishing the interface can alter shared storage or data interpretation.",
            verify,
            {"category": "interface_dependency", "title": title,
             "reason": reason,
             "expected_outcome": "An explicitly verified CALL USING interface for each position, or a documented unresolved/external boundary.",
             "completion_condition": "Every argument/parameter position has evidence for identity, passing mode, representation, and any intended mismatch; the mapping is not promoted on position alone.",
             "dependency": {"caller": source, "callee": m.get("to"),
                            "line": line, "target": m.get("target"),
                            "status": status},
             "prerequisites": _mapping_prerequisites(m),
             "deduplication_basis": "One package per source CALL statement (caller file + line), shared with matching dynamic/missing CALL edge and XFD finding records."},
        )

    # 5. Data/integrity and cross-program findings. XFD findings join the
    # CALL package when possible; every source finding remains a ref.
    finding_to_package: Dict[Tuple[Optional[str], Optional[str]], str] = {}
    for f, source_context in assessment_findings:
        code = f.get("code") or ""
        cls = f.get("classification")
        if cls not in ("risk", "violation"):
            continue
        detail = f.get("detail") or {}
        ref = _finding_ref(f, source_context)
        affected = finding_programs(f, source_context)
        if code.startswith("XFD_") and detail.get("caller_file") and f.get("line"):
            key = call_key(detail["caller_file"], f.get("line"))
            finding_to_package[(source_context, f.get("finding_id"))] = key
            title = "Verify CALL interface risk: " + code
            reason = f.get("message") or "A cross-program interface risk was recorded."
            verify = "Verify caller/receiver argument counts, declaration sizes and passing semantics against authoritative interface/build evidence."
            add_issue(
                key, code, title, reason, [ref], affected,
                ["interface_dependency", "data_integrity"],
                "What are the intended interface layout and passing semantics for this CALL?",
                "A caller/callee representation mismatch can change the data observed across a program boundary.",
                verify,
                {"category": "interface_dependency", "title": title,
                 "reason": reason,
                 "expected_outcome": "A verified CALL interface or a documented mismatch disposition with source/interface evidence.",
                 "completion_condition": "The affected CALL position is checked against authoritative declaration/layout evidence and the migration boundary records the result.",
                 "dependency": {"caller": detail.get("caller_file"),
                                "callee": detail.get("receiver_file"),
                                "line": f.get("line"), "code": code},
                 "deduplication_basis": "Attached to the CALL work package keyed by caller source file + line; the finding id is retained separately."},
            )
            continue
        if code.startswith("DEP_"):
            # Cycle findings belong to the SCC package created above.
            if code == "DEP_CYCLE":
                members = sorted(set(detail.get("members") or []))
                cycle_key = "cycle|" + "|".join(members)
                finding_to_package[(source_context, f.get("finding_id"))] = cycle_key
                if cycle_key in work:
                    work[cycle_key]["evidence_refs"] = _sorted_refs(
                        work[cycle_key]["evidence_refs"] + [ref])
                continue
            # Dependency findings are attached to the matching exact edge
            # package where possible, avoiding a second package for one edge.
            detail_file, line = detail.get("file"), f.get("line")
            match = next((e for e in edges
                          if e.get("from") == detail_file
                          and e.get("line") == line
                          and (not detail.get("target")
                               or e.get("target") == detail.get("target"))), None)
            if match:
                key = (call_key(detail_file, line) if match.get("kind") == "call"
                       else "dependency|%s|%s|%s|%s" % (
                           match.get("kind"), match.get("from"),
                           match.get("target") or match.get("to"), line))
                finding_to_package[(source_context, f.get("finding_id"))] = key
                if key in work:
                    work[key]["evidence_refs"] = _sorted_refs(
                        work[key]["evidence_refs"] + [ref])
                for p in affected:
                    if key in program_issues.get(p, {}):
                        program_issues[p][key]["evidence_refs"] = _sorted_refs(
                            program_issues[p][key]["evidence_refs"] + [ref])
                continue
        category = "data_integrity" if code.startswith("SEM_") else "investigation"
        title = ("Verify data representation risk: " + code
                 if code.startswith("SEM_") else
                 "Investigate recorded risk: " + code)
        reason = f.get("message") or "An existing project finding requires review."
        if code.startswith("SEM_"):
            verify = "Compare the source statement, sender/result bounds, receiver PICTURE/USAGE, sign and storage representation with the compiler/runtime contract; document intended handling before changing data representation."
            expected = "The affected storage and value-range behavior is established from declarations and source/compiler evidence, including whether truncation/precision/sign loss is intended."
            completion = "The source and declaration evidence are reviewed, and the migration plan records the verified representation and treatment of the finding."
            dimensions = ["data_integrity"]
        else:
            verify = f.get("hint") or "Review the cited source and related dependency records; establish the underlying behavior before planning changes."
            expected = "The finding's underlying source/dependency behavior and impact are documented with evidence."
            completion = "The finding is resolved or explicitly retained as a known planning constraint with reviewed evidence."
            dimensions = ["investigation_requirements"]
        key = "finding|" + str(f.get("finding_id"))
        finding_to_package[(source_context, f.get("finding_id"))] = key
        add_issue(
            key, code, title, reason, [ref], affected, dimensions,
            "Does the cited source behavior create a migration constraint, and what representation/behavior must be preserved?",
            "The engine recorded a specific risk/violation; absence of runtime evidence means its impact must be reviewed, not dismissed.",
            verify,
            {"category": category, "title": title, "reason": reason,
             "expected_outcome": expected, "completion_condition": completion,
             "dependency": None,
             "deduplication_basis": "One package per exact finding_id; distinct findings are kept separate even when their messages or codes are similar."},
        )

    # Add non-blocking note evidence to matching ambiguous dependency work.
    for f, source_context in assessment_findings:
        if f.get("classification") != "note":
            continue
        if f.get("code") != "DEP_DUPLICATE_BASENAME":
            continue
        detail = f.get("detail") or {}
        files_for_name = set(detail.get("files") or [])
        ref = _finding_ref(f, source_context)
        for e in edges:
            if e.get("resolution") == "ambiguous" and set(e.get("candidates") or []) & files_for_name:
                key = "dependency|%s|%s|%s|%s" % (
                    e.get("kind"), e.get("from"),
                    e.get("target") or e.get("to"), e.get("line"))
                if key in work:
                    work[key]["evidence_refs"] = _sorted_refs(
                        work[key]["evidence_refs"] + [ref])

    # 6. Per-program scan limitations, unknown declarations, operations,
    # unsupported structures, data references, and rule-candidate status.
    for fid in programs:
        flow = dataflow.get(fid) or {}
        model = logical.get(fid) or {}
        for u in flow.get("unsupported_statements") or []:
            line, structure = u.get("line"), u.get("structure") or "unsupported statement"
            ref = {"kind": "unsupported_construct", "file": u.get("file") or fid,
                   "line": line, "structure": structure,
                   "reason": u.get("reason"), "evidence": u.get("text")}
            key = "unsupported|%s|%s|%s" % (fid, line, structure)
            add_issue(
                key, "UNSUPPORTED_" + str(structure).upper(),
                "Review unsupported " + str(structure) + " in " + fid,
                u.get("reason") or "The statement is not interpreted by the existing scanner.",
                [ref], affected_by(fid), ["source_understanding", "business_logic"],
                "What behavior is implemented by this unsupported construct and its body?",
                "The structure and its nested operations are not established by existing analysis records.",
                "Review the full source range and authoritative program documentation; record every branch/path and the effects relevant to the component.",
                {"category": "business_logic", "title": "Review unsupported " + str(structure) + " in " + fid,
                 "reason": u.get("reason") or "The construct is outside the analyzed statement subset.",
                 "expected_outcome": "A source-backed description of the construct and relevant branch behavior.",
                 "completion_condition": "The construct's cases and affected data/dependencies are reviewed and recorded for planning.",
                 "dependency": {"program": fid, "line": line, "structure": structure},
                 "deduplication_basis": "One package per physical source location and unsupported structure; duplicate representations of the same location are combined."},
            )

        rules = flow.get("rules") or {}
        for unsupported in rules.get("unsupported") or []:
            line = unsupported.get("line")
            structure = unsupported.get("structure") or "unsupported rule structure"
            ref = {"kind": "unsupported_rule_structure", "file": unsupported.get("source_file") or fid,
                   "line": line, "rule_id": unsupported.get("rule_id"),
                   "structure": structure, "status": unsupported.get("status"),
                   "reason": unsupported.get("reason"),
                   "evidence": unsupported.get("evidence")}
            key = "unsupported|%s|%s|%s" % (fid, line, structure)
            add_issue(
                key, "UNSUPPORTED_" + str(structure).upper(),
                "Review unsupported " + str(structure) + " in " + fid,
                unsupported.get("reason") or "The decision/rule structure is not interpreted by the existing rule model.",
                [ref], direct_programs((fid,)), ["source_understanding", "business_logic"],
                "What does this unsupported decision structure do in each case and branch?",
                "The rule model cannot establish its subject, cases, or branch effects.",
                "Review every case/default branch and its operations in source, and validate the behavior with authoritative program or business documentation.",
                {"category": "business_logic",
                 "title": "Review unsupported " + str(structure) + " in " + fid,
                 "reason": unsupported.get("reason") or "Rule structure status is unsupported.",
                 "expected_outcome": "A source-backed account of the decision cases and affected operations.",
                 "completion_condition": "Every case and resulting operation is reviewed and recorded for planning without inferring business meaning from identifiers.",
                 "dependency": {"program": fid, "rule_id": unsupported.get("rule_id"),
                                "line": line, "structure": structure},
                 "deduplication_basis": "Coalesced with the same file/line/structure unsupported-statement package; rule and scanner evidence refs remain separate."},
            )

        for u in model.get("unsupported_structures") or []:
            decl_id = u.get("decl_id") or u.get("id")
            line, name = u.get("line"), u.get("name") or u.get("structure") or "declaration"
            ref = {"kind": "unsupported_declaration", "file": u.get("file") or u.get("source_file") or fid,
                   "line": line, "decl_id": decl_id, "name": name,
                   "reason": u.get("reason") or u.get("unsupported_reason"),
                   "evidence": u.get("text")}
            key = "declaration|%s|%s|%s" % (fid, decl_id or line, name)
            add_issue(
                key, "UNKNOWN_OR_UNSUPPORTED_DECLARATION",
                "Establish storage representation for " + str(name),
                ref.get("reason") or "The declaration includes storage semantics not established by the current logical model.",
                [ref], affected_by(fid), ["source_understanding", "data_integrity"],
                "What storage size, representation, and layout does this declaration have in the target runtime/compiler?",
                "Unknown storage cannot safely be treated as zero or copied into a migration representation.",
                "Verify the declaration and compiler/layout evidence, including unsupported clauses or usage, and record exact storage semantics.",
                {"category": "data_integrity", "title": "Establish storage representation for " + str(name),
                 "reason": ref.get("reason") or "Storage semantics are not established.",
                 "expected_outcome": "A verified declaration/layout record with size and representation semantics.",
                 "completion_condition": "The unknown or unsupported storage semantics are verified from source/compiler artifacts or explicitly retained as an unresolved blocker.",
                 "dependency": {"program": fid, "decl_id": decl_id, "line": line},
                 "deduplication_basis": "One package per logical declaration id (or exact program/source line when no id exists)."},
            )

        for decl in model.get("declarations") or []:
            unknown = (decl.get("status") in ("partial", "unsupported", "unresolved")
                       or decl.get("unsupported_reason")
                       or (decl.get("byte_length") is None
                           and not decl.get("children")))
            if not unknown:
                continue
            dfile = decl.get("source_file") or decl.get("file") or fid
            line, decl_id = decl.get("line"), decl.get("decl_id")
            ref = {"kind": "logical_declaration", "file": dfile,
                   "program": fid, "line": line, "decl_id": decl_id,
                   "name": decl.get("name"), "status": decl.get("status"),
                   "picture": decl.get("picture"), "usage": decl.get("usage"),
                   "byte_length": decl.get("byte_length"),
                   "reason": decl.get("unsupported_reason"),
                   "origin": decl.get("origin"),
                   "via_copybooks": decl.get("via_copybooks") or []}
            key = "declaration|%s|%s|%s" % (
                fid, decl_id or line, decl.get("name") or "declaration")
            add_issue(
                key, "UNKNOWN_STORAGE", "Verify storage for " + str(decl.get("name")),
                "The logical declaration has unresolved status or no established storage size.",
                [ref], affected_by(fid), ["data_integrity", "source_understanding"],
                "What exact storage size and representation does this item have?",
                "Dataflow and interface planning cannot rely on an unknown storage size or unsupported declaration semantics.",
                "Check the full declaration, included copybooks, compiler listing, and applicable record layout; document size, sign, usage, and unsupported clauses.",
                {"category": "data_integrity", "title": "Verify storage for " + str(decl.get("name")),
                 "reason": "Storage size or declaration status is unresolved in the logical model.",
                 "expected_outcome": "A verified storage/layout description for the named item.",
                 "completion_condition": "The declaration's size and representation are established or explicitly kept as an unresolved blocker with source evidence.",
                 "dependency": {"program": fid, "decl_id": decl_id,
                                "file": dfile, "line": line},
                 "deduplication_basis": "One package per logical declaration id in its owning program."},
            )

        for ref_record in model.get("references") or []:
            status = ref_record.get("status") or ref_record.get("resolution")
            if status not in ("unresolved", "ambiguous", "partial", "unsupported"):
                continue
            ref = {"kind": "logical_data_reference", "program": fid,
                   "file": ref_record.get("source_file") or fid,
                   "line": ref_record.get("line"),
                   "name": ref_record.get("name"), "status": status,
                   "evidence": ref_record.get("text") or ref_record.get("statement"),
                   "candidates": ref_record.get("candidates")}
            key = "data-reference|%s|%s|%s|%s" % (
                fid, ref.get("line"), ref.get("name"), status)
            add_issue(
                key, "DATA_REFERENCE_" + status.upper(),
                "Resolve data reference " + str(ref.get("name")),
                "The logical data model did not establish this reference.",
                [ref], affected_by(fid), ["data_integrity"],
                "Which declaration does this data reference denote, and is that relationship unambiguous?",
                "An unresolved producer/consumer can invalidate dataflow and interface assumptions.",
                "Trace the source reference to a declaration using qualification and copybook provenance; document the exact declaration or ambiguity.",
                {"category": "data_integrity", "title": "Resolve data reference " + str(ref.get("name")),
                 "reason": "The existing logical model records this reference as " + str(status) + ".",
                 "expected_outcome": "The source reference is tied to one established declaration or recorded with its candidate set.",
                 "completion_condition": "The reference's declaration target and provenance are evidenced, or its unresolved status is explicitly carried into planning.",
                 "dependency": {"program": fid, "line": ref.get("line"),
                                "name": ref.get("name")},
                 "deduplication_basis": "One package per source program, line, identifier, and recorded resolution status."},
            )

        for op in flow.get("operations") or []:
            if op.get("status") in (None, "established"):
                continue
            ref = _operation_ref(fid, op)
            key = "operation|%s|%s" % (fid, op.get("op_id") or op.get("line"))
            add_issue(
                key, "DATAFLOW_" + str(op.get("status")).upper(),
                "Resolve dataflow operation in " + fid,
                "The operation is not fully established by the existing dataflow records.",
                [ref], affected_by(fid), ["data_integrity"],
                "Which operands and receivers participate in this operation, and are their declarations established?",
                "Planning a data transformation against a partial operation may change data effects.",
                "Review the cited operation, its operands/receivers and declarations; establish or document unresolved flow endpoints.",
                {"category": "data_integrity", "title": "Resolve dataflow operation in " + fid,
                 "reason": "The operation status is " + str(op.get("status")) + ".",
                 "expected_outcome": "An evidence-backed operation with established operands and receiver relationships.",
                 "completion_condition": "All operation endpoints are resolved or explicitly documented as unsupported/unresolved.",
                 "dependency": {"program": fid, "op_id": op.get("op_id"), "line": op.get("line")},
                 "deduplication_basis": "One package per operation id; source-line fallback is used only when no id exists."},
            )

        rules = flow.get("rules") or {}
        candidates_by_condition = {
            c.get("condition_id"): c for c in (rules.get("candidates") or [])
            if c.get("condition_id")
        }
        for condition in flow.get("conditions") or []:
            operands = [condition.get("left"), condition.get("right"),
                        condition.get("left_operand"), condition.get("right_operand")]
            bad_operands = [o for o in operands if isinstance(o, dict)
                            and o.get("resolution") in
                            ("unresolved", "ambiguous", "partial", "unsupported")]
            if condition.get("status") in (None, "established") and not bad_operands:
                continue
            cond_id = condition.get("cond_id") or condition.get("condition_id")
            candidate = candidates_by_condition.get(cond_id) or {}
            rule_id = candidate.get("rule_id")
            key = ("rule|" + str(rule_id) if rule_id else
                   "condition|%s|%s" % (fid, cond_id or condition.get("line")))
            ref = {"kind": "condition", "program": fid,
                   "condition_id": cond_id, "line": condition.get("line"),
                   "status": condition.get("status"),
                   "evidence": condition.get("evidence"),
                   "left": condition.get("left") or condition.get("left_operand"),
                   "right": condition.get("right") or condition.get("right_operand"),
                   "unresolved_operands": bad_operands}
            add_issue(
                key, "UNRESOLVED_CONDITION",
                "Establish decision condition in " + fid,
                "The condition or one of its operands is not fully established by existing records.",
                [ref], direct_programs((fid,)), ["business_logic", "data_integrity"],
                "What values and declarations does this condition compare, and are its branches complete?",
                "An unresolved condition can change which operations or business paths are planned.",
                "Trace the condition operands to their declarations and review both branch bodies and source scope; preserve any unsupported resolution as explicit uncertainty.",
                {"category": "business_logic", "title": "Establish decision condition in " + fid,
                 "reason": "The decision condition or an operand has unresolved status.",
                 "expected_outcome": "A source-backed comparison with resolved operand declarations and reviewed branch boundaries.",
                 "completion_condition": "Both operands and relevant branches are established or explicitly documented as unsupported/unresolved.",
                 "dependency": {"program": fid, "condition_id": cond_id,
                                "rule_id": rule_id, "line": condition.get("line")},
                 "deduplication_basis": "Merged into its existing partial rule package by rule_id when available; otherwise one package per condition id."},
            )

        for candidate in rules.get("candidates") or []:
            status = candidate.get("status")
            if status not in ("partial", "unsupported"):
                continue
            ref = {"kind": "rule_candidate", "program": fid,
                   "rule_id": candidate.get("rule_id"),
                   "decision_id": candidate.get("decision_id"),
                   "line": candidate.get("line"),
                   "condition_text": candidate.get("condition_text"),
                   "status": status,
                   "then_ops": candidate.get("then_ops") or [],
                   "else_ops": candidate.get("else_ops") or []}
            key = "rule|%s" % (candidate.get("rule_id") or
                               "%s:%s" % (fid, candidate.get("line")))
            add_issue(
                key, "RULE_CANDIDATE_" + status.upper(),
                "Review partial rule candidate in " + fid,
                "The source structure is only partially established; it is not a verified business requirement.",
                [ref], affected_by(fid), ["business_logic"],
                "What business decision and branch behavior does this source condition represent, if any?",
                "A partial source candidate does not establish all branch effects or business meaning.",
                "Review the condition, every THEN/ELSE operation, and authoritative business documentation; record the verified behavior without inferring meaning from identifiers.",
                {"category": "business_logic", "title": "Review partial rule candidate " + str(candidate.get("rule_id")),
                 "reason": "Rule candidate status is " + str(status) + ".",
                 "expected_outcome": "A source-backed description of branch structure and independently verified business meaning, if established.",
                 "completion_condition": "All candidate branches are reviewed, the behavior is evidenced, and any business interpretation is independently validated or left explicit as unknown.",
                 "dependency": {"program": fid, "rule_id": candidate.get("rule_id"),
                                "decision_id": candidate.get("decision_id")},
                 "deduplication_basis": "One package per existing rule_id; candidate evidence is not merged by similar condition text."},
            )

    # Attach XFD and dependency finding references to already-created package
    # objects after all evidence sources have been traversed.
    for key, refs in edge_issue_refs.items():
        if key in work:
            work[key]["evidence_refs"] = _sorted_refs(work[key]["evidence_refs"] + refs)
    for key, refs in mapping_issue_refs.items():
        if key in work:
            work[key]["evidence_refs"] = _sorted_refs(work[key]["evidence_refs"] + refs)

    # If a finding is the sole evidence for an interface package, the XFD
    # issue loop created it; if it matches an existing edge/mapping, its ref
    # was merged above. This pass ensures no evidence disappears.
    for f, source_context in assessment_findings:
        if f.get("classification") not in ("risk", "violation"):
            continue
        fid = f.get("finding_id")
        key = finding_to_package.get((source_context, fid))
        if key and key in work:
            work[key]["evidence_refs"] = _sorted_refs(
                work[key]["evidence_refs"] + [_finding_ref(f, source_context)])

    # Construct assessments after issue propagation is complete.
    program_rows: List[dict] = []
    for fid in programs:
        pf = per_file.get(fid) or {}
        flow = dataflow.get(fid)
        model = logical.get(fid)
        pissues = sorted(program_issues[fid].values(),
                         key=lambda x: (x["code"], x["title"],
                                        _stable_json(x["evidence_refs"])))
        accepted = pf.get("status") == "analyzed"
        enough_records = (flow is not None and model is not None)
        not_assessable = not enough_records
        if not_assessable:
            state = "not_assessable"
            reasons = [{
                "code": "INSUFFICIENT_ANALYSIS_RECORDS",
                "title": "Insufficient source evidence",
                "detail": "The logical model or dataflow records needed for the readiness dimensions are unavailable.",
                "evidence_refs": [_file_ref(fid, pf.get("status"), pf.get("reason"))],
            }] + pissues
            questions = [_question(
                "What source and project records are missing for this program?",
                "Without logical and dataflow records, readiness dimensions cannot be meaningfully assessed.",
                "Restore/index the source and produce the existing per-file, logical, and dataflow evidence; then reassess.",
                reasons[0]["evidence_refs"], True)]
            questions.extend(_question(
                issue.get("unresolved_question") or issue["title"],
                issue.get("why_it_matters") or issue["detail"],
                issue.get("verify") or "Review the cited records and source evidence.",
                issue.get("evidence_refs") or [], True)
                for issue in pissues)
        elif pissues:
            state = "investigation_required"
            reasons = pissues
            questions = [_question(
                issue.get("unresolved_question") or issue["title"],
                issue.get("why_it_matters") or issue["detail"],
                issue.get("verify") or "Review the cited records and source evidence.",
                issue.get("evidence_refs") or [], True)
                for issue in pissues]
        else:
            state = "ready_for_planning"
            positive_ref = _file_ref(fid, pf.get("status"), pf.get("reason"))
            reasons = [{
                "code": "SUPPORTED_SCOPE_NO_RECORDED_BLOCKER",
                "title": "Planning may begin within represented scope",
                "detail": "Per-file analysis was accepted and logical/dataflow records are present; this assessment found no blocker in the explicitly checked records.",
                "evidence_refs": [positive_ref],
            }]
            questions = []

        # No rule candidate is a limitation, never proof that business logic
        # is absent. Keep this explicit even when it is not a blocker.
        rule_cov = ((flow or {}).get("rules") or {}).get("coverage") or {}
        rule_candidates = ((flow or {}).get("rules") or {}).get("candidates") or []
        decisions = (flow or {}).get("decisions") or []
        if not rule_candidates:
            qrefs = [_file_ref(fid, pf.get("status"), pf.get("reason"))]
            if flow is not None:
                qrefs.append({"kind": "rule_coverage", "program": fid,
                              "candidate_count": rule_cov.get("candidates_total", 0),
                              "unsupported_count": rule_cov.get("unsupported_total", 0),
                              "decision_count": len(decisions)})
            questions.append(_question(
                "Does this program contain important business decision logic not represented by a supported rule candidate?",
                "Zero candidates do not establish that business rules are absent; candidate discovery is limited to existing source-structure models.",
                "Review procedural source, decision documentation, and business-owned rule inventories; record relevant decisions or confirm the scope of the review.",
                qrefs, False))

        # If the analysis exists but contains no CALL/COPY records, preserve a
        # non-blocking question rather than interpreting silence as proof.
        outgoing = [e for e in edges if e.get("from") == fid]
        if not outgoing and accepted:
            questions.append(_question(
                "Are there external or indirect dependencies not represented by the indexed dependency records?",
                "The absence of recorded dependency edges is limited to existing scanners and the indexed project inputs.",
                "Compare the dependency inventory with build/link configuration and operational invocation records.",
                [_file_ref(fid, pf.get("status"))], False))

        # Dimension-specific evidence sets.
        source_refs = [_file_ref(fid, pf.get("status"), pf.get("reason"))]
        if model is not None:
            source_refs.append({"kind": "logical_program_model", "program": fid,
                                "declaration_count": len(model.get("declarations") or []),
                                "reference_count": len(model.get("references") or []),
                                "unsupported_structure_count": len(model.get("unsupported_structures") or [])})
        if flow is not None:
            source_refs.append({"kind": "dataflow_program_model", "program": fid,
                                "operation_count": len(flow.get("operations") or []),
                                "condition_count": len(flow.get("conditions") or []),
                                "decision_count": len(flow.get("decisions") or []),
                                "unsupported_statement_count": len(flow.get("unsupported_statements") or [])})
        if pf.get("result"):
            for d in pf["result"].get("diagnostics") or []:
                source_refs.append({
                    "kind": "parser_diagnostic", "finding_id": d.get("finding_id"),
                    "code": d.get("code"), "classification": d.get("classification"),
                    "file": fid, "line": d.get("line"),
                    "col": d.get("col"), "message": d.get("message"),
                    "context_line": d.get("context_line")})
        for u in ((flow or {}).get("unsupported_statements") or []):
            source_refs.append({"kind": "unsupported_construct", "file": u.get("file") or fid,
                                "line": u.get("line"), "structure": u.get("structure"),
                                "reason": u.get("reason"), "evidence": u.get("text")})
        rule_unsupported = ((flow or {}).get("rules") or {}).get("unsupported") or []
        for u in rule_unsupported:
            source_refs.append({"kind": "unsupported_rule_structure",
                                "file": u.get("source_file") or fid,
                                "line": u.get("line"), "structure": u.get("structure"),
                                "rule_id": u.get("rule_id"), "reason": u.get("reason"),
                                "evidence": u.get("evidence")})
        for u in (model or {}).get("unsupported_structures") or []:
            source_refs.append({"kind": "unsupported_declaration", "file": u.get("file") or fid,
                                "line": u.get("line"), "name": u.get("name"),
                                "reason": u.get("reason") or u.get("unsupported_reason")})
        source_status = ("insufficient" if not (accepted or enough_records) else
                         "accepted_within_frozen_subset" if accepted and not any(
                             r.get("kind", "").startswith("unsupported")
                             for r in source_refs) else "partial")

        dim_refs = {k: [] for k in ("source_understanding", "data_integrity",
                                    "interface_dependency", "business_logic")}
        for issue in pissues:
            for dim in issue.get("dimensions", []):
                if dim in dim_refs:
                    dim_refs[dim].extend(issue.get("evidence_refs") or [])
        for f, source_context in assessment_findings:
            if fid in finding_programs(f, source_context):
                ref = _finding_ref(f, source_context)
                if f.get("code", "").startswith("SEM_"):
                    dim_refs["data_integrity"].append(ref)
                elif f.get("code", "").startswith("XFD_"):
                    dim_refs["data_integrity"].append(ref)
                    dim_refs["interface_dependency"].append(ref)
                elif f.get("code", "").startswith("DEP_"):
                    dim_refs["interface_dependency"].append(ref)
        for e in edges:
            if e.get("from") == fid or fid in affected_by(e.get("to")):
                dim_refs["interface_dependency"].append(_edge_ref(e))
        for m in mappings:
            if fid in affected_by_many((m.get("from"), m.get("to"))):
                dim_refs["interface_dependency"].append(_mapping_ref(m))
        if flow:
            for candidate in rule_candidates:
                dim_refs["business_logic"].append({
                    "kind": "rule_candidate", "program": fid,
                    "rule_id": candidate.get("rule_id"),
                    "decision_id": candidate.get("decision_id"),
                    "line": candidate.get("line"),
                    "status": candidate.get("status"),
                    "condition_text": candidate.get("condition_text"),
                    "then_ops": candidate.get("then_ops") or [],
                    "else_ops": candidate.get("else_ops") or []})
            for d in decisions:
                dim_refs["business_logic"].append({
                    "kind": "decision", "program": fid,
                    "decision_id": d.get("decision_id"),
                    "line": d.get("line"), "condition": d.get("condition") or d.get("condition_text"),
                    "has_else": d.get("has_else")})
            for u in (flow.get("unsupported_statements") or []):
                dim_refs["business_logic"].append({
                    "kind": "unsupported_construct", "file": u.get("file") or fid,
                    "line": u.get("line"), "structure": u.get("structure"),
                    "reason": u.get("reason"), "evidence": u.get("text")})
            for u in ((flow.get("rules") or {}).get("unsupported") or []):
                dim_refs["business_logic"].append({
                    "kind": "unsupported_rule_structure",
                    "file": u.get("source_file") or fid,
                    "line": u.get("line"), "structure": u.get("structure"),
                    "rule_id": u.get("rule_id"), "reason": u.get("reason"),
                    "evidence": u.get("evidence")})

        def dim_status(name: str, default: str) -> str:
            if not (accepted or enough_records):
                return "insufficient"
            if dim_refs[name]:
                return "investigation_required"
            return default

        unsupported_keys = {
            (u.get("line"), u.get("structure"))
            for u in (((flow or {}).get("unsupported_statements") or [])
                      + rule_unsupported)
        }
        dimensions = {
            "source_understanding": {
                "status": source_status,
                "summary": ("Per-file parser accepted this program within the frozen subset." if accepted else
                            "Per-file parser rejected this program; supplemental records are partial and do not replace the missing parse." if enough_records else
                            "No sufficient per-file/logical/dataflow record set is available."),
                "parser_status": pf.get("status"),
                "unsupported_statements": len(unsupported_keys),
                "unsupported_declarations": len((model or {}).get("unsupported_structures") or []),
                "evidence_refs": _sorted_refs(source_refs),
            },
            "data_integrity": {
                "status": dim_status("data_integrity", "no_blocker_recorded"),
                "summary": "Recorded SEM/XFD risks, storage uncertainty, unresolved logical references, and dataflow endpoint status; no runtime behavior is inferred.",
                "risk_findings": [f["finding_id"] for f, context in assessment_findings
                                  if fid in finding_programs(f, context)
                                  and (f.get("code", "").startswith("SEM_")
                                       or f.get("code", "").startswith("XFD_"))],
                "unknown_storage_declarations": sum(
                    1 for d in ((model or {}).get("declarations") or [])
                    if d.get("status") in ("partial", "unsupported", "unresolved")
                    or d.get("unsupported_reason")
                    or (d.get("byte_length") is None and not d.get("children"))),
                "evidence_refs": _sorted_refs(dim_refs["data_integrity"]),
            },
            "interface_dependency": {
                "status": dim_status("interface_dependency", "no_blocker_recorded"),
                "summary": "CALL/COPY edge resolution and CALL USING mapping statuses are assessed independently; established endpoint declarations do not make an incomplete mapping a verified contract.",
                "outgoing_edges": len(outgoing),
                "incomplete_mappings": sum(1 for m in mappings
                                            if m.get("status") != "established"
                                            and fid in affected_by_many((m.get("from"), m.get("to")))),
                "evidence_refs": _sorted_refs(dim_refs["interface_dependency"]),
            },
            "business_logic": {
                "status": dim_status("business_logic", "source_structure_only_or_no_candidates"),
                "decision_count": len(decisions),
                "candidate_count": len(rule_candidates),
                "partial_candidates": sum(1 for c in rule_candidates
                                           if c.get("status") == "partial"),
                "unsupported_structures": len(unsupported_keys),
                "disclaimer": "Candidates are source structure, not verified business requirements; no candidates does not prove absence of business logic.",
                "evidence_refs": _sorted_refs(dim_refs["business_logic"]),
            },
        }
        supporting = _sorted_refs(
            [ref for reason in reasons for ref in reason.get("evidence_refs", [])]
            + [ref for dim in dimensions.values() for ref in dim.get("evidence_refs", [])])
        program_rows.append({
            "program": fid, "readiness_state": state,
            "reasons": reasons, "supporting_evidence_refs": supporting,
            "unresolved_questions": questions,
            "dimensions": dimensions,
            "limitations": LIMITATIONS + ([
                "The frozen-subset parser rejected this program; supplemental scans are not a substitute for accepted whole-program parsing."
            ] if pf.get("status") == "rejected" else []),
            "assumption_ids": all_assumption_ids,
            "blocking_requirement_count": len(pissues) if state in
                ("investigation_required", "not_assessable") else 0,
            "work_package_ids": sorted(
                wp["work_package_id"] for wp in work.values()
                if fid in wp["affected_programs"]),
        })

    # Work packages for unreadable/skipped input have no inferred file kind.
    skipped_inputs = []
    for item in sorted(skipped, key=lambda x: (x.get("path", ""), x.get("code", ""))):
        ref = {"kind": "skipped_input", "path": item.get("path"),
               "code": item.get("code"), "reason": item.get("reason")}
        skipped_inputs.append(ref)
        key = "skipped|%s|%s" % (item.get("path"), item.get("code"))
        work[key] = {
            "work_package_id": _id("wp-", key),
            "category": "source_understanding",
            "title": "Restore or classify skipped project input " + str(item.get("path")),
            "affected_programs": [],
            "affected_dependency": {"path": item.get("path")},
            "reason": item.get("reason") or "The input was not indexed.",
            "evidence_refs": [ref], "prerequisites": [],
            "expected_outcome": "The input is indexed as a supported source/dependency or explicitly classified as outside the project scope.",
            "completion_condition": "The skipped input's identity, kind, and effect on project boundaries are established from source/build evidence.",
            "blocking_for_planning": True,
            "deduplication_basis": "One package per skipped path and ingestion code.",
        }

    # Add explicit parser-rejection/no-evidence disposition for unreadable
    # program files which are indexed but have no supplemental record. They
    # already receive a program report; package creation stays source-keyed.
    work_packages = sorted(work.values(),
                           key=lambda w: (w["category"], w["title"],
                                          w["work_package_id"]))
    by_state = {s: sum(1 for p in program_rows
                       if p["readiness_state"] == s) for s in STATES}
    program_by_id = {p["program"]: p for p in program_rows}

    # Shared target aggregation uses distinct dependent programs, not edge
    # count. Repeated COPY/CALL occurrences remain in `edges` and are retained
    # in evidence refs; the dependent count is intentionally logical-program
    # count.
    target_edges: Dict[str, List[dict]] = defaultdict(list)
    for e in edges:
        if e.get("to"):
            target_edges[e["to"]].append(e)
    shared_dependencies = []
    for target, rows in sorted(target_edges.items()):
        dependents = set(affected_by(target))
        if file_kind.get(target) == "program":
            # A target program is the provider, not its own dependent.
            dependents.discard(target)
        dependents = sorted(dependents)
        if len(dependents) < 2:
            continue
        shared_dependencies.append({
            "dependency": target,
            "dependency_kind": file_kind.get(target, "external_or_unindexed"),
            "dependent_programs": dependents,
            "readiness_states": {p: program_by_id[p]["readiness_state"]
                                  for p in dependents if p in program_by_id},
            "edge_occurrences": len(rows),
            "evidence_refs": _sorted_refs([_edge_ref(e) for e in rows]),
            "note": "Shared dependency is counted by distinct logical program dependents; edge occurrences remain separate evidence records.",
        })

    unresolved_interfaces = []
    for m in mappings:
        if m.get("status") == "established":
            continue
        unresolved_interfaces.append({
            "caller": m.get("from"), "callee": m.get("to"),
            "target": m.get("target"), "line": m.get("line"),
            "status": m.get("status"),
            "affected_programs": affected_by_many((m.get("from"), m.get("to"))),
            "evidence_refs": [_mapping_ref(m)],
        })
    unresolved_interfaces.sort(key=lambda x: (x.get("caller") or "",
                                               x.get("line") or 0,
                                               x.get("target") or ""))

    unsupported_constructs = []
    parser_rejections = []
    for fid in programs:
        pf = per_file.get(fid) or {}
        if pf.get("status") == "rejected":
            result = pf.get("result") or {}
            parser_rejections.append({
                "program": fid, "reason": pf.get("reason"),
                "diagnostics": [{
                    "finding_id": d.get("finding_id"), "code": d.get("code"),
                    "classification": d.get("classification"),
                    "line": d.get("line"), "col": d.get("col"),
                    "message": d.get("message"),
                    "evidence_ref": {"kind": "parser_diagnostic",
                                     "finding_id": d.get("finding_id"),
                                     "file": fid, "line": d.get("line"),
                                     "col": d.get("col"), "code": d.get("code"),
                                     "classification": d.get("classification"),
                                     "context_line": d.get("context_line")},
                } for d in (result.get("diagnostics") or [])],
                "affected_programs": affected_by(fid),
            })
        flow = dataflow.get(fid) or {}
        model = logical.get(fid) or {}
        for u in (flow.get("unsupported_statements") or []):
            unsupported_constructs.append({
                "file": u.get("file") or fid, "line": u.get("line"),
                "structure": u.get("structure"), "reason": u.get("reason"),
                "evidence_ref": {"kind": "unsupported_construct",
                                 "file": u.get("file") or fid,
                                 "line": u.get("line"),
                                 "structure": u.get("structure"),
                                 "evidence": u.get("text")},
                "affected_programs": affected_by(fid),
            })
        for u in ((flow.get("rules") or {}).get("unsupported") or []):
            unsupported_constructs.append({
                "file": u.get("source_file") or fid,
                "line": u.get("line"),
                "structure": u.get("structure") or "unsupported rule structure",
                "reason": u.get("reason"),
                "evidence_ref": {"kind": "unsupported_rule_structure",
                                 "file": u.get("source_file") or fid,
                                 "line": u.get("line"),
                                 "rule_id": u.get("rule_id"),
                                 "structure": u.get("structure"),
                                 "evidence": u.get("evidence"),
                                 "reason": u.get("reason")},
                "affected_programs": affected_by(fid),
            })
        for u in (model.get("unsupported_structures") or []):
            unsupported_constructs.append({
                "file": u.get("file") or u.get("source_file") or fid,
                "line": u.get("line"),
                "structure": u.get("name") or u.get("structure") or "declaration",
                "reason": u.get("reason") or u.get("unsupported_reason"),
                "evidence_ref": {"kind": "unsupported_declaration",
                                 "file": u.get("file") or u.get("source_file") or fid,
                                 "line": u.get("line"), "decl_id": u.get("decl_id"),
                                 "name": u.get("name"),
                                 "reason": u.get("reason") or u.get("unsupported_reason")},
                "affected_programs": affected_by(fid),
            })
    unsupported_by_location: Dict[Tuple[str, Optional[int], str], dict] = {}
    for u in unsupported_constructs:
        key = (u["file"], u.get("line"), u.get("structure") or "")
        entry = unsupported_by_location.setdefault(key, {
            "file": u["file"], "line": u.get("line"),
            "structure": u.get("structure"), "reasons": [],
            "evidence_refs": [], "affected_programs": [],
        })
        if u.get("reason") and u["reason"] not in entry["reasons"]:
            entry["reasons"].append(u["reason"])
        entry["evidence_refs"].append(u["evidence_ref"])
        entry["affected_programs"] = sorted(set(
            entry["affected_programs"] + u["affected_programs"]))
    unsupported_constructs = [
        {**unsupported_by_location[k],
         "reason": " ".join(unsupported_by_location[k]["reasons"]) or None,
         "evidence_refs": _sorted_refs(unsupported_by_location[k]["evidence_refs"])}
        for k in sorted(unsupported_by_location,
                        key=lambda k: (k[0], k[1] or 0, k[2]))]
    parser_rejections.sort(key=lambda x: x["program"])

    cross_program_risks = [
        {"work_package_id": w["work_package_id"], "category": w["category"],
         "title": w["title"], "affected_programs": w["affected_programs"],
         "evidence_refs": w["evidence_refs"]}
        for w in work_packages if len(w["affected_programs"]) > 1
    ]

    # Count blockers as distinct program issue keys, not severity points.
    queue = sorted(
        [{"program": p["program"],
          "blocking_requirement_count": p["blocking_requirement_count"],
          "readiness_state": p["readiness_state"],
          "work_package_ids": p["work_package_ids"]}
         for p in program_rows if p["blocking_requirement_count"] > 0],
        key=lambda x: (-x["blocking_requirement_count"], x["program"]))

    if not programs or all(p["readiness_state"] == "not_assessable"
                           for p in program_rows):
        project_state = "not_assessable"
    elif (all(p["readiness_state"] == "ready_for_planning"
              for p in program_rows) and not skipped):
        project_state = "ready_for_planning"
    else:
        project_state = "investigation_required"

    project_reasons = []
    if project_state == "ready_for_planning":
        project_reasons.append({
            "code": "ALL_INDEXED_PROGRAMS_READY",
            "detail": "Every indexed program meets the deterministic planning-readiness rules and no inputs were skipped.",
            "evidence_refs": [_file_ref(p["program"], "analyzed")
                              for p in program_rows],
        })
    elif project_state == "not_assessable":
        project_reasons.append({
            "code": "PROJECT_EVIDENCE_INSUFFICIENT",
            "detail": "No indexed program has sufficient analysis records for a meaningful project readiness determination.",
            "evidence_refs": skipped_inputs,
        })
    else:
        project_reasons.append({
            "code": "PROJECT_HAS_UNRESOLVED_PREREQUISITES",
            "detail": "At least one program or input is not ready for planning; project readiness does not inherit the state of its most-ready component.",
            "evidence_refs": _sorted_refs(
                [ref for p in program_rows if p["readiness_state"] != "ready_for_planning"
                 for ref in p["supporting_evidence_refs"]] + skipped_inputs),
        })

    return {
        "classification_rules": CLASSIFICATION_RULES,
        "limitations": LIMITATIONS,
        "assumptions": [{"id": a.get("id"), "topic": a.get("topic"),
                         "detail": a.get("detail")}
                        for a in sorted(assumptions, key=lambda a: a.get("id", ""))],
        "project": {
            "readiness_state": project_state,
            "reasons": project_reasons,
            "program_count": len(programs),
            "counts_by_state": by_state,
            "skipped_inputs": skipped_inputs,
            "programs_with_most_investigation_requirements": queue,
            "shared_dependencies": shared_dependencies,
            "unresolved_interfaces": unresolved_interfaces,
            "unsupported_constructs": unsupported_constructs,
            "parser_rejections": parser_rejections,
            "cross_program_risks": cross_program_risks,
            "planning_prerequisites": [
                {"work_package_id": w["work_package_id"], "title": w["title"],
                 "affected_programs": w["affected_programs"]}
                for w in work_packages if w["blocking_for_planning"]],
            "note": ("Project readiness is derived from all indexed program states and skipped inputs; a ready component does not make the whole application ready. The queue is ordered by distinct investigation-item count then path, not by risk score or severity."),
        },
        "programs": program_rows,
        "work_packages": work_packages,
        "note": ("Readiness means evidence-backed readiness to begin detailed modernization planning within the represented analysis scope only; it is not permission to migrate and does not establish runtime equivalence."),
    }
