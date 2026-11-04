"""Milestone 6: statement-level data-flow analysis.

Covers: parsed and scanned operation models for MOVE/COMPUTE/ADD/
SUBTRACT/MULTIPLY/DIVIDE, GIVING/ROUNDED/ON SIZE ERROR/REMAINDER,
multiple receivers, IF/ELSE/END-IF guards (nested), unsupported
EVALUATE and expressions, copybook operands/receivers, arithmetic
capacity/precision/sign risks, cross-program links (including dynamic
CALL boundaries and unresolved declarations), field_flow queries,
evidence on every operation, determinism, and single-file/project
compatibility. Negative tests prove unsupported forms never silently
become established operations.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from necro.project import PROJECT_SCHEMA_VERSION, analyze_project
from necro.dataflow import field_flow


def run(*entries):
    return analyze_project("t", [
        {"path": p, "content": c} for p, c in entries])


def flow_of(env, fid):
    return env["cross_file"]["dataflow"]["programs"][fid]


def ops_of(env, fid):
    return flow_of(env, fid)["operations"]


def findings_for(env, code):
    return [d for d in env["findings"] if d["code"] == code]


def ingest_dir():
    from necro.project import ingest_directory
    return ingest_directory("examples/sample-project")


# subset-clean program (parsed path): LINKAGE mandatory in the frozen
# grammar when a DATA DIVISION is present
PFIX_HEAD = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. PFX.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  A PIC 9(3).
       01  B PIC 9(5)V99.
       01  D PIC 9(2).
       01  E PIC 9(3).
       LINKAGE SECTION.
       01  C PIC S9(4) COMP-3.
       PROCEDURE DIVISION USING C.
"""

PFIX_OPS = PFIX_HEAD + """           COMPUTE C ROUNDED = A + B * D
               ON SIZE ERROR MOVE 0 TO C
               END-COMPUTE.
           ADD A 5 TO B.
           SUBTRACT A FROM B GIVING C.
           MULTIPLY A BY B GIVING C ROUNDED.
           DIVIDE A INTO B GIVING C.
           GOBACK.
"""


# scanned path (COPY puts the program outside the frozen grammar)
AUDREC = """      * shared record
       01  LK-REC.
           05  LK-ID        PIC 9(5).
           05  LK-AMT       PIC S9(5)V99 COMP-3.
"""

SCANNED = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SCX.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY AUDREC.
       01  WS-T PIC S9(7)V99 COMP-3.
       01  WS-N PIC 9(3).
       PROCEDURE DIVISION.
           COMPUTE WS-T ROUNDED = LK-AMT * WS-N
           ADD LK-ID 5 TO WS-N
           SUBTRACT LK-ID FROM WS-T GIVING WS-N
           MULTIPLY LK-AMT BY LK-ID GIVING WS-T ROUNDED
           DIVIDE LK-ID INTO LK-AMT GIVING WS-N REMAINDER LK-ID
           GOBACK.
"""


def test_parsed_operations_from_ast():
    r = run(("src/PFX.cbl", PFIX_OPS))
    ops = ops_of(r, "src/PFX.cbl")
    assert [(o["type"], o["origin"]) for o in ops] == [
        ("COMPUTE", "parsed"), ("ADD", "parsed"), ("SUBTRACT", "parsed"),
        ("MULTIPLY", "parsed"), ("DIVIDE", "parsed")]
    comp = ops[0]
    assert comp["status"] == "established"
    assert comp["receivers"][0]["name"] == "C"
    assert comp["receivers"][0]["rounded"] is True
    assert comp["options"]["size_error"] is True
    assert comp["expression"]["text"] == "(A + (B * D))"
    names = [o["name"] for o in comp["source_operands"]]
    assert names == ["A", "B", "D"]


def test_scanned_operations_shapes():
    r = run(("src/SCX.cbl", SCANNED), ("cpy/AUDREC.cpy", AUDREC))
    ops = ops_of(r, "src/SCX.cbl")
    assert [o["type"] for o in ops] == ["COMPUTE", "ADD", "SUBTRACT",
                                        "MULTIPLY", "DIVIDE"]
    assert all(o["origin"] == "scanned" for o in ops)
    assert all(o["status"] == "established" for o in ops)
    comp = ops[0]
    assert comp["receivers"][0]["rounded"] is True
    assert comp["expression"]["supported"] is True
    add = ops[1]
    assert add["options"]["mode"] == "TO"
    assert [o.get("name") or o.get("text")
            for o in add["source_operands"]] == [
        "LK-ID", "5", "WS-N"]        # TO-receiver is an implicit operand
    sub = ops[2]
    assert sub["options"]["giving"] is True
    roles = {o["role"]: o["name"] for o in sub["source_operands"]}
    assert roles == {"subtrahend": "LK-ID", "minuend": "WS-T"}
    mul = ops[3]
    assert {o["role"]: o["name"] for o in mul["source_operands"]} == {
        "left": "LK-AMT", "right": "LK-ID"}
    div = ops[4]
    assert div["options"]["mode"] == "INTO"
    assert div["options"]["remainder"] == "LK-ID"
    roles = {o["role"]: o["name"] for o in div["source_operands"]}
    assert roles == {"divisor": "LK-ID", "dividend": "LK-AMT",
                     "remainder": "LK-ID"}


def test_giving_and_multiple_receivers():
    prog = PFIX_HEAD + """           ADD A 5 GIVING B D.
           MOVE 1 TO A B D.
           GOBACK.
"""
    r = run(("src/PFX.cbl", prog))
    ops = ops_of(r, "src/PFX.cbl")
    add = ops[0]
    assert [t["name"] for t in add["receivers"]] == ["B", "D"]
    assert add["options"]["giving"] is True
    mv = ops[1]
    assert [t["name"] for t in mv["receivers"]] == ["A", "B", "D"]
    assert mv["status"] == "established"


def test_on_size_error_guard_flags_and_finding():
    prog = SCANNED.replace(
        "COMPUTE WS-T ROUNDED = LK-AMT * WS-N",
        "COMPUTE WS-T ROUNDED = LK-AMT * WS-N ON SIZE ERROR MOVE 0 TO WS-T")
    r = run(("src/SCX.cbl", prog), ("cpy/AUDREC.cpy", AUDREC))
    ops = ops_of(r, "src/SCX.cbl")
    comp = ops[0]
    assert comp["options"]["size_error"] is True
    guard_f = findings_for(r, "SEM_SIZE_ERROR_GUARD")
    assert len(guard_f) == 1
    assert guard_f[0]["severity"] == "info"
    assert guard_f[0]["classification"] == "note"
    # the guard suppresses capacity warnings for that receiver
    trunc = [d for d in findings_for(r, "SEM_TRUNCATION_HIGH")
             if d["detail"].get("statement_line") == 9]
    assert trunc == []


def test_divide_makes_no_precision_claims():
    r = run(("src/SCX.cbl", SCANNED), ("cpy/AUDREC.cpy", AUDREC))
    div = ops_of(r, "src/SCX.cbl")[4]
    sem = [d for d in r["findings"]
           if d["code"].startswith("SEM_")
           and (d["detail"] or {}).get("statement_line") == 14]
    trunc = [d for d in sem if d["code"] in ("SEM_TRUNCATION_HIGH",
                                             "SEM_PRECISION_LOSS")]
    assert trunc == []      # quotient precision is never established
    assert div["options"]["remainder"] == "LK-ID"


def test_if_else_guard_branches():
    prog = SCANNED + """           IF WS-N > 5
               MOVE 1 TO WS-N
           ELSE
               ADD 2 TO WS-N
           END-IF
           GOBACK.
"""
    r = run(("src/SCX.cbl", prog), ("cpy/AUDREC.cpy", AUDREC))
    fl = flow_of(r, "src/SCX.cbl")
    conds = fl["conditions"]
    assert len(conds) == 1
    c = conds[0]
    assert c["op"] == ">" and c["left"]["name"] == "WS-N"
    assert c["right"]["text"] == "5"
    ops = {o["line"]: o for o in fl["operations"]}
    then_mv = [o for o in fl["operations"] if o["line"] == 16][0]
    else_add = [o for o in fl["operations"] if o["line"] == 18][0]
    assert then_mv["guards"] == [
        {"cond_id": c["cond_id"], "branch": "then", "line": c["line"]}]
    assert else_add["guards"] == [
        {"cond_id": c["cond_id"], "branch": "else", "line": c["line"]}]
    # guard edges exist in the graph
    g = [e for e in fl["graph"]["edges"] if e["kind"] == "guard"]
    assert {(e["role"], e["from"]) for e in g} == {
        ("then", "c:" + c["cond_id"]), ("else", "c:" + c["cond_id"])}


def test_nested_conditions():
    prog = SCANNED + """           IF WS-N > 5
               IF LK-ID = 1
                   MOVE 1 TO WS-N
               END-IF
           END-IF
           GOBACK.
"""
    r = run(("src/SCX.cbl", prog), ("cpy/AUDREC.cpy", AUDREC))
    fl = flow_of(r, "src/SCX.cbl")
    assert len(fl["conditions"]) == 2
    inner = [o for o in fl["operations"] if o["line"] == 17][0]
    assert len(inner["guards"]) == 2
    assert {g["branch"] for g in inner["guards"]} == {"then"}


def test_unsupported_evaluate_recorded():
    prog = SCANNED + """           EVALUATE WS-N
               WHEN 1
                   MOVE 1 TO WS-N
           END-EVALUATE
           GOBACK.
"""
    r = run(("src/SCX.cbl", prog), ("cpy/AUDREC.cpy", AUDREC))
    fl = flow_of(r, "src/SCX.cbl")
    ev = [u for u in fl["unsupported_statements"]
          if u["structure"] == "EVALUATE"]
    assert len(ev) == 1
    assert ev[0]["line"] == 15
    assert "not supported" in ev[0]["reason"]
    # nothing inside EVALUATE was interpreted as a guarded operation
    mv = [o for o in fl["operations"] if o["line"] == 17]
    assert mv == []


def test_unsupported_expression_not_established():
    prog = SCANNED.replace(
        "COMPUTE WS-T ROUNDED = LK-AMT * WS-N",
        "COMPUTE WS-T ROUNDED = FUNCTION LENGTH(LK-AMT)")
    r = run(("src/SCX.cbl", prog), ("cpy/AUDREC.cpy", AUDREC))
    ops = ops_of(r, "src/SCX.cbl")
    comp = ops[0]
    assert comp["status"] == "unsupported"
    assert comp["expression"]["supported"] is False
    assert comp["source_operands"] == []
    assert comp["receivers"] == []
    # and no capacity claims were invented
    sem = [d for d in r["findings"]
           if d["code"].startswith("SEM_")
           and (d["detail"] or {}).get("statement_line") == 9]
    assert sem == []


def test_malformed_arithmetic_not_established():
    prog = SCANNED.replace(
        "MULTIPLY LK-AMT BY LK-ID GIVING WS-T ROUNDED",
        "MULTIPLY LK-AMT BY")
    r = run(("src/SCX.cbl", prog), ("cpy/AUDREC.cpy", AUDREC))
    fl = flow_of(r, "src/SCX.cbl")
    unsup = [u for u in fl["unsupported_statements"]
             if u["structure"] == "MULTIPLY statement"]
    assert len(unsup) == 1 and unsup[0]["line"] == 12
    assert all(o["type"] != "MULTIPLY" for o in fl["operations"])


def test_copybook_operands_and_receivers_with_provenance():
    r = run(("src/SCX.cbl", SCANNED), ("cpy/AUDREC.cpy", AUDREC))
    ops = ops_of(r, "src/SCX.cbl")
    comp = ops[0]
    recv = comp["receivers"][0]
    assert recv["name"] == "WS-T"
    assert recv["decl"]["origin"] == "program"
    op_lk = [o for o in comp["source_operands"] if o["name"] == "LK-AMT"][0]
    assert op_lk["decl"]["origin"] == "copybook"
    assert op_lk["decl"]["source_file"] == "cpy/AUDREC.cpy"
    assert op_lk["decl"]["via_copybooks"] == ["cpy/AUDREC.cpy"]


def test_arithmetic_capacity_risk_scanned_path():
    r = run(("src/SCX.cbl", SCANNED), ("cpy/AUDREC.cpy", AUDREC))
    # MULTIPLY LK-AMT BY LK-ID GIVING WS-T: 5+5 int > 7 -> truncation
    f = [d for d in findings_for(r, "SEM_TRUNCATION_HIGH")
         if (d["detail"] or {}).get("statement_type") == "MULTIPLY"]
    assert len(f) == 1
    assert f[0]["detail"]["receiver"] == "WS-T"
    assert f[0]["detail"]["receiver_int_digits"] == 7
    assert f[0]["detail"]["bound_int_digits"] == 10
    assert f[0]["detail"]["statement_line"] == 12
    assert f[0]["line"] == 6      # WS-T's declaration line


def test_precision_and_sign_risks_scanned_path():
    prog = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. PSX.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY AUDREC.
       01  WS-P PIC 9(2)V9.
       01  WS-U PIC 9(3).
       PROCEDURE DIVISION.
           COMPUTE WS-P = LK-AMT + 1
           COMPUTE WS-U = LK-AMT - 1
           GOBACK.
"""
    r = run(("src/PSX.cbl", prog), ("cpy/AUDREC.cpy", AUDREC))
    prec = findings_for(r, "SEM_PRECISION_LOSS")
    assert [(d["detail"]["receiver"],
             d["detail"]["receiver_frac_digits"]) for d in prec] == [
        ("WS-P", 1), ("WS-U", 0)]
    assert all(d["detail"]["bound_frac_digits"] == 2 for d in prec)
    # both receivers are unsigned while the result can be negative
    sign = findings_for(r, "SEM_SIGN_DISCARD")
    assert [d["detail"]["receiver"] for d in sign] == ["WS-P", "WS-U"]


def test_divide_by_zero_literal_error_scanned():
    prog = SCANNED.replace(
        "DIVIDE LK-ID INTO LK-AMT GIVING WS-N REMAINDER LK-ID",
        "DIVIDE 0 INTO LK-AMT GIVING WS-N")
    r = run(("src/SCX.cbl", prog), ("cpy/AUDREC.cpy", AUDREC))
    f = findings_for(r, "SEM_DIVISOR_ZERO")
    assert len(f) == 1
    assert f[0]["severity"] == "error"
    assert f[0]["classification"] == "violation"


def test_unresolved_operand_leaves_operation_unresolved():
    prog = SCANNED.replace("ADD LK-ID 5 TO WS-N", "ADD GHOST 5 TO WS-N")
    r = run(("src/SCX.cbl", prog), ("cpy/AUDREC.cpy", AUDREC))
    add = ops_of(r, "src/SCX.cbl")[1]
    assert add["status"] == "unresolved"
    ghost = add["source_operands"][0]
    assert ghost["resolution"] == "unresolved"
    assert ghost["decl"] is None
    # any remaining bound comes only from KNOWN operands (5 and WS-N,
    # the same rule as the layer-5 engine) — never from the unknown
    trunc = [d for d in findings_for(r, "SEM_TRUNCATION_HIGH")
             if (d["detail"] or {}).get("statement_line") == 10]
    assert len(trunc) == 1
    assert trunc[0]["detail"]["bound_int_digits"] == 4   # max(1,3)+1
    assert trunc[0]["detail"]["receiver"] == "WS-N"


def test_unsupported_declaration_receiver_partial():
    prog = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. RU.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY AUDREC.
       01  WS-R PIC 9(3) OCCURS 2.
       PROCEDURE DIVISION.
           MOVE 5 TO WS-R
           GOBACK.
"""
    r = run(("src/RU.cbl", prog), ("cpy/AUDREC.cpy", AUDREC))
    ops = ops_of(r, "src/RU.cbl")
    mv = ops[0]
    assert mv["status"] == "partial"
    assert mv["receivers"][0]["decl"]["status"] == "unsupported"
    assert mv["receivers"][0]["decl"]["unsupported_reason"]


def test_cross_program_links_full_chain():
    caller = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. TXC.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY AUDREC.
       01  WS-T PIC S9(5)V99 COMP-3.
       PROCEDURE DIVISION.
           COMPUTE WS-T = LK-AMT * 2
           CALL "TXP" USING WS-T
           GOBACK.
"""
    callee = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. TXP.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY AUDREC.
       LINKAGE SECTION.
       01  LK-X PIC S9(5)V99 COMP-3.
       PROCEDURE DIVISION USING LK-X.
           COMPUTE LK-AMT = LK-X + 1
           GOBACK.
"""
    r = run(("src/TXC.cbl", caller), ("src/TXP.cbl", callee),
            ("cpy/AUDREC.cpy", AUDREC))
    links = r["cross_file"]["dataflow"]["cross_program_links"]
    lk = [l for l in links if l["caller"] == "src/TXC.cbl"]
    assert len(lk) == 1
    l = lk[0]
    assert l["status"] == "established"
    assert l["from_decl"] and l["to_decl"]
    assert len(l["caller_writes"]) == 1     # COMPUTE WS-T writes the arg
    assert l["caller_writes"][0]["line"] == 8
    assert len(l["callee_reads"]) == 1      # callee COMPUTE reads LK-X
    assert l["callee_reads"][0]["line"] == 9


def test_unresolved_call_boundary_has_no_link():
    caller = SCANNED.replace('CALL "TXP" USING', 'CALL')  # not present
    prog = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. DYN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-PGM PIC X(8).
       01  WS-T PIC 9(3).
       PROCEDURE DIVISION.
           MOVE 1 TO WS-T
           CALL WS-PGM
           GOBACK.
"""
    r = run(("src/DYN.cbl", prog))
    links = r["cross_file"]["dataflow"]["cross_program_links"]
    assert [l for l in links if l["caller"] == "src/DYN.cbl"] == []
    # the dynamic mapping itself remains recorded as unresolved
    m = [m for m in r["cross_file"]["mappings"]
         if m["from"] == "src/DYN.cbl"]
    assert m and m[0]["status"] == "unresolved"


def test_field_flow_queries():
    r = run(("src/SCX.cbl", SCANNED), ("cpy/AUDREC.cpy", AUDREC))
    fl = flow_of(r, "src/SCX.cbl")
    ws_t = [d for d in
            r["cross_file"]["logical"]["src/SCX.cbl"]["declarations"]
            if d["name"] == "WS-T"][0]
    ff = field_flow(fl, ws_t["decl_id"])
    # producers: COMPUTE (L9) and MULTIPLY (L12) write WS-T
    assert [p["line"] for p in ff["producers"]] == [9, 12]
    comp = ff["producers"][0]
    assert comp["label"] == "COMPUTE"
    assert {c["label"] for c in comp["contributors"]} == {
        "LK-AMT", "WS-N"}
    assert comp["rounded"] is True
    # consumers: SUBTRACT uses WS-T as minuend
    assert [c["line"] for c in ff["consumers"]] == [11]
    # subsequent uses of WS-COUNT
    ws_n = [d for d in
            r["cross_file"]["logical"]["src/SCX.cbl"]["declarations"]
            if d["name"] == "WS-N"][0]
    ff_n = field_flow(fl, ws_n["decl_id"])
    producer_lines = sorted(p["line"] for p in ff_n["producers"])
    assert producer_lines == [10, 11, 13]
    consumer_lines = sorted(c["line"] for c in ff_n["consumers"])
    # COMPUTE (9) reads it; ADD (10) reads the TO-receiver as an
    # implicit operand; MULTIPLY (12) does not touch WS-N
    assert consumer_lines == [9, 10]
    assert "not proof of runtime" in ff["note"]


def test_every_operation_carries_evidence():
    name, entries = ingest_dir()
    r = analyze_project(name, entries)
    for fid, fl in r["cross_file"]["dataflow"]["programs"].items():
        for o in fl["operations"]:
            assert o["evidence"], fid
            assert o["op_id"] and len(o["op_id"]) == 12
            assert o["source_file"] == fid
            assert o["line"] and o["col"]


def test_example_project_flagship_dataflow_chain():
    name, entries = ingest_dir()
    r = analyze_project(name, entries)
    fl = flow_of(r, "src/AUDTOTAL.cbl")
    ops = fl["operations"]
    assert [(o["type"], o["line"], o["status"]) for o in ops] == [
        ("MOVE", 11, "established"),
        ("COMPUTE", 12, "established"),
        ("MOVE", 14, "established")]
    comp = ops[1]
    assert comp["receivers"][0]["rounded"] is True
    contribs = {o["name"] for o in comp["source_operands"]}
    assert contribs == {"LK-AMT", "WS-COUNT"}
    # guarded write
    assert ops[2]["guards"] and ops[2]["guards"][0]["branch"] == "then"
    # condition references WS-TOTAL
    assert fl["conditions"][0]["left"]["name"] == "WS-TOTAL"
    # cross-program link carries the chain into GLUPDATE
    links = r["cross_file"]["dataflow"]["cross_program_links"]
    lk = [l for l in links if l["caller"] == "src/AUDTOTAL.cbl"][0]
    assert lk["status"] == "established"
    assert len(lk["caller_writes"]) == 1
    assert lk["caller_writes"][0]["op_id"] == comp["op_id"]
    # the COMPUTE truncation risk exists with receiver provenance
    f = [d for d in findings_for(r, "SEM_TRUNCATION_HIGH")
         if (d["detail"] or {}).get("statement_type") == "COMPUTE"]
    assert len(f) == 1
    assert f[0]["detail"]["receiver"] == "WS-TOTAL"
    assert f[0]["detail"]["statement_line"] == 12


def test_dataflow_separate_from_dependency_and_call_models():
    name, entries = ingest_dir()
    r = analyze_project(name, entries)
    df = r["cross_file"]["dataflow"]
    # three distinct models coexist without cross-contamination
    assert set(df["programs"]) == set(r["cross_file"]["logical"])
    assert r["edges"]                      # dependency graph intact
    assert r["cross_file"]["mappings"]     # CALL USING model intact
    assert df["coverage"]["edges_total"] >= 11
    assert "not proof of" in df["schema_note"]


def test_dataflow_determinism():
    name, entries = ingest_dir()
    a = json.dumps(analyze_project(name, entries), sort_keys=True)
    b = json.dumps(analyze_project(name, entries), sort_keys=True)
    assert a == b


def test_schema_v4_additive_and_contracts_intact():
    name, entries = ingest_dir()
    r = analyze_project(name, entries)
    assert r["schema_version"] == PROJECT_SCHEMA_VERSION == 4
    for key in ("project", "files", "skipped", "references", "edges",
                "cycles", "per_file", "findings", "coverage",
                "assumptions", "summary", "cross_file"):
        assert key in r
    df = r["cross_file"]["dataflow"]
    for key in ("programs", "cross_program_links", "assumptions",
                "coverage", "schema_note"):
        assert key in df
    # single-file contract untouched
    from necro.analyzer import analyze
    src = open("examples/sample-project/src/GLUPDATE.cbl").read()
    single = analyze(src, "GLUPDATE")
    assert single["schema_version"] == 2
    assert "dataflow" not in single and "logical" not in single


def test_operand_decl_provenance_contract_for_ui():
    """Regression (M6.1): the UI's operand chip reads decl.source_file and
    decl.origin. Lock the exact payload contract so a key rename cannot
    silently break copybook provenance rendering again."""
    r = run(("src/SCX.cbl", SCANNED), ("cpy/AUDREC.cpy", AUDREC))
    comp = ops_of(r, "src/SCX.cbl")[0]
    op_lk = [o for o in comp["source_operands"]
             if o.get("name") == "LK-AMT"][0]
    d = op_lk["decl"]
    assert d["source_file"] == "cpy/AUDREC.cpy"
    assert d["origin"] == "copybook"
    assert d["decl_id"] and d["line"] == 4
    assert d["via_copybooks"] == ["cpy/AUDREC.cpy"]
    assert "file" not in d and "origin_kind" not in d


def test_cross_program_link_decl_ids_match_logical_model():
    """Regression (M6.1): FieldFlow matches cross-program links against
    the logical model's decl_id; the ids must be identical on both
    sides of the envelope."""
    name, entries = ingest_dir()
    r = analyze_project(name, entries)
    links = r["cross_file"]["dataflow"]["cross_program_links"]
    for l in links:
        if l["status"] != "established":
            continue
        if l["from_decl"] is None or l["to_decl"] is None:
            continue
        caller_model = r["cross_file"]["logical"][l["caller"]]
        callee_model = r["cross_file"]["logical"][l["callee"]]
        assert any(d["decl_id"] == l["from_decl"]
                   for d in caller_model["declarations"])
        assert any(d["decl_id"] == l["to_decl"]
                   for d in callee_model["declarations"])
    aud = [l for l in links if l["caller"] == "src/AUDTOTAL.cbl"][0]
    wst = [d for d in r["cross_file"]["logical"]["src/AUDTOTAL.cbl"]
           ["declarations"] if d["name"] == "WS-TOTAL"][0]
    assert aud["from_decl"] == wst["decl_id"]


def test_dfa_assumptions_recorded():
    name, entries = ingest_dir()
    r = analyze_project(name, entries)
    ids = [a["id"] for a in r["assumptions"]]
    for aid in ("dataflow-not-execution", "single-sentence-scan",
                "guards-are-evidence", "risk-propagation-limits"):
        assert aid in ids


def test_parsed_and_scanned_equivalence():
    """The same COMPUTE capacity rule produces the same quantified risk
    whether the program was parsed or scanned (same code path seeds)."""
    parsed = PFIX_HEAD + "           COMPUTE C = A + B * D\n" \
        "               END-COMPUTE.\n           GOBACK.\n"
    scanned = parsed.replace(
        "       LINKAGE SECTION.\n       01  C PIC S9(4) COMP-3.\n",
        "").replace("PROCEDURE DIVISION USING C.", "PROCEDURE DIVISION.")
    scanned = scanned.replace(
        "       PROGRAM-ID. PFX.",
        "       PROGRAM-ID. PFX.\n       COPY CB.").replace(
        "           COMPUTE C = A + B * D",
        "           COMPUTE D = A + B * D")
    r_p = run(("src/PFX.cbl", parsed), ("cpy/CB.cpy", "       01 Z PIC 9.\n"))
    r_s = run(("src/PFX.cbl", scanned), ("cpy/CB.cpy", "       01 Z PIC 9.\n"))
    parsed_diags = r_p["per_file"]["src/PFX.cbl"]["result"]["diagnostics"]
    fp = [d for d in parsed_diags
          if d["code"] == "SEM_TRUNCATION_HIGH"
          and (d["detail"] or {}).get("statement") == "COMPUTE"]
    fs = [d for d in r_s["findings"]
          if d["code"] == "SEM_TRUNCATION_HIGH"
          and (d["detail"] or {}).get("statement_type") == "COMPUTE"]
    assert len(fp) == 1 and len(fs) == 1
    assert fp[0]["detail"]["bound_int_digits"] == \
        fs[0]["detail"]["bound_int_digits"]
    assert fp[0]["severity"] == fs[0]["severity"] == "warning"
