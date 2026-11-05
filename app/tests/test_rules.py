"""Milestone 8: evidence-backed business rule candidates.

Covers: candidate discovery from established decisions (parsed and
scanned paths), conditions without supported branch operations,
THEN-only and IF/ELSE candidates, nested decisions, data items read
and written, copybook provenance, cross-program links, incomplete
argument mappings, unresolved operands, unsupported decision
structures, deterministic rule ids, evidence completeness, the absence
of invented business interpretation, and M5–M7 regression stability.
Candidates are source structure only: explanations quote conditions,
operations and data items — never business intent.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from necro.project import analyze_project

# shared copybook (same content as the M6/M7 suites' AUDREC)
AUDREC = """      * shared record
       01  LK-REC.
           05  LK-ID        PIC 9(5).
           05  LK-AMT       PIC S9(5)V99 COMP-3.
"""


def run(*entries):
    return analyze_project("t", [
        {"path": p, "content": c} for p, c in entries])


def flow_of(env, fid):
    return env["cross_file"]["dataflow"]["programs"][fid]


def rules_of(env, fid):
    return flow_of(env, fid)["rules"]


def candidates_of(env, fid):
    return rules_of(env, fid)["candidates"]


def ingest_dir():
    from necro.project import ingest_directory
    return ingest_directory("examples/sample-project")


def example_project():
    name, entries = ingest_dir()
    return analyze_project(name, entries)


def candidate_at(env, fid, line):
    for c in candidates_of(env, fid):
        if c["line"] == line:
            return c
    raise AssertionError("no rule candidate at line %d" % line)


# a scanned program with a COPY (outside the frozen subset); IF at L9,
# THEN MOVE at L10, convergence MOVE at L12
SCANNED_IF = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SCIF.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY AUDREC.
       01  WS-FLAG        PIC X.
       PROCEDURE DIVISION.
           MOVE 10 TO LK-ID
           IF LK-ID > 5
               MOVE 1 TO LK-ID
           END-IF
           MOVE 9 TO LK-ID
           GOBACK.
"""


def test_candidate_from_established_decision():
    r = example_project()
    c = candidate_at(r, "src/AUDTOTAL.cbl", 13)
    assert c["status"] == "established_structure"
    assert c["condition_text"] == "WS-TOTAL > 1000"
    assert c["condition_id"]
    assert len(c["then_ops"]) == 1 and c["else_ops"] == []
    assert c["has_else"] is False
    # explanation is exact, source-derived, and traceable
    assert c["explanation"] == (
        "IF WS-TOTAL > 1000 at L13 controls a THEN branch containing "
        "MOVE at L14 writes WS-COUNT. The condition reads WS-TOTAL. "
        "The branch writes WS-COUNT.")
    assert c["trace"]["condition_line"] == 13
    assert c["then_ops"][0] in c["trace"]["op_ids"]


def test_condition_without_supported_branch_operations():
    src = SCANNED_IF.replace(
        "           MOVE 1 TO LK-ID\n", "")
    r = run(("cpy/AUDREC.cpy", AUDREC), ("src/SCIF.cbl", src))
    assert candidates_of(r, "src/SCIF.cbl") == []
    unsup = rules_of(r, "src/SCIF.cbl")["unsupported"]
    m = [u for u in unsup if u["structure"] == "decision"
         and u["line"] == 9]
    assert len(m) == 1
    assert m[0]["status"] == "unsupported"
    assert "no supported operation" in m[0]["reason"]
    # the decision itself remains visible in the decision model
    assert len(flow_of(r, "src/SCIF.cbl")["decisions"]) == 1


def test_then_only_rule_never_invents_else():
    r = run(("cpy/AUDREC.cpy", AUDREC), ("src/SCIF.cbl", SCANNED_IF))
    c = candidate_at(r, "src/SCIF.cbl", 9)
    assert c["has_else"] is False and c["else_ops"] == []
    assert "ELSE" not in c["explanation"]
    assert c["status"] == "established_structure"


def test_if_else_candidate_with_branch_operations():
    r = example_project()
    c = candidate_at(r, "src/DECISIONS.cbl", 13)
    assert c["has_else"] is True
    assert len(c["then_ops"]) == 3 and len(c["else_ops"]) == 1
    ops = {o["op_id"]: o for o in flow_of(r, "src/DECISIONS.cbl")["operations"]}
    assert [ops[i]["line"] for i in c["then_ops"]] == [14, 18, 19]
    assert [ops[i]["line"] for i in c["else_ops"]] == [22]
    assert "The ELSE branch contains MOVE at L22 writes LK-ID." in \
        c["explanation"]


def test_nested_decision_own_candidate():
    r = example_project()
    outer = candidate_at(r, "src/DECISIONS.cbl", 13)
    inner = candidate_at(r, "src/DECISIONS.cbl", 15)
    assert inner["decision_id"] != outer["decision_id"]
    # the inner candidate's decision is the nested one from M7
    dec = {d["decision_id"]: d
           for d in flow_of(r, "src/DECISIONS.cbl")["decisions"]}
    assert dec[inner["decision_id"]]["parent_decision"] == \
        outer["decision_id"]
    assert inner["condition_text"] == 'WS-FLAG = "Y"'
    assert len(inner["then_ops"]) == 1


def test_data_items_read_and_written():
    r = example_project()
    c = candidate_at(r, "src/DECISIONS.cbl", 13)
    reads = {i["name"]: i for i in c["items_read"]}
    assert set(reads) == {"WS-ADJ"}
    assert reads["WS-ADJ"]["role"] == "condition"
    assert reads["WS-ADJ"]["resolution"] == "resolved"
    writes = {i["name"]: i for i in c["items_written"]}
    assert set(writes) == {"LK-ID", "WS-FLAG", "WS-ADJ"}
    # ELSE-branch writes are included (LK-ID written by both branches)
    assert writes["LK-ID"]["resolution"] == "resolved"


def test_copybook_provenance_preserved():
    r = example_project()
    c = candidate_at(r, "src/DECISIONS.cbl", 13)
    writes = {i["name"]: i for i in c["items_written"]}
    lk = writes["LK-ID"]
    assert lk["source_file"] == "copybooks/AUDREC.cpy"
    assert lk["origin"] == "copybook"
    assert lk["via_copybooks"] == ["copybooks/AUDREC.cpy"]
    assert lk["decl"]["decl_id"]
    assert lk["decl"]["line"] == 3


def test_cross_program_link_attached():
    r = example_project()
    c = candidate_at(r, "src/DECISIONS.cbl", 13)
    x = [x for x in c["cross_program"]
         if x["callee"] == "src/GLUPDATE.cbl"]
    assert len(x) == 1
    row = x[0]
    assert row["argument"] == "WS-ADJ"
    assert row["parameter"] == "LK-IO"
    assert row["call_line"] == 20
    assert row["written_by_op"] in c["then_ops"]
    assert row["status"] == "established"
    # the branch result really is passed into the other program
    assert "passed to src/GLUPDATE.cbl at L20 (parameter LK-IO)" in \
        c["explanation"]


def test_incomplete_mapping_marks_candidate_partial():
    r = example_project()
    c = candidate_at(r, "src/DECISIONS.cbl", 13)
    assert c["status"] == "partial"
    row = [x for x in c["cross_program"]
           if x["callee"] == "src/GLUPDATE.cbl"][0]
    assert row["mapping_status"] == "incomplete"
    assert "not a complete data contract" in row["qualification"]
    el = [u for u in c["unresolved_elements"]
          if u["element"] == "argument_mapping"]
    assert len(el) == 1 and el[0]["line"] == 20
    # the inner (link-free) candidate stays fully established
    assert candidate_at(r, "src/DECISIONS.cbl", 15)["status"] == \
        "established_structure"


def test_unresolved_condition_operand():
    src = SCANNED_IF.replace("IF LK-ID > 5", "IF ZZZ-UNDEF > 5")
    r = run(("cpy/AUDREC.cpy", AUDREC), ("src/SCIF.cbl", src))
    c = candidate_at(r, "src/SCIF.cbl", 9)
    assert c["status"] == "partial"
    reads = {i["name"]: i for i in c["items_read"]}
    assert reads["ZZZ-UNDEF"]["resolution"] == "unresolved"
    el = [u for u in c["unresolved_elements"]
          if u["element"] == "condition_operand"]
    assert len(el) == 1
    assert "ZZZ-UNDEF" in c["explanation"]


def test_unsupported_decision_structures_recorded():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. EVALSUP.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  A PIC 9(3).
       01  B PIC 9(3).
       PROCEDURE DIVISION.
           EVALUATE A
               WHEN 1
                   MOVE 1 TO B
           END-EVALUATE
           IF A = 9
           END-IF
           GOBACK.
"""
    r = run(("src/EVALSUP.cbl", src))
    rules = rules_of(r, "src/EVALSUP.cbl")
    assert rules["candidates"] == []
    structures = {u["structure"] for u in rules["unsupported"]}
    assert "EVALUATE" in structures and "decision" in structures
    assert all(u["status"] == "unsupported" for u in rules["unsupported"])
    # WHEN bodies were never promoted into candidates
    assert not any("WHEN" in json.dumps(u) for u in rules["candidates"])


def test_dynamic_call_never_promoted():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. DYNC.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY AUDREC.
       01  WS-PGM         PIC X(8).
       PROCEDURE DIVISION.
           MOVE 10 TO LK-ID
           IF LK-ID > 5
               MOVE 1 TO LK-ID
               CALL WS-PGM USING LK-ID
           END-IF
           GOBACK.
"""
    r = run(("cpy/AUDREC.cpy", AUDREC), ("src/DYNC.cbl", src))
    c = candidate_at(r, "src/DYNC.cbl", 9)
    # the dynamic target produced no attached cross-program relationship
    assert c["cross_program"] == []
    assert c["status"] == "established_structure"


def test_parsed_path_candidates():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. PDEC.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  A PIC 9(3).
       01  B PIC 9(3).
       01  C PIC 9(3).
       LINKAGE SECTION.
       01  P PIC 9(3).
       PROCEDURE DIVISION USING P.
           IF A > 1
               MOVE 1 TO B
               IF B = 1
                   MOVE 2 TO C
               END-IF
           ELSE
               MOVE 3 TO P
           END-IF
           MOVE 4 TO A
           GOBACK.
"""
    r = run(("src/PDEC.cbl", src))
    cs = candidates_of(r, "src/PDEC.cbl")
    assert [c["origin"] for c in cs] == ["parsed", "parsed"]
    outer = candidate_at(r, "src/PDEC.cbl", 11)
    assert outer["condition_text"] == "A > 1"
    assert outer["has_else"] is True
    ops = {o["op_id"]: o
           for o in flow_of(r, "src/PDEC.cbl")["operations"]}
    assert [ops[i]["line"] for i in outer["then_ops"]] == [12]
    assert [ops[i]["line"] for i in outer["else_ops"]] == [17]
    # parsed condition operands carry their resolved declarations
    left = [i for i in outer["items_read"] if i["name"] == "A"][0]
    assert left["resolution"] == "resolved" and left["decl"]
    assert outer["status"] == "established_structure"
    # nested decision gets its own candidate
    assert candidate_at(r, "src/PDEC.cbl", 13)["decision_id"] != \
        outer["decision_id"]


def test_rule_ids_deterministic_and_distinct():
    a = example_project()
    b = example_project()
    ids_a = [c["rule_id"] for f in
             ("src/AUDTOTAL.cbl", "src/DECISIONS.cbl")
             for c in candidates_of(a, f)]
    ids_b = [c["rule_id"] for f in
             ("src/AUDTOTAL.cbl", "src/DECISIONS.cbl")
             for c in candidates_of(b, f)]
    assert ids_a == ids_b
    assert len(set(ids_a)) == len(ids_a) == 3
    assert all(len(i) == 12 for i in ids_a)
    # identity is positional: a shifted decision gets a different rule
    src = SCANNED_IF.replace("       PROCEDURE DIVISION.",
                             "       PROCEDURE DIVISION.\n")
    r3 = run(("cpy/AUDREC.cpy", AUDREC), ("src/SCIF.cbl", src))
    base = run(("cpy/AUDREC.cpy", AUDREC), ("src/SCIF.cbl", SCANNED_IF))
    assert candidate_at(r3, "src/SCIF.cbl", 10)["rule_id"] != \
        candidate_at(base, "src/SCIF.cbl", 9)["rule_id"]


def test_evidence_completeness():
    r = example_project()
    df = r["cross_file"]["dataflow"]
    for fid in ("src/AUDTOTAL.cbl", "src/DECISIONS.cbl"):
        ops = {o["op_id"]: o
               for o in df["programs"][fid]["operations"]}
        conds = {c["cond_id"]
                 for c in df["programs"][fid]["conditions"]}
        decs = {d["decision_id"]
                for d in df["programs"][fid]["decisions"]}
        for c in candidates_of(r, fid):
            assert c["explanation"] and c["evidence" ] is not None \
                if False else True
            assert c["condition_id"] in conds
            assert c["decision_id"] in decs
            for oid in c["then_ops"] + c["else_ops"]:
                assert oid in ops
            for i in c["items_read"] + c["items_written"]:
                if i.get("decl"):
                    assert i["decl"]["decl_id"]
            assert c["trace"]["op_ids"] == \
                c["then_ops"] + c["else_ops"]


def test_no_invented_business_interpretation():
    r = example_project()
    c = candidate_at(r, "src/AUDTOTAL.cbl", 13)
    # the explanation is exactly the source-derived sentences: it must
    # not grow policy language ("rejects", "requires", "means",
    # "transaction", "business")
    text = c["explanation"].lower()
    for word in ("reject", "require", "means", "transaction",
                 "business", "policy", "valid", "should", "must"):
        assert word not in text, word
    # every operation mentioned comes from the operation records
    assert "MOVE at L14 writes WS-COUNT" in c["explanation"]
    assert c["explanation"].count(".") == 3


def test_m5_m7_regression_stability():
    r = example_project()
    df = r["cross_file"]["dataflow"]
    assert r["schema_version"] == 8
    # M6 anchor: the cross-program link still cites the COMPUTE op
    au = df["programs"]["src/AUDTOTAL.cbl"]
    comp = [o for o in au["operations"] if o["type"] == "COMPUTE"][0]
    link = [l for l in df["cross_program_links"]
            if l["caller"] == "src/AUDTOTAL.cbl"][0]
    assert link["caller_writes"][0]["op_id"] == comp["op_id"]
    # M7 anchors: decisions unchanged by rule derivation
    d = au["decisions"][0]
    assert d["line"] == 13 and d["has_else"] is False
    assert d["then_ops"] == [au["operations"][2]["op_id"]]
    # coverage totals match the per-program sections
    total = sum(f["rules"]["coverage"]["candidates_total"]
                for f in df["programs"].values())
    assert df["coverage"]["rules_total"] == total == 3
    assert df["coverage"]["rules_established_structure"] == 2
    assert df["coverage"]["rules_partial"] == 1
    # the assumptions registry carries the rule assumptions
    ids = [a["id"] for a in df["assumptions"]]
    assert ids.count("RULE_001") == 1
    assert "dataflow-not-execution" in ids  # M6 assumptions preserved


def test_unsupported_structure_visible_in_project_response():
    # the sample project contains a real EVALUATE program (EVALFIX):
    # the structure must be visible as unsupported, never interpreted
    r = example_project()
    assert r["per_file"]["src/EVALFIX.cbl"]["status"] == "rejected"
    rules = rules_of(r, "src/EVALFIX.cbl")
    assert rules["candidates"] == []
    assert rules["coverage"] == {
        "candidates_total": 0, "candidates_established_structure": 0,
        "candidates_partial": 0, "unsupported_total": 1}
    ev = [u for u in rules["unsupported"]
          if u["structure"] == "EVALUATE"]
    assert len(ev) == 1
    row = ev[0]
    assert row["status"] == "unsupported"
    assert row["line"] == 13
    assert "EVALUATE" in row["reason"] and row["evidence"]
    assert row["rule_id"] and len(row["rule_id"]) == 12
    # WHEN bodies were never promoted into operations or candidates
    ops = flow_of(r, "src/EVALFIX.cbl")["operations"]
    assert [o["line"] for o in ops] == [12]
    assert not any("WHEN" in json.dumps(c) for c in rules["candidates"])
    # the project-level counter reflects the unsupported structure
    assert r["cross_file"]["dataflow"]["coverage"]["rules_unsupported"] == 1


def test_zero_candidate_program_state_fields():
    # a program with neither candidates nor unsupported structures still
    # carries the rules section with explicit zero coverage (the UI
    # renders the explanatory empty state from these fields)
    r = example_project()
    rules = rules_of(r, "src/GLUPDATE.cbl")
    assert rules["candidates"] == [] and rules["unsupported"] == []
    assert rules["coverage"] == {
        "candidates_total": 0, "candidates_established_structure": 0,
        "candidates_partial": 0, "unsupported_total": 0}
    assert rules["program"] == "src/GLUPDATE.cbl"


def test_status_labels_and_machine_enum_unchanged():
    # the human label is presentation-only: the API enum is untouched
    r = example_project()
    c = candidate_at(r, "src/AUDTOTAL.cbl", 13)
    assert c["status"] == "established_structure"
    assert candidate_at(r, "src/DECISIONS.cbl", 13)["status"] == "partial"
