"""Milestone 10 readiness rules and migration work-package evidence."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from necro.project import analyze_project, ingest_directory
from necro.readiness import build_readiness


def sample_envelope():
    name, entries = ingest_directory("examples/sample-project")
    return analyze_project(name, entries)


def minimal_inputs(file_id="src/CLEAN.cbl", *, status="analyzed",
                   with_models=True, skipped=None, findings=None):
    files = [{"file_id": file_id, "kind": "program"}]
    per_file = {file_id: {"status": status, "reason": None,
                          "result": {"diagnostics": []}}}
    cross_file = {"mappings": []}
    if with_models:
        cross_file["logical"] = {file_id: {
            "program": file_id, "declarations": [], "references": [],
            "unsupported_structures": [], "unsupported_statements": [],
        }}
        cross_file["dataflow"] = {"programs": {file_id: {
            "program": file_id, "operations": [], "conditions": [],
            "decisions": [], "unsupported_statements": [],
            "rules": {"candidates": [], "unsupported": [], "coverage": {
                "candidates_total": 0, "candidates_partial": 0,
                "unsupported_total": 0}},
        }}}
    assumptions = [{"id": "test-assumption", "topic": "Test assumption",
                    "detail": "Evidence scope is synthetic for unit testing."}]
    return {
        "files": files, "skipped": skipped or [], "per_file": per_file,
        "edges": [], "cycles": [], "cross_file": cross_file,
        "findings": findings or [], "assumptions": assumptions,
    }


def minimal_report(**kwargs):
    return build_readiness(**minimal_inputs(**kwargs))


def by_program(report, fid):
    return next(p for p in report["programs"] if p["program"] == fid)


def test_ready_for_planning_requires_accepted_source_and_both_models():
    r = minimal_report()
    p = by_program(r, "src/CLEAN.cbl")
    assert p["readiness_state"] == "ready_for_planning"
    assert p["reasons"][0]["code"] == "SUPPORTED_SCOPE_NO_RECORDED_BLOCKER"
    assert p["supporting_evidence_refs"]
    assert p["unresolved_questions"]  # zero candidates / no edges are explicit, non-blocking checks
    assert all(not q["blocking_for_planning"] for q in p["unresolved_questions"])
    assert p["limitations"] and p["assumption_ids"] == ["test-assumption"]
    assert r["project"]["readiness_state"] == "ready_for_planning"


def test_not_assessable_when_logical_or_dataflow_records_are_missing():
    args = minimal_inputs(status="rejected", with_models=False)
    args["per_file"]["src/CLEAN.cbl"]["reason"] = "single-file parse rejected"
    args["per_file"]["src/CLEAN.cbl"]["result"]["diagnostics"] = [{
        "finding_id": "f-parser", "code": "ERR_GRAMMAR_UNEXPECTED_TOKEN",
        "classification": "unsupported", "severity": "error",
        "line": 4, "col": 8, "layer": "Grammar",
        "message": "Unsupported source token", "context_line": "BAD TOKEN",
    }]
    r = build_readiness(**args)
    p = by_program(r, "src/CLEAN.cbl")
    assert p["readiness_state"] == "not_assessable"
    assert {x["code"] for x in p["reasons"]} >= {
        "INSUFFICIENT_ANALYSIS_RECORDS", "SOURCE_PARSER_REJECTED",
        "REQUIRED_ANALYSIS_RECORD_MISSING"}
    assert any("f-parser" in json.dumps(q["evidence_refs"])
               for q in p["unresolved_questions"])
    assert any(w["category"] == "source_understanding"
               and "readiness evidence" in w["title"]
               for w in r["work_packages"])
    assert r["project"]["readiness_state"] == "not_assessable"


def test_rejected_program_with_supplemental_records_requires_investigation():
    args = minimal_inputs(status="rejected")
    args["per_file"]["src/CLEAN.cbl"]["reason"] = "lexical rejection"
    args["per_file"]["src/CLEAN.cbl"]["result"]["diagnostics"] = [{
        "finding_id": "f-reject", "code": "ERR_LEX_INVALID_WORD",
        "classification": "unsupported", "severity": "error",
        "line": 5, "col": 17, "layer": "Lexical",
        "message": "Unexpected quote", "context_line": "CALL \"X\"",
    }]
    r = build_readiness(**args)
    p = by_program(r, "src/CLEAN.cbl")
    assert p["readiness_state"] == "investigation_required"
    assert any(x["code"] == "SOURCE_PARSER_REJECTED" for x in p["reasons"])
    w = [x for x in r["work_packages"] if "rejected source" in x["title"]]
    assert len(w) == 1 and any(ref.get("finding_id") == "f-reject"
                               for ref in w[0]["evidence_refs"])


def test_sample_project_aggregates_all_states_without_a_score():
    env = sample_envelope()
    r = env["migration_readiness"]
    assert env["schema_version"] == 8
    assert r["project"]["readiness_state"] == "investigation_required"
    assert r["project"]["counts_by_state"] == {
        "ready_for_planning": 0,
        "investigation_required": 12,
        "not_assessable": 0,
    }
    assert sum(r["project"]["counts_by_state"].values()) == 12
    text = json.dumps(r, sort_keys=True).lower()
    assert "confidence_score" not in text and "readiness_score" not in text
    assert "score" not in r["project"]
    assert "all indexed program states" in r["project"]["note"]


def test_evalfix_rejection_and_unsupported_evaluate_are_both_visible():
    r = sample_envelope()["migration_readiness"]
    p = by_program(r, "src/EVALFIX.cbl")
    assert p["readiness_state"] == "investigation_required"
    assert p["dimensions"]["source_understanding"]["parser_status"] == "rejected"
    assert p["dimensions"]["business_logic"]["candidate_count"] == 0
    assert p["dimensions"]["business_logic"]["unsupported_structures"] == 1
    assert any(q["blocking_for_planning"] is False
               and "zero candidates" in q["why_it_matters"].lower()
               for q in p["unresolved_questions"])
    unsupported = r["project"]["unsupported_constructs"]
    eval_rows = [x for x in unsupported if x["file"] == "src/EVALFIX.cbl"
                 and x["line"] == 13 and x["structure"] == "EVALUATE"]
    assert len(eval_rows) == 1
    assert {x["kind"] for x in eval_rows[0]["evidence_refs"]} == {
        "unsupported_construct", "unsupported_rule_structure"}
    eval_wp = [w for w in r["work_packages"] if "EVALUATE" in w["title"]]
    assert len(eval_wp) == 1
    assert any(ref.get("kind") == "unsupported_construct"
               and ref.get("line") == 13 for ref in eval_wp[0]["evidence_refs"])


def test_program_with_no_candidates_retains_nonblocking_business_question():
    r = sample_envelope()["migration_readiness"]
    p = by_program(r, "src/AUDITER.cbl")
    assert p["dimensions"]["business_logic"]["candidate_count"] == 0
    assert p["dimensions"]["business_logic"]["disclaimer"].startswith("Candidates are source structure")
    assert any("zero candidates" in q["why_it_matters"].lower()
               for q in p["unresolved_questions"])


def test_per_file_data_risks_are_included_and_keep_classification():
    r = sample_envelope()["migration_readiness"]
    p = by_program(r, "src/GLUPDATE.cbl")
    assert p["dimensions"]["data_integrity"]["status"] == "investigation_required"
    refs = p["dimensions"]["data_integrity"]["evidence_refs"]
    assert any(x.get("kind") == "finding"
               and x.get("code") == "SEM_PRECISION_LOSS"
               and x.get("classification") == "risk"
               and x.get("file") == "src/GLUPDATE.cbl" for x in refs)


def test_dynamic_missing_and_ambiguous_dependencies_have_work_packages():
    r = sample_envelope()["migration_readiness"]
    packages = r["work_packages"]
    dynamic = [w for w in packages if "dynamic CALL target" in w["title"]]
    missing = [w for w in packages if "missing COPY dependency PAYCODES" in w["title"]]
    ambiguous = [w for w in packages if "Disambiguate COPY dependency USRINFO" in w["title"]]
    assert len(dynamic) == len(missing) == len(ambiguous) == 1
    assert "src/PAYROLL.cbl" in dynamic[0]["affected_programs"]
    assert "src/EMPREC.cbl" in missing[0]["affected_programs"]
    assert "src/REPORT.cbl" in ambiguous[0]["affected_programs"]
    assert any(ref.get("resolution") == "dynamic" for ref in dynamic[0]["evidence_refs"])
    assert any(ref.get("resolution") == "missing" for ref in missing[0]["evidence_refs"])
    assert any(ref.get("resolution") == "ambiguous"
               and len(ref.get("candidates", [])) == 2
               for ref in ambiguous[0]["evidence_refs"])


def test_incomplete_mapping_is_one_call_package_with_prerequisites():
    r = sample_envelope()["migration_readiness"]
    matches = [w for w in r["work_packages"]
               if (w.get("affected_dependency") or {}).get("caller") == "src/AUDTOTAL.cbl"
               and (w.get("affected_dependency") or {}).get("line") == 16]
    assert len(matches) == 1
    w = matches[0]
    assert w["category"] == "interface_dependency"
    assert len(w["prerequisites"]) == 2
    assert any(x.get("kind") == "call_using_mapping" and x.get("status") == "incomplete"
               for x in w["evidence_refs"])
    assert any(x.get("kind") == "dependency_edge" and x.get("resolution") == "resolved"
               for x in w["evidence_refs"])
    assert any(x.get("kind") == "finding" and x.get("code") == "XFD_PARAM_SIZE_MISMATCH"
               and x.get("classification") == "risk" for x in w["evidence_refs"])
    assert w["expected_outcome"] and w["completion_condition"]
    assert "position alone" in w["completion_condition"]


def test_copybook_cycle_propagates_to_callers_with_edge_evidence():
    r = sample_envelope()["migration_readiness"]
    w = [x for x in r["work_packages"] if "copybook cycle" in x["title"].lower()]
    assert len(w) == 1
    assert w[0]["affected_programs"] == ["src/CYCTEST.cbl"]
    assert any(x.get("kind") == "dependency_edge"
               and x.get("from") == "src/CYCTEST.cbl"
               and x.get("to") == "copybooks/P.cpy"
               for x in w[0]["evidence_refs"])
    shared = next(x for x in r["project"]["shared_dependencies"]
                  if x["dependency"] == "src/GLUPDATE.cbl")
    assert shared["dependent_programs"] == [
        "src/AUDTOTAL.cbl", "src/BILLING.cbl", "src/DECISIONS.cbl",
        "src/PAYROLL.cbl"]
    # A rejected called program affects its caller; the CALL edge is cited.
    auditer = [w for w in r["work_packages"]
               if w["title"] == "Review rejected source in src/AUDITER.cbl"][0]
    assert "src/FEEDER.cbl" in auditer["affected_programs"]
    assert any(x.get("from") == "src/FEEDER.cbl"
               and x.get("to") == "src/AUDITER.cbl"
               for x in auditer["evidence_refs"] if x.get("kind") == "dependency_edge")


def test_work_packages_keep_source_evidence_and_unique_ids():
    r = sample_envelope()["migration_readiness"]
    ids = [w["work_package_id"] for w in r["work_packages"]]
    assert len(ids) == len(set(ids))
    for w in r["work_packages"]:
        assert w["title"] and w["reason"] and w["evidence_refs"]
        assert w["expected_outcome"] and w["completion_condition"]
        assert w["deduplication_basis"]
    missing = [w for w in r["work_packages"] if "PAYCODES" in w["title"]][0]
    assert any(ref.get("kind") == "finding"
               and ref.get("classification") == "violation"
               and ref.get("code") == "DEP_COPYBOOK_MISSING"
               for ref in missing["evidence_refs"])


def test_unknown_storage_declaration_creates_one_package():
    args = minimal_inputs()
    fid = "src/CLEAN.cbl"
    args["cross_file"]["logical"][fid]["declarations"] = [{
        "decl_id": "decl-1", "program": fid, "source_file": fid,
        "name": "WS-OPAQUE", "line": 8, "status": "unsupported",
        "byte_length": None, "picture": None, "usage": "COMP-99",
        "unsupported_reason": "unsupported storage usage", "children": [],
    }]
    args["cross_file"]["logical"][fid]["unsupported_structures"] = [{
        "decl_id": "decl-1", "file": fid, "line": 8, "name": "WS-OPAQUE",
        "reason": "unsupported storage usage",
    }]
    r = build_readiness(**args)
    assert by_program(r, fid)["readiness_state"] == "investigation_required"
    packages = [w for w in r["work_packages"]
                if (w.get("affected_dependency") or {}).get("decl_id") == "decl-1"]
    assert len(packages) == 1
    assert any(ref.get("kind") == "logical_declaration"
               and ref.get("byte_length") is None for ref in packages[0]["evidence_refs"])


def test_unresolved_conditions_and_operations_are_blockers():
    args = minimal_inputs()
    fid = "src/CLEAN.cbl"
    flow = args["cross_file"]["dataflow"]["programs"][fid]
    flow["conditions"] = [{"cond_id": "cond-x", "program": fid,
                           "line": 11, "status": "partial",
                           "evidence": "IF WS-X = 1"}]
    flow["operations"] = [{"op_id": "op-x", "program": fid,
                           "line": 12, "type": "MOVE", "status": "unresolved",
                           "evidence": "MOVE WS-X TO WS-Y"}]
    r = build_readiness(**args)
    p = by_program(r, fid)
    assert p["readiness_state"] == "investigation_required"
    assert any(w["work_package_id"] in p["work_package_ids"]
               and w["category"] == "business_logic"
               for w in r["work_packages"])
    assert any(w["category"] == "data_integrity"
               and any(x.get("op_id") == "op-x" for x in w["evidence_refs"])
               for w in r["work_packages"])


def test_project_does_not_inherit_readiness_from_a_clean_program():
    clean = minimal_inputs("src/CLEAN.cbl")
    other = "src/OTHER.cbl"
    clean["files"].append({"file_id": other, "kind": "program"})
    clean["per_file"][other] = {"status": "rejected", "reason": "parser rejection",
        "result": {"diagnostics": [{"finding_id": "other-parse", "code": "ERR_X",
            "classification": "unsupported", "line": 2, "col": 8,
            "message": "unsupported"}]}}
    clean["cross_file"]["logical"][other] = {"declarations": [], "references": [],
        "unsupported_structures": []}
    clean["cross_file"]["dataflow"]["programs"][other] = {
        "operations": [], "conditions": [], "decisions": [],
        "unsupported_statements": [], "rules": {"candidates": [], "unsupported": [], "coverage": {}}}
    clean["edges"] = [{"kind": "call", "from": "src/CLEAN.cbl", "to": other,
        "target": "OTHER", "resolution": "resolved", "line": 9,
        "col": 8, "text": "CALL OTHER"}]
    r = build_readiness(**clean)
    assert by_program(r, "src/CLEAN.cbl")["readiness_state"] == "investigation_required"
    assert by_program(r, other)["readiness_state"] == "investigation_required"
    assert r["project"]["readiness_state"] == "investigation_required"
    assert r["project"]["counts_by_state"]["ready_for_planning"] == 0


def test_skipped_inputs_block_project_readiness_and_are_reported():
    args = minimal_inputs(skipped=[{"path": "src/UNREAD.cbl", "code": "READ_ERROR",
                                  "reason": "permission denied"}])
    r = build_readiness(**args)
    assert by_program(r, "src/CLEAN.cbl")["readiness_state"] == "ready_for_planning"
    assert r["project"]["readiness_state"] == "investigation_required"
    assert r["project"]["skipped_inputs"][0]["path"] == "src/UNREAD.cbl"
    assert any("UNREAD.cbl" in w["title"] for w in r["work_packages"])


def test_migration_readiness_is_deterministic():
    a = json.dumps(sample_envelope()["migration_readiness"], sort_keys=True,
                   separators=(",", ":"))
    b = json.dumps(sample_envelope()["migration_readiness"], sort_keys=True,
                   separators=(",", ":"))
    assert a == b


def test_single_file_contract_remains_exactly_twelve_keys():
    from necro.analyzer import analyze

    source = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. OKAY.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 X PIC 9.
       LINKAGE SECTION.
       01 LK-X PIC 9.
       PROCEDURE DIVISION.
           MOVE 1 TO X.
           GOBACK.
"""
    result = analyze(source, "OK.cbl")
    assert result["schema_version"] == 2
    assert set(result) == {
        "assumptions", "ast", "coverage", "diagnostics", "layers", "meta",
        "references", "schema_version", "semantic_counts", "summary",
        "symbols", "tokens",
    }
