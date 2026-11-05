"""NecroSpec project-level intelligence overview (Milestone 9).

Consolidates the existing M1–M8 analysis results into one deterministic,
evidence-backed project assessment. Nothing here re-analyses source:
every number is derived from records the engines already produced
(files, per_file statuses, dependency edges, cross-file mappings,
logical models, dataflow programs, decisions, rule candidates and
findings). Aggregates carry navigation identifiers (file ids, finding
ids, lines) instead of decorative counters.

Counting rules (documented in the overview-counting-rules assumption):
  * a physical source file is an entry of `files` (+`skipped`); a
    logical program is a per-file program entry; copybooks are counted
    separately and never as programs;
  * a dependency relationship is one entry of `edges` — totals are
    partitioned by resolution (resolved / missing / ambiguous /
    dynamic / unresolved) with no double counting;
  * a finding is one entry of `findings`; the register groups risks by
    code for compactness but keeps every finding id, file and line —
    findings are never merged away;
  * per-program decision/rule/operation totals are summed from each
    program's own section; a program contributes to exactly one row;
  * rejected files remain in the inventory; rejection (frozen-grammar
    parse) does not mean the scanner layers produced nothing — the
    coverage dimensions state their own denominators;
  * coverage dimensions are never combined into a single percentage.
"""
from typing import Dict, List

OVERVIEW_NOTE = (
    "Aggregates are derived from existing analysis records; navigation "
    "rows cite file, line and finding identifiers. Coverage dimensions "
    "have different denominators and are deliberately not combined into "
    "one percentage.")


def build_overview(files: List[dict], skipped: List[dict],
                   per_file: Dict[str, dict], edges: List[dict],
                   cycles: List[List[str]], cross_file: dict,
                   findings: List[dict]) -> dict:
    xfc = cross_file.get("coverage", {})
    df = cross_file.get("dataflow") or {}
    dfc = df.get("coverage", {})
    programs = [f for f in files if f.get("kind") == "program"]
    copybooks = [f for f in files if f.get("kind") == "copybook"]

    def pf(fid: str) -> dict:
        return per_file.get(fid) or {}

    # ---- A. inventory (denominator: discovered files) -------------------
    programs_analyzed = [f["file_id"] for f in programs
                         if pf(f["file_id"]).get("status") == "analyzed"]
    programs_rejected = [f["file_id"] for f in programs
                         if pf(f["file_id"]).get("status") == "rejected"]
    flow_programs: Dict[str, dict] = df.get("programs", {})
    programs_partial = [f["file_id"] for f in programs
                        if f["file_id"] in flow_programs
                        and pf(f["file_id"]).get("status") == "rejected"]
    programs_unsupported = [fid for fid, fl in flow_programs.items()
                            if (fl.get("rules") or {}).get("coverage", {})
                            .get("unsupported_total", 0) > 0]
    inventory = {
        "files_total": len(files) + len(skipped),
        "files_indexed": len(files),
        "files_skipped": len(skipped),
        "programs_total": len(programs),
        "copybooks_total": len(copybooks),
        "files_rejected": sum(1 for f in files
                              if pf(f["file_id"]).get("status")
                              == "rejected"),
        "programs_analyzed": len(programs_analyzed),
        "programs_rejected": len(programs_rejected),
        "programs_partial_analysis": len(programs_partial),
        "programs_unsupported": len(programs_unsupported),
        "program_files_partial_analysis": sorted(programs_partial),
        "program_files_unsupported": sorted(programs_unsupported),
        "programs_with_dataflow": len(flow_programs),
        "logical_programs": xfc.get("logical_programs", 0),
        "copybooks_indexed": xfc.get("copybooks_indexed", 0),
        "program_files_analyzed": sorted(programs_analyzed),
        "program_files_rejected": sorted(programs_rejected),
        "note": ("Discovered files include rejected ones; rejection "
                 "means the frozen-grammar parse did not accept the "
                 "file, while the source-evidence scanners may still "
                 "have produced records for it."),
    }

    # ---- B. dependency intelligence (denominator: dependency edges) -----
    res_counts: Dict[str, int] = {}
    kind_counts: Dict[str, int] = {}
    for e in edges:
        res_counts[e["resolution"]] = res_counts.get(e["resolution"], 0) + 1
        kind_counts[e["kind"]] = kind_counts.get(e["kind"], 0) + 1
    unresolved_edges = [e for e in edges
                        if e["resolution"] in ("missing", "unresolved",
                                               "dynamic")]
    ambiguous_edges = [e for e in edges if e["resolution"] == "ambiguous"]
    def edge_row(e: dict) -> dict:
        return {"from": e["from"], "to": e.get("to"),
                "target": e.get("target"), "kind": e["kind"],
                "resolution": e["resolution"], "line": e.get("line"),
                "col": e.get("col"), "evidence": e.get("text")}

    dependencies = {
        "total": len(edges),
        "call_relationships": kind_counts.get("call", 0),
        "copy_relationships": kind_counts.get("copy", 0),
        "resolved": res_counts.get("resolved", 0),
        "missing": res_counts.get("missing", 0),
        "ambiguous": res_counts.get("ambiguous", 0),
        "dynamic": res_counts.get("dynamic", 0),
        "unresolved_other": res_counts.get("unresolved", 0),
        "unresolved_total": len(unresolved_edges),
        "cycles": sorted(sorted(c) for c in cycles),
        "resolved_edges": [edge_row(e) for e in sorted(
            (e for e in edges if e["resolution"] == "resolved"),
            key=lambda e: (e["from"], e.get("line") or 0, e["kind"]))],
        "note": ("One row per dependency edge; resolution partition "
                 "sums to the total."),
    }

    # ---- C. data and cross-program intelligence -------------------------
    mappings = cross_file.get("mappings", [])
    map_counts: Dict[str, int] = {}
    for m in mappings:
        map_counts[m["status"]] = map_counts.get(m["status"], 0) + 1
    links = df.get("cross_program_links", [])
    links_by_est = {"established": 0, "other": 0}
    dynamic_calls = []
    for l in links:
        if l.get("status") == "established":
            links_by_est["established"] += 1
        else:
            links_by_est["other"] += 1
    for e in edges:
        if e["kind"] == "call" and e["resolution"] == "dynamic":
            dynamic_calls.append({
                "caller": e["from"], "target": e.get("target"),
                "line": e.get("line"), "evidence": e.get("text")})
    cross_program_flows = []
    for link in links:
        cross_program_flows.append({
            "caller": link["caller"], "callee": link["callee"],
            "argument": link.get("argument"), "parameter": link.get("parameter"),
            "mapping_status": link.get("mapping_status"),
            "status": link.get("status"),
            "call_line": (link.get("call") or {}).get("line"),
            "call_evidence": (link.get("call") or {}).get("evidence"),
            "caller_writes": link.get("caller_writes") or [],
            "callee_reads": link.get("callee_reads") or [],
        })
    established_mappings = [
        {"from": m["from"], "to": m["to"], "argument": m.get("argument"),
         "parameter": m.get("parameter"), "line": m.get("line"),
         "status": m["status"],
         "evidence": m.get("text")}
        for m in mappings if m["status"] == "established"]
    data = {
        "mappings_total": len(mappings),
        "mappings_established": map_counts.get("established", 0),
        "mappings_incomplete": map_counts.get("incomplete", 0),
        "mappings_unresolved": map_counts.get("unresolved", 0),
        "cross_program_links_total": len(links),
        "cross_program_links_with_resolved_declarations": links_by_est["established"],
        "operations_total": dfc.get("operations_total", 0),
        "operations_established": dfc.get("operations_established", 0),
        "conditions_total": dfc.get("conditions_total", 0),
        "logical_declarations": xfc.get("logical_declarations", 0),
        "copybook_origin_declarations":
            xfc.get("logical_copybook_origin_declarations", 0),
        "dynamic_call_targets": sorted(
            dynamic_calls, key=lambda d: (d["caller"], d["line"])),
        "established_mappings": established_mappings,
        "cross_program_flows": sorted(
            cross_program_flows,
            key=lambda x: (x["caller"], x.get("call_line") or 0,
                           x["callee"], x.get("argument") or "")),
        "note": ("A positional argument/parameter match is a structural "
                 "mapping, not a verified runtime data contract; "
                 "incomplete mappings keep their qualification."),
    }

    # ---- D. decision and rule intelligence ------------------------------
    per_program_rules = []
    rule_candidates = []
    programs_without_candidates = []
    for fid in sorted(flow_programs):
        fl = flow_programs[fid]
        rules = fl.get("rules") or {}
        rc = rules.get("coverage", {})
        decs = fl.get("decisions") or []
        row = {
            "program": fid,
            "decisions": len(decs),
            "candidates": rc.get("candidates_total", 0),
            "candidates_partial": rc.get("candidates_partial", 0),
            "unsupported_structures": rc.get("unsupported_total", 0),
        }
        per_program_rules.append(row)
        for candidate in rules.get("candidates") or []:
            rule_candidates.append({
                "program": fid, "rule_id": candidate["rule_id"],
                "decision_id": candidate.get("decision_id"),
                "line": candidate.get("line"),
                "end_line": candidate.get("end_line"),
                "status": candidate.get("status"),
                "condition_text": candidate.get("condition_text"),
                "then_ops": candidate.get("then_ops") or [],
                "else_ops": candidate.get("else_ops") or [],
                "origin": candidate.get("origin"),
            })
        if not rc.get("candidates_total"):
            # Unsupported structures remain separately counted and visible;
            # they do not create an established or partial rule candidate.
            programs_without_candidates.append(fid)
    decisions_rules = {
        "decisions_total": dfc.get("decisions_total", 0),
        "decisions_with_else": dfc.get("decisions_with_else", 0),
        "nested_decisions": dfc.get("nested_decisions", 0),
        "conditions_total": dfc.get("conditions_total", 0),
        "rules_total": dfc.get("rules_total", 0),
        "rules_established_structure":
            dfc.get("rules_established_structure", 0),
        "rules_partial": dfc.get("rules_partial", 0),
        "rules_unsupported": dfc.get("rules_unsupported", 0),
        "programs_without_candidates": programs_without_candidates,
        "per_program": per_program_rules,
        "candidates": sorted(rule_candidates,
                              key=lambda x: (x["program"], x.get("line") or 0,
                                             x["rule_id"])),
        "disclaimer": ("Rule candidates represent discovered source "
                       "structure — a condition and the operations of "
                       "its branches. They are not verified business "
                       "requirements, and no business meaning is "
                       "inferred."),
    }

    # ---- E. risk and investigation register ------------------------------
    def finding_source(f: dict) -> dict:
        """Resolve the finding's primary source location without guessing.

        Engine detail schemas differ: dependency details use `file`,
        cross-program details use `caller_file`, and semantic findings use
        `program` + `statement_line` (their `file` may instead be the
        copybook declaration location, retained in the original evidence).
        Project-wide records such as a cycle may have no single location.
        """
        detail = f.get("detail") or {}
        file_id = (detail.get("program") or detail.get("caller_file")
                   or detail.get("file"))
        line = detail.get("statement_line") or f.get("line")
        return {"file": file_id, "line": line, "col": f.get("col")}

    def finding_row(f: dict) -> dict:
        loc = finding_source(f)
        return {"finding_id": f["finding_id"], "code": f["code"],
                "severity": f["severity"], "file": loc["file"],
                "line": loc["line"], "col": loc["col"],
                "message": f.get("message"),
                "evidence": f.get("evidence"), "hint": f.get("hint")}

    violations = [finding_row(f) for f in findings
                  if f["classification"] == "violation"]
    notes = [finding_row(f) for f in findings
             if f["classification"] == "note"]
    risks_by_code: Dict[str, dict] = {}
    for f in findings:
        if f["classification"] != "risk":
            continue
        entry = risks_by_code.setdefault(
            f["code"], {"code": f["code"], "count": 0, "finding_ids": [],
                        "locations": [], "findings": []})
        row = finding_row(f)
        entry["count"] += 1
        entry["finding_ids"].append(f["finding_id"])
        entry["locations"].append({"file": row["file"],
                                   "line": row["line"]})
        entry["findings"].append(row)
    for entry in risks_by_code.values():
        entry["findings"] = sorted(
            entry["findings"],
            key=lambda x: (x.get("file") or "", x.get("line") or 0,
                           x["finding_id"]))
        entry["finding_ids"] = [x["finding_id"] for x in entry["findings"]]
        entry["locations"] = sorted(
            entry["locations"],
            key=lambda x: (x.get("file") or "", x.get("line") or 0))
    unsupported_structures = []
    for fid in sorted(flow_programs):
        for u in flow_programs[fid].get("unsupported_statements") or []:
            unsupported_structures.append({
                "file": fid, "line": u.get("line"),
                "structure": u.get("structure"),
                "reason": u.get("reason")})
    incomplete_mappings = [
        {"from": m["from"], "to": m.get("to"), "argument": m.get("argument"),
         "parameter": m.get("parameter"), "line": m.get("line"),
         "status": m["status"], "evidence": m.get("text")}
        for m in mappings if m["status"] != "established"]
    register = {
        "violations": sorted(
            violations, key=lambda v: (v["code"], v.get("file") or "",
                                       v.get("line") or 0)),
        "violations_total": len(violations),
        "risks_total": sum(e["count"] for e in risks_by_code.values()),
        "risks_by_code": sorted(risks_by_code.values(),
                                key=lambda e: (-e["count"], e["code"])),
        "notes_total": len(notes),
        "notes": notes,
        "unsupported_structures": sorted(
            unsupported_structures,
            key=lambda u: (u["file"], u.get("line") or 0)),
        "unresolved_dependencies": [
            {"from": e["from"], "to": e.get("to"),
             "kind": e["kind"], "resolution": e["resolution"],
             "line": e.get("line"), "evidence": e.get("text")}
            for e in sorted(unresolved_edges,
                            key=lambda e: (e["from"],
                                           e.get("line") or 0))],
        "ambiguous_dependencies": [
            edge_row(e) for e in sorted(ambiguous_edges,
                                        key=lambda e: (e["from"],
                                                       e.get("line") or 0))],
        "incomplete_mappings": sorted(
            incomplete_mappings,
            key=lambda m: (m["from"], m.get("line") or 0)),
        "human_review_total": sum(
            1 for f in findings if f["classification"] == "risk"),
        "note": ("Every row retains its original classification, "
                 "finding id and source location; grouped risk counts "
                 "list the underlying finding ids and are never merged."),
    }

    # ---- F. coverage dimensions (separate denominators) ------------------
    n_prog = len(programs)
    with_decisions = sum(1 for r in per_program_rules
                         if r["decisions"] > 0)
    with_candidates = sum(1 for r in per_program_rules
                          if r["candidates"] > 0)
    coverage = {
        "dimensions": [
            {"dimension": "frozen-subset parse",
             "covered": len(programs_analyzed),
             "denominator": n_prog,
             "note": "programs fully accepted by the frozen grammar"},
            {"dimension": "statement scan",
             "covered": len(flow_programs),
             "denominator": n_prog,
             "note": "programs included in the existing source-evidence scan; "
                     "this does not imply every statement was recognized "
                     "or that analysis is complete"},
            {"dimension": "decision structure",
             "covered": with_decisions,
             "denominator": n_prog,
             "note": "programs with at least one established decision"},
            {"dimension": "rule candidates",
             "covered": with_candidates,
             "denominator": n_prog,
             "note": "programs with at least one established or partial "
                     "candidate"},
        ],
        "unsupported_constructs_total": len(unsupported_structures),
        "unresolved_relationships_total":
            len(unresolved_edges) + map_counts.get("unresolved", 0),
        "assumptions_total": None,  # filled by the caller
        "note": ("Dimensions use different denominators and are "
                 "reported separately; a low result is not a clean or "
                 "safe result."),
    }

    return {
        "inventory": inventory,
        "dependencies": dependencies,
        "data": data,
        "decisions_rules": decisions_rules,
        "register": register,
        "coverage": coverage,
        "note": OVERVIEW_NOTE,
    }
