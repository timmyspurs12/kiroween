"""Milestone 9: whole-project intelligence overview.

Covers: inventory totals with discovered-vs-analysed distinction,
dependency aggregation (resolution partition, kinds, cycles),
cross-program mapping aggregation, decision/rule status aggregation,
EVALUATE visibility, zero-candidate programs, human-review coverage,
deterministic output, navigation identifiers, duplicate-counting
boundaries, and M5–M8 stability. The overview derives every number
from existing records — no re-analysis, no combined percentage, no new
risk or confidence score.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from necro.project import analyze_project


def ingest_dir():
    from necro.project import ingest_directory
    return ingest_directory("examples/sample-project")


def example_project():
    name, entries = ingest_dir()
    return analyze_project(name, entries)


def ov_of(env):
    return env["overview"]


def test_inventory_totals_and_distinctions():
    r = example_project()
    inv = ov_of(r)["inventory"]
    assert inv["files_total"] == 18      # discovered files (incl. rejected)
    assert inv["files_skipped"] == 0
    assert inv["programs_total"] == 12   # physical program files
    assert inv["copybooks_total"] == 6   # never counted as programs
    assert inv["files_rejected"] == 11   # rejected files stay listed
    assert inv["programs_analyzed"] == 1     # frozen-grammar full parse
    assert inv["programs_rejected"] == 11
    assert inv["programs_partial_analysis"] == 11
    assert inv["programs_unsupported"] == 1
    assert inv["program_files_unsupported"] == ["src/EVALFIX.cbl"]
    assert inv["programs_with_dataflow"] == 12  # scanner layer ran anyway
    # discovered ≠ successfully analysed: both numbers coexist
    assert inv["programs_analyzed"] + inv["programs_rejected"] == \
        inv["programs_total"]
    assert inv["program_files_analyzed"] == ["src/GLUPDATE.cbl"]
    assert "src/AUDTOTAL.cbl" in inv["program_files_rejected"]
    assert "rejection" in inv["note"]


def test_dependency_aggregation_partitions_total():
    r = example_project()
    d = ov_of(r)["dependencies"]
    # single source of truth: the dependency edge list
    assert d["total"] == len(r["edges"])
    # resolution partition sums to total (no double counting)
    assert d["resolved"] + d["missing"] + d["ambiguous"] + d["dynamic"] \
        + d["unresolved_other"] == d["total"]
    assert len(d["resolved_edges"]) == d["resolved"]
    assert all(e["from"] and e["to"] and e["line"] and e["evidence"]
               for e in d["resolved_edges"])
    assert all(e["from"] and e["line"] and e["evidence"]
               for e in ov_of(r)["register"]["ambiguous_dependencies"])
    assert d["call_relationships"] + d["copy_relationships"] == d["total"]
    assert (d["resolved"], d["missing"], d["ambiguous"], d["dynamic"]) \
        == (14, 1, 1, 1)
    assert d["unresolved_total"] == 3  # missing + dynamic + other


def test_dependency_cycles_listed():
    r = example_project()
    assert ov_of(r)["dependencies"]["cycles"] == [["copybooks/P.cpy",
                                                   "copybooks/Q.cpy"]]
    assert r["cycles"] == [["copybooks/P.cpy", "copybooks/Q.cpy"]]


def test_mapping_aggregation_and_qualification():
    r = example_project()
    d = ov_of(r)["data"]
    assert d["mappings_total"] == len(r["cross_file"]["mappings"])
    assert d["mappings_established"] == 1
    assert d["mappings_incomplete"] == 4
    assert d["mappings_unresolved"] == 2
    assert d["cross_program_links_with_resolved_declarations"] == 5
    assert d["operations_established"] == d["operations_total"] == 17
    assert d["copybook_origin_declarations"] == 32
    aud_flow = [f for f in d["cross_program_flows"]
                if f["caller"] == "src/AUDTOTAL.cbl"][0]
    assert aud_flow["mapping_status"] == "incomplete"
    assert aud_flow["caller_writes"][0]["op_id"] == "66f4c6770058"
    assert aud_flow["call_line"] == 16 and aud_flow["call_evidence"]
    assert "not a verified runtime data contract" in d["note"]
    # established mapping rows carry navigation evidence (the one truly
    # established contract: FEEDER → AUDITER, equal-sized LK-REC)
    row = [m for m in d["established_mappings"]
           if m["from"] == "src/FEEDER.cbl"][0]
    assert row["to"] == "src/AUDITER.cbl"
    assert row["status"] == "established" and row["line"]
    assert "CALL" in row["evidence"]


def test_dynamic_call_targets_visible():
    r = example_project()
    dyn = ov_of(r)["data"]["dynamic_call_targets"]
    assert len(dyn) == 1
    assert dyn[0]["caller"] == "src/PAYROLL.cbl"
    assert dyn[0]["target"] == "WS-PGM" and dyn[0]["line"]


def test_rule_candidate_status_aggregation():
    r = example_project()
    dr = ov_of(r)["decisions_rules"]
    dfp = r["cross_file"]["dataflow"]["programs"]
    # per-program sums equal the project totals (no double counting)
    assert sum(x["candidates"] for x in dr["per_program"]) == \
        dr["rules_total"] == 3
    assert sum(x["candidates_partial"] for x in dr["per_program"]) == \
        dr["rules_partial"] == 1
    assert sum(x["decisions"] for x in dr["per_program"]) == \
        dr["decisions_total"] == 3
    assert (dr["rules_established_structure"], dr["rules_partial"],
            dr["rules_unsupported"]) == (2, 1, 1)
    aud_candidate = [c for c in dr["candidates"]
                     if c["rule_id"] == "b59be6a539b7"][0]
    assert aud_candidate["condition_text"] == "WS-TOTAL > 1000"
    assert aud_candidate["then_ops"]
    assert dr["decisions_with_else"] == 1
    # the partial candidate belongs to exactly one program row
    dec = [x for x in dr["per_program"]
           if x["program"] == "src/DECISIONS.cbl"][0]
    assert dec["candidates"] == 2 and dec["candidates_partial"] == 1
    # disclaimer preserved
    assert "not verified business requirements" in dr["disclaimer"]


def test_unsupported_evaluate_visible_in_register():
    r = example_project()
    reg = ov_of(r)["register"]
    ev = [u for u in reg["unsupported_structures"]
          if u["file"] == "src/EVALFIX.cbl"]
    assert len(ev) == 1
    assert ev[0]["structure"] == "EVALUATE" and ev[0]["line"] == 13
    assert "not supported" in ev[0]["reason"]
    assert ov_of(r)["coverage"]["unsupported_constructs_total"] == 1


def test_zero_candidate_programs_listed():
    r = example_project()
    dr = ov_of(r)["decisions_rules"]
    assert "src/GLUPDATE.cbl" in dr["programs_without_candidates"]
    assert "src/EVALFIX.cbl" in dr["programs_without_candidates"]
    assert "src/AUDTOTAL.cbl" not in dr["programs_without_candidates"]
    # unsupported EVALUATE means no rule candidate; it remains independently
    # visible as an unsupported structure rather than being silently omitted.
    dfp = r["cross_file"]["dataflow"]["programs"]
    for fid in dr["programs_without_candidates"]:
        assert dfp[fid]["rules"]["coverage"]["candidates_total"] == 0
    assert dfp["src/EVALFIX.cbl"]["rules"]["coverage"]["unsupported_total"] == 1


def test_register_retains_findings_without_merging():
    r = example_project()
    reg = ov_of(r)["register"]
    assert reg["violations_total"] == 1
    assert reg["violations"][0]["code"] == "DEP_COPYBOOK_MISSING"
    assert reg["violations"][0]["finding_id"]
    # grouped risk counts keep every underlying finding id
    assert reg["risks_total"] == 14 == reg["human_review_total"]
    size = [e for e in reg["risks_by_code"]
            if e["code"] == "XFD_PARAM_SIZE_MISMATCH"][0]
    assert size["count"] == 4 and len(size["finding_ids"]) == 4
    assert len({i for e in reg["risks_by_code"]
                for i in e["finding_ids"]}) == reg["risks_total"]
    # Every finding remains its own navigable row, with source evidence.
    ids = {f["finding_id"] for f in r["findings"]}
    risk_rows = [f for e in reg["risks_by_code"] for f in e["findings"]]
    assert len(risk_rows) == reg["risks_total"]
    assert {f["finding_id"] for f in risk_rows} == ids - {
        f["finding_id"] for f in r["findings"]
        if f["classification"] != "risk"}
    assert all(f["evidence"] for f in risk_rows)
    au = [f for f in risk_rows if f["finding_id"] == "a40404c2ab08"][0]
    assert au["file"] == "src/AUDTOTAL.cbl" and au["line"] == 12
    xfd = [f for f in risk_rows if f["code"] == "XFD_PARAM_SIZE_MISMATCH"
           and f["file"] == "src/AUDTOTAL.cbl"][0]
    assert xfd["line"] and "Caller:" in xfd["evidence"]
    # every register finding id exists in the envelope findings
    for e in reg["risks_by_code"]:
        assert all(i in ids for i in e["finding_ids"])
    assert reg["notes_total"] == 1


def test_coverage_dimensions_separate_denominators():
    r = example_project()
    cov = ov_of(r)["coverage"]
    dims = {d["dimension"]: d for d in cov["dimensions"]}
    assert dims["frozen-subset parse"]["covered"] == 1
    assert dims["statement scan"]["covered"] == 12
    assert dims["decision structure"]["covered"] == 2
    assert dims["rule candidates"]["covered"] == 2
    assert all(d["denominator"] == 12 for d in dims.values())
    # no single combined percentage exists anywhere in the overview
    text = json.dumps(ov_of(r))
    assert "%" not in text and "score" not in text


def test_navigation_identifiers_resolve():
    r = example_project()
    ov = ov_of(r)
    fids = {f["file_id"] for f in r["files"]}
    finding_ids = {f["finding_id"] for f in r["findings"]}
    # every program id cited anywhere exists
    for row in ov["decisions_rules"]["per_program"]:
        assert row["program"] in fids
    for fid in ov["decisions_rules"]["programs_without_candidates"]:
        assert fid in fids
    for e in (ov["register"]["unresolved_dependencies"]
              + ov["register"]["ambiguous_dependencies"]):
        assert e["from"] in fids
        assert e["line"] and e["evidence"]
    for v in ov["register"]["violations"]:
        assert v["finding_id"] in finding_ids
        assert v["file"] in fids and v["line"]
    for u in ov["register"]["unsupported_structures"]:
        assert u["file"] in fids and u["line"] and u["structure"]
    for d in ov["data"]["dynamic_call_targets"]:
        assert d["caller"] in fids and d["line"]
    for m in ov["data"]["established_mappings"]:
        assert m["from"] in fids and m["line"]


def test_overview_deterministic():
    a = json.dumps(example_project()["overview"], sort_keys=True)
    b = json.dumps(example_project()["overview"], sort_keys=True)
    assert a == b


def test_schema_additive_and_single_file_untouched():
    r = example_project()
    assert r["schema_version"] == 8
    assert "overview" in r
    # All candidate source records remain present in their original section.
    assert "programs" in r["cross_file"]["dataflow"]
    assert len(r["overview"]["decisions_rules"]["per_program"]) == 12
    # counting-rule assumption documented
    ids = [a["id"] for a in r["assumptions"]]
    assert ids.count("overview-counting-rules") == 1
    assert ov_of(r)["coverage"]["assumptions_total"] == len(ids) == 20


def test_m5_m8_records_unchanged_by_overview():
    r = example_project()
    dfp = r["cross_file"]["dataflow"]
    # M6 anchor
    au = dfp["programs"]["src/AUDTOTAL.cbl"]
    comp = [o for o in au["operations"] if o["type"] == "COMPUTE"][0]
    assert comp["op_id"] == "66f4c6770058"
    # M7 anchor
    assert au["decisions"][0]["decision_id"] == "8d5af8e696b0"
    # M8 anchors
    assert [c["rule_id"] for c in au["rules"]["candidates"]] == \
        ["b59be6a539b7"]
    assert [c["rule_id"] for c in
            dfp["programs"]["src/DECISIONS.cbl"]["rules"]["candidates"]] \
        == ["418ed530bbcb", "f9be0d402040"]
    # existing CALL qualification intact
    link = [l for l in dfp["cross_program_links"]
            if l["caller"] == "src/AUDTOTAL.cbl"][0]
    assert link["mapping_status"] == "incomplete"


def test_repeated_dependency_declarations_and_same_code_findings_are_not_deduped():
    from necro.overview import build_overview

    repeated_edges = [
        {"kind": "copy", "from": "src/A.cbl", "to": "copybooks/X.cpy",
         "target": "X", "resolution": "resolved", "line": line,
         "col": 8, "text": "COPY X."}
        for line in (4, 9)
    ]
    repeated_findings = [
        {"finding_id": fid, "code": "SEM_TRUNCATION_HIGH",
         "classification": "risk", "severity": "warning",
         "message": f"finding at {line}", "line": line, "col": 8,
         "evidence": f"source evidence L{line}",
         "detail": {"program": "src/A.cbl", "statement_line": line}}
        for fid, line in (("f-1", 4), ("f-2", 9))
    ]
    ov = build_overview(
        files=[{"file_id": "src/A.cbl", "kind": "program"},
               {"file_id": "copybooks/X.cpy", "kind": "copybook"}],
        skipped=[],
        per_file={"src/A.cbl": {"status": "analyzed"}},
        edges=repeated_edges,
        cycles=[],
        cross_file={"mappings": []},
        findings=repeated_findings,
    )
    # Each source declaration is an edge occurrence; repeated target does
    # not collapse distinct physical lines into one relationship.
    assert ov["dependencies"]["total"] == 2
    assert len(ov["dependencies"]["resolved_edges"]) == 2
    assert [e["line"] for e in ov["dependencies"]["resolved_edges"]] == [4, 9]
    # Same classification/code is compacted only at the group header;
    # each original finding id, location and evidence remains visible.
    group = ov["register"]["risks_by_code"][0]
    assert group["count"] == 2
    assert group["finding_ids"] == ["f-1", "f-2"]
    assert [f["evidence"] for f in group["findings"]] == [
        "source evidence L4", "source evidence L9"]
