"""Milestone 5: copybook-aware semantic analysis.

Covers: effective-declaration model with provenance, nested copybooks,
hierarchy, qualified/ambiguous/duplicate resolution, missing/cyclic/
duplicate/REPLACING copybooks, unsupported structures (REDEFINES,
OCCURS, level-88, unsupported USAGE), MOVE-based capacity/precision/
sign/SPACES semantics using copybook declarations, CALL USING with
copybook-defined arguments and parameters, equivalence with
program-local declarations, determinism, and single-file/project
compatibility. Unsupported declarations must never silently become
established ones.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from necro.project import PROJECT_SCHEMA_VERSION, analyze_project, impact
from necro.logical import scan_moves


def run(*entries):
    return analyze_project("t", [
        {"path": p, "content": c} for p, c in entries])


def model_of(env, fid):
    return env["cross_file"]["logical"][fid]


def findings_for(env, code):
    return [d for d in env["findings"] if d["code"] == code]


AUDREC = """      * AUDREC: audited record layout (shared copybook)
       01  LK-REC.
           05  LK-ID        PIC 9(5).
           05  LK-AMT       PIC S9(5)V99 COMP-3.
"""

AUDUSER = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. AUDUSER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY AUDREC.
       PROCEDURE DIVISION.
           MOVE 123456 TO LK-AMT
           GOBACK.
"""


def test_direct_copybook_participates_with_provenance():
    r = run(("src/AUDUSER.cbl", AUDUSER), ("cpy/AUDREC.cpy", AUDREC))
    m = model_of(r, "src/AUDUSER.cbl")
    by_name = {d["name"]: d for d in m["declarations"]}
    assert set(by_name) == {"LK-REC", "LK-ID", "LK-AMT"}
    for d in by_name.values():
        assert d["origin"] == "copybook"
        assert d["source_file"] == "cpy/AUDREC.cpy"
        assert d["program"] == "src/AUDUSER.cbl"
        assert d["via_copybooks"] == ["cpy/AUDREC.cpy"]
    assert by_name["LK-REC"]["line"] == 2
    assert by_name["LK-ID"]["line"] == 3
    assert by_name["LK-AMT"]["line"] == 4
    assert all(d["decl_id"] and d["col"] for d in by_name.values())


def test_copybook_elementary_numeric_and_alphanumeric():
    cb = """       01  WS-NUM        PIC S9(5)V99 COMP-3.
       01  WS-NAME       PIC X(10).
"""
    prog = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY FIELDS.
       PROCEDURE DIVISION.
           GOBACK.
"""
    r = run(("src/P.cbl", prog), ("cpy/FIELDS.cpy", cb))
    d = {x["name"]: x for x in model_of(r, "src/P.cbl")["declarations"]}
    assert d["WS-NUM"]["status"] == "established"
    assert d["WS-NUM"]["byte_length"] == 4      # 7 digits -> ceil(8/2)
    assert d["WS-NUM"]["usage"] == "comp3"
    assert d["WS-NAME"]["status"] == "established"
    assert d["WS-NAME"]["byte_length"] == 10    # one byte per X


def test_copybook_group_hierarchy_and_sizes():
    r = run(("src/AUDUSER.cbl", AUDUSER), ("cpy/AUDREC.cpy", AUDREC))
    m = model_of(r, "src/AUDUSER.cbl")
    d = {x["name"]: x for x in m["declarations"]}
    grp = d["LK-REC"]
    assert grp["children"] == ["LK-ID", "LK-AMT"]
    assert grp["byte_length"] == 9              # 5 + 4
    assert grp["status"] == "established"
    assert d["LK-ID"]["parent"] == "LK-REC"
    assert d["LK-AMT"]["parent"] == "LK-REC"
    assert d["LK-ID"]["ancestor_groups"] == ["LK-REC"]
    assert d["LK-AMT"]["ancestor_groups"] == ["LK-REC"]
    assert grp["ancestor_groups"] == []


def test_nested_copybook_association_preserves_chain():
    inner = """       01  LK-IN.
           05  LK-I1        PIC 9(3).
"""
    outer = """       01  LK-OUT.
           05  LK-O1        PIC 9(2).
       COPY INNER.
"""
    prog = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY OUTER.
       PROCEDURE DIVISION.
           GOBACK.
"""
    r = run(("src/P.cbl", prog), ("cpy/OUTER.cpy", outer),
            ("cpy/INNER.cpy", inner))
    m = model_of(r, "src/P.cbl")
    d = {x["name"]: x for x in m["declarations"]}
    assert d["LK-OUT"]["via_copybooks"] == ["cpy/OUTER.cpy"]
    assert d["LK-O1"]["via_copybooks"] == ["cpy/OUTER.cpy"]
    assert d["LK-IN"]["via_copybooks"] == ["cpy/OUTER.cpy",
                                           "cpy/INNER.cpy"]
    assert d["LK-I1"]["via_copybooks"] == ["cpy/OUTER.cpy",
                                           "cpy/INNER.cpy"]
    assert {a["copybook"]: a["via"] for a in m["associations"]} == {
        "cpy/OUTER.cpy": "direct", "cpy/INNER.cpy": "nested"}


def test_duplicate_names_ambiguous_until_qualified():
    cb = """       01  EMP-RECORD.
           05  EMP-ID       PIC 9(5).
       01  DEP-RECORD.
           05  EMP-ID       PIC 9(5).
"""
    prog = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY FAM.
       PROCEDURE DIVISION.
           MOVE 1 TO EMP-ID
           MOVE 2 TO EMP-ID OF DEP-RECORD
           GOBACK.
"""
    r = run(("src/P.cbl", prog), ("cpy/FAM.cpy", cb))
    m = model_of(r, "src/P.cbl")
    ids = [d for d in m["declarations"] if d["name"] == "EMP-ID"]
    assert len(ids) == 2          # duplicates kept apart, never merged
    assert {d["parent"] for d in ids} == {"EMP-RECORD", "DEP-RECORD"}
    amb = findings_for(r, "XFS_REF_AMBIGUOUS")
    assert len(amb) == 1          # unqualified MOVE 1 TO EMP-ID
    assert amb[0]["detail"]["reference"] == "EMP-ID"
    assert len(amb[0]["detail"]["candidates"]) == 2
    # the qualified reference resolved uniquely: no second ambiguity
    refs = m["references"]
    q = [x for x in refs if x["qualified_by"] == "DEP-RECORD"]
    assert len(q) == 1 and q[0]["status"] == "resolved"
    assert q[0]["source_file"] == "cpy/FAM.cpy"


def test_qualified_reference_resolves_through_group():
    cb = """       01  EMP-RECORD.
           05  EMP-ID       PIC 9(5).
       01  DEP-RECORD.
           05  EMP-ID       PIC 9(5).
"""
    prog = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY FAM.
       PROCEDURE DIVISION.
           MOVE 7 TO EMP-ID OF EMP-RECORD
           GOBACK.
"""
    r = run(("src/P.cbl", prog), ("cpy/FAM.cpy", cb))
    m = model_of(r, "src/P.cbl")
    assert findings_for(r, "XFS_REF_AMBIGUOUS") == []
    row = [x for x in m["references"] if x["name"] == "EMP-ID"][0]
    assert row["status"] == "resolved"
    assert row["qualified_by"] == "EMP-RECORD"


def test_missing_copybook_leaves_references_unresolved():
    prog = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY GHOST.
       PROCEDURE DIVISION.
           MOVE 1 TO LK-AMT
           GOBACK.
"""
    r = run(("src/P.cbl", prog))
    m = model_of(r, "src/P.cbl")
    assert m["declarations"] == []
    assert m["associations"] == []
    row = m["references"][0]
    assert row["status"] == "unresolved"
    assert findings_for(r, "SEM_TRUNCATION_HIGH") == []
    assert any(d["code"] == "DEP_COPYBOOK_MISSING"
               for d in r["findings"])


def test_cyclic_copybooks_build_once_without_looping():
    a = """       01  LK-A.
           05  LK-A1        PIC 9(2).
       COPY B.
"""
    b = """       01  LK-B.
           05  LK-B1        PIC 9(3).
       COPY A.
"""
    prog = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY A.
       PROCEDURE DIVISION.
           GOBACK.
"""
    r = run(("src/P.cbl", prog), ("cpy/A.cpy", a), ("cpy/B.cpy", b))
    m = model_of(r, "src/P.cbl")
    names = [d["name"] for d in m["declarations"]]
    assert sorted(names) == ["LK-A", "LK-A1", "LK-B", "LK-B1"]
    assert len(names) == len(set(names))     # no duplicates from the cycle
    assert r["cycles"] == [["cpy/A.cpy", "cpy/B.cpy"]]
    assert {a2["copybook"]: a2["via"]
            for a2 in m["associations"]} == {
        "cpy/A.cpy": "direct", "cpy/B.cpy": "nested"}


def test_duplicate_copybook_inclusion_prevented():
    twice = AUDUSER.replace("       COPY AUDREC.",
                            "       COPY AUDREC.\n       COPY AUDREC.")
    r = run(("src/AUDUSER.cbl", twice), ("cpy/AUDREC.cpy", AUDREC))
    m = model_of(r, "src/AUDUSER.cbl")
    names = [d["name"] for d in m["declarations"]]
    assert sorted(names) == ["LK-AMT", "LK-ID", "LK-REC"]
    assert len(names) == len(set(names))
    assert any(u["structure"] == "duplicate copybook inclusion"
               for u in m["unsupported_structures"])


def test_copy_replacing_contributes_no_declarations():
    cp = """       01  X PIC 9(3).
"""
    prog = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY CP REPLACING ==X== BY ==Y==.
       PROCEDURE DIVISION.
           GOBACK.
"""
    r = run(("src/P.cbl", prog), ("cpy/CP.cpy", cp))
    m = model_of(r, "src/P.cbl")
    assert m["declarations"] == []       # rewritten names unestablishable
    assert any(u["structure"] == "COPY REPLACING" and
               u["file"] == "cpy/CP.cpy"
               for u in m["unsupported_structures"])
    # the dependency edge itself is still discovered and shown
    assert any(e["kind"] == "copy" and e["to"] == "cpy/CP.cpy"
               for e in r["edges"])


def test_isolation_declarations_not_globally_visible():
    cb_a = "       01  ONLY-IN-A PIC 9(3).\n"
    cb_b = "       01  ONLY-IN-B PIC 9(3).\n"
    pa = AUDUSER.replace("COPY AUDREC", "COPY CBA")
    pb = AUDUSER.replace("AUDUSER", "AUDUSERB").replace("COPY AUDREC",
                                                        "COPY CBB")
    r = run(("src/A.cbl", pa), ("src/B.cbl", pb),
            ("cpy/CBA.cpy", cb_a), ("cpy/CBB.cpy", cb_b))
    ma = model_of(r, "src/A.cbl")
    mb = model_of(r, "src/B.cbl")
    assert [d["name"] for d in ma["declarations"]] == ["ONLY-IN-A"]
    assert [d["name"] for d in mb["declarations"]] == ["ONLY-IN-B"]


def test_capacity_analysis_uses_copybook_declaration():
    r = run(("src/AUDUSER.cbl", AUDUSER), ("cpy/AUDREC.cpy", AUDREC))
    f = findings_for(r, "SEM_TRUNCATION_HIGH")
    assert len(f) == 1
    assert f[0]["severity"] == "warning"
    assert f[0]["classification"] == "risk"
    # finding cites the ORIGINAL copybook location, not the program
    assert f[0]["line"] == 4
    assert f[0]["detail"]["receiver_file"] == "cpy/AUDREC.cpy"
    assert f[0]["detail"]["receiver_line"] == 4
    assert f[0]["detail"]["receiver_origin"] == "copybook"
    assert f[0]["detail"]["statement_line"] == 7
    assert "cpy/AUDREC.cpy:L4" in f[0]["evidence"]
    assert "copybook origin" in f[0]["evidence"]
    assert f[0]["detail"]["sender_int_digits"] == 6
    assert f[0]["detail"]["receiver_int_digits"] == 5


def test_precision_analysis_uses_copybook_declaration():
    prog = AUDUSER.replace("MOVE 123456 TO LK-AMT",
                           "MOVE 1.2345 TO LK-AMT")
    r = run(("src/AUDUSER.cbl", prog), ("cpy/AUDREC.cpy", AUDREC))
    f = findings_for(r, "SEM_PRECISION_LOSS")
    assert len(f) == 1
    assert f[0]["detail"]["sender_frac_digits"] == 4
    assert f[0]["detail"]["receiver_frac_digits"] == 2
    assert f[0]["line"] == 4       # copybook location again
    assert findings_for(r, "SEM_TRUNCATION_HIGH") == []


def test_sign_analysis_uses_copybook_declaration():
    cb = "       01  WS-U          PIC 9(3).\n"
    prog = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY UREC.
       PROCEDURE DIVISION.
           MOVE -5 TO WS-U
           GOBACK.
"""
    r = run(("src/P.cbl", prog), ("cpy/UREC.cpy", cb))
    f = findings_for(r, "SEM_SIGN_DISCARD")
    assert len(f) == 1
    assert f[0]["detail"]["receiver_origin"] == "copybook"
    assert f[0]["line"] == 1


def test_move_spaces_to_copybook_numeric():
    r = run(("src/AUDUSER.cbl",
             AUDUSER.replace("MOVE 123456 TO LK-AMT",
                             "MOVE SPACES TO LK-ID")),
            ("cpy/AUDREC.cpy", AUDREC))
    f = findings_for(r, "SEM_MOVE_SPACES_TO_NUMERIC")
    assert len(f) == 1
    assert f[0]["line"] == 3       # LK-ID's copybook line
    assert f[0]["detail"]["receiver_file"] == "cpy/AUDREC.cpy"


def test_fitting_moves_produce_no_findings():
    r = run(("src/AUDUSER.cbl",
             AUDUSER.replace("MOVE 123456 TO LK-AMT",
                             "MOVE 12345 TO LK-ID")),
            ("cpy/AUDREC.cpy", AUDREC))
    assert findings_for(r, "SEM_TRUNCATION_HIGH") == []
    assert findings_for(r, "SEM_PRECISION_LOSS") == []
    assert findings_for(r, "SEM_SIGN_DISCARD") == []
    assert findings_for(r, "SEM_MOVE_SPACES_TO_NUMERIC") == []


def test_redefines_recorded_unsupported_never_established():
    cb = """       01  WS-A          PIC 9(3).
       01  WS-B REDEFINES WS-A PIC 9(5).
"""
    prog = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY RDEF.
       PROCEDURE DIVISION.
           MOVE 12345 TO WS-B
           GOBACK.
"""
    r = run(("src/P.cbl", prog), ("cpy/RDEF.cpy", cb))
    m = model_of(r, "src/P.cbl")
    d = {x["name"]: x for x in m["declarations"]}
    assert d["WS-B"]["status"] == "unsupported"
    assert d["WS-B"]["byte_length"] is None
    assert "REDEFINES" in d["WS-B"]["unsupported_reason"]
    assert d["WS-A"]["status"] == "established"
    # no capacity claim is computed from an unsupported declaration
    assert findings_for(r, "SEM_TRUNCATION_HIGH") == []
    row = [x for x in m["references"] if x["name"] == "WS-B"][0]
    assert row["status"] == "resolved"
    assert row["decl_status"] == "unsupported"


def test_occurs_recorded_unsupported_never_established():
    cb = """       01  WS-TAB.
           05  WS-ENT       PIC 9(3) OCCURS 5 TIMES.
"""
    prog = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY TAB.
       PROCEDURE DIVISION.
           GOBACK.
"""
    r = run(("src/P.cbl", prog), ("cpy/TAB.cpy", cb))
    m = model_of(r, "src/P.cbl")
    d = {x["name"]: x for x in m["declarations"]}
    assert d["WS-ENT"]["status"] == "unsupported"
    assert d["WS-ENT"]["byte_length"] is None
    assert "OCCURS" in d["WS-ENT"]["unsupported_reason"]
    # parent group is partial, never silently established
    assert d["WS-TAB"]["status"] == "partial"
    assert d["WS-TAB"]["byte_length"] is None


def test_level_88_condition_names_preserved_unsupported():
    cb = """       01  WS-FLAG       PIC X.
           88  WS-ON        VALUE 'Y'.
"""
    prog = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY FLAG.
       PROCEDURE DIVISION.
           GOBACK.
"""
    r = run(("src/P.cbl", prog), ("cpy/FLAG.cpy", cb))
    m = model_of(r, "src/P.cbl")
    d = {x["name"]: x for x in m["declarations"]}
    assert d["WS-ON"]["status"] == "unsupported"
    assert "88" in d["WS-ON"]["unsupported_reason"]
    assert d["WS-ON"]["value"] is not None     # evidence preserved
    assert d["WS-FLAG"]["status"] == "established"
    assert d["WS-FLAG"]["byte_length"] == 1


def test_unsupported_usage_recorded_without_sizes():
    cb = "       01  WS-C          PIC 9(4) COMP.\n"
    prog = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY COMPX.
       PROCEDURE DIVISION.
           MOVE 12345 TO WS-C
           GOBACK.
"""
    r = run(("src/P.cbl", prog), ("cpy/COMPX.cpy", cb))
    m = model_of(r, "src/P.cbl")
    d = {x["name"]: x for x in m["declarations"]}
    assert d["WS-C"]["usage"] == "unsupported:COMP"
    assert d["WS-C"]["status"] == "unsupported"
    assert d["WS-C"]["byte_length"] is None
    assert findings_for(r, "SEM_TRUNCATION_HIGH") == []   # no invented size


def test_unsupported_statements_recorded_not_interpreted():
    prog = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY AUDREC.
       PROCEDURE DIVISION.
           COMPUTE LK-AMT = LK-AMT + 1
           MOVE LK-ID TO LK-AMT LK-ID
           GOBACK.
"""
    r = run(("src/AUDUSER.cbl", prog), ("cpy/AUDREC.cpy", AUDREC))
    m = model_of(r, "src/AUDUSER.cbl")
    # since Milestone 6, COMPUTE is a structured data-flow operation, so
    # it is no longer a flat "unsupported statement" record
    u = m["unsupported_statements"]
    assert u == []
    comp = [o for o in
            r["cross_file"]["dataflow"]["programs"]["src/AUDUSER.cbl"]
            ["operations"] if o["type"] == "COMPUTE"]
    assert len(comp) == 1 and comp[0]["status"] == "established"
    # the well-formed MOVE was still analysed through the M5 path
    refs = [(x["name"], x["role"]) for x in m["references"]]
    assert ("LK-ID", "receiver") in refs


def test_call_using_with_copybook_defined_caller_argument():
    cb = "       01  LK-PAR PIC S9(4)V9 COMP-3.\n"
    caller = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY PAR.
       PROCEDURE DIVISION.
           CALL "CALLEE" USING LK-PAR
           GOBACK.
"""
    callee = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLEE.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-P PIC S9(4)V9 COMP-3.
       PROCEDURE DIVISION USING LK-P.
           GOBACK.
"""
    r = run(("src/CALLER.cbl", caller), ("src/CALLEE.cbl", callee),
            ("cpy/PAR.cpy", cb))
    m = [x for x in r["cross_file"]["mappings"]
         if x["from"] == "src/CALLER.cbl"][0]
    assert m["status"] == "established"
    p = m["positions"][0]
    assert p["caller_decl"]["file"] == "cpy/PAR.cpy"
    assert p["caller_decl"]["byte_length"] == 3
    assert p["receiver_decl"]["file"] == "src/CALLEE.cbl"
    assert p["size_status"] == "equal"


def test_call_using_with_copybook_defined_receiving_param():
    cb = "       01  LK-PAR PIC S9(4)V9 COMP-3.\n"
    caller = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY PAR.
       PROCEDURE DIVISION.
           CALL "CALLEE" USING LK-PAR
           GOBACK.
"""
    callee = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLEE.
       DATA DIVISION.
       LINKAGE SECTION.
       COPY PAR.
       PROCEDURE DIVISION USING LK-PAR.
           GOBACK.
"""
    r = run(("src/CALLER.cbl", caller), ("src/CALLEE.cbl", callee),
            ("cpy/PAR.cpy", cb))
    m = [x for x in r["cross_file"]["mappings"]
         if x["from"] == "src/CALLER.cbl"][0]
    p = m["positions"][0]
    assert m["status"] == "established"
    assert p["receiver_decl"]["file"] == "cpy/PAR.cpy"
    assert p["receiver_decl"]["origin"] == "scanned"
    assert p["size_status"] == "equal"


def test_copybook_params_consistent_with_program_local_ones():
    cb = "       01  LK-PAR PIC S9(4)V9 COMP-3.\n"
    caller_cp = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY PAR.
       PROCEDURE DIVISION.
           CALL "CALLEE" USING LK-PAR
           GOBACK.
"""
    caller_local = caller_cp.replace(
        "       COPY PAR.",
        "       01  LK-PAR PIC S9(4)V9 COMP-3.")
    callee = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLEE.
       DATA DIVISION.
       LINKAGE SECTION.
       COPY PAR.
       PROCEDURE DIVISION USING LK-PAR.
           GOBACK.
"""
    r_cp = run(("src/CALLER.cbl", caller_cp),
               ("src/CALLEE.cbl", callee), ("cpy/PAR.cpy", cb))
    r_loc = run(("src/CALLER.cbl", caller_local),
                ("src/CALLEE.cbl", callee), ("cpy/PAR.cpy", cb))
    m_cp = [x for x in r_cp["cross_file"]["mappings"]
            if x["from"] == "src/CALLER.cbl"][0]
    m_loc = [x for x in r_loc["cross_file"]["mappings"]
             if x["from"] == "src/CALLER.cbl"][0]
    # same status, same sizes, same codes — only the declaring file differs
    assert m_cp["status"] == m_loc["status"] == "established"
    assert m_cp["positions"][0]["size_caller"] == \
        m_loc["positions"][0]["size_caller"] == 3
    assert m_cp["positions"][0]["size_status"] == \
        m_loc["positions"][0]["size_status"] == "equal"
    codes_cp = sorted(d["code"] for d in r_cp["findings"])
    codes_loc = sorted(d["code"] for d in r_loc["findings"])
    assert codes_cp == codes_loc
    # and a copybook-defined SIZE MISMATCH behaves identically too
    cb_small = "       01  LK-PAR PIC S9(2)V9 COMP-3.\n"
    callee_local = callee.replace("       COPY PAR.",
                                  "       01  LK-PAR PIC S9(4)V9 COMP-3.")
    r_mm = run(("src/CALLER.cbl", caller_cp),
               ("src/CALLEE.cbl", callee_local), ("cpy/PAR.cpy", cb_small))
    f = [d for d in r_mm["findings"]
         if d["code"] == "XFD_PARAM_SIZE_MISMATCH"]
    assert len(f) == 1
    assert f[0]["detail"]["caller_file"] == "src/CALLER.cbl"
    assert f[0]["detail"]["caller_bytes"] == 2   # S9(2)V9 COMP-3
    assert f[0]["detail"]["receiver_bytes"] == 3  # S9(4)V9 COMP-3


def test_example_project_flagship_copybook_semantics():
    name, entries = ingest_dir()
    r = analyze_project(name, entries)
    m = model_of(r, "src/AUDPOST.cbl")
    d = {x["name"]: x for x in m["declarations"]}
    assert d["LK-AMT"]["origin"] == "copybook"
    assert d["LK-AMT"]["source_file"] == "copybooks/AUDREC.cpy"
    assert d["LK-RATE-EX"]["via_copybooks"] == ["copybooks/AUDREC.cpy"]
    f = findings_for(r, "SEM_TRUNCATION_HIGH")
    assert [(x["line"], x["detail"]["receiver"],
             x["detail"]["receiver_file"]) for x in f] == [
        (4, "LK-AMT", "copybooks/AUDREC.cpy"),
        (6, "LK-RATE-EX", "copybooks/AUDREC.cpy"),
        (8, "WS-TOTAL", "src/AUDTOTAL.cbl"),
        (9, "WS-COUNT", "src/AUDTOTAL.cbl")]
    prec = findings_for(r, "SEM_PRECISION_LOSS")
    assert prec[0]["detail"]["receiver"] == "LK-RATE-EX"
    assert prec[0]["line"] == 6     # LK-RATE-EX's copybook line
    assert r["coverage"]["cross_file"]["copybook_semantic_findings"] == 3
    assert r["coverage"]["cross_file"]["logical_copybook_origin_declarations"] > 0


def ingest_dir():
    from necro.project import ingest_directory
    return ingest_directory("examples/sample-project")


def test_logical_model_determinism():
    name, entries = ingest_dir()
    a = json.dumps(analyze_project(name, entries), sort_keys=True)
    b = json.dumps(analyze_project(name, entries), sort_keys=True)
    assert a == b


def test_single_file_envelope_unchanged_by_m5():
    from necro.analyzer import analyze
    src = open("examples/sample-project/src/GLUPDATE.cbl").read()
    r = analyze(src, "GLUPDATE")
    assert r["schema_version"] == 2
    assert "logical" not in r
    assert set(r.keys()) == {
        "meta", "schema_version", "layers", "diagnostics", "tokens",
        "ast", "symbols", "references", "semantic_counts", "coverage",
        "assumptions", "summary"}


def test_project_schema_stays_additive():
    name, entries = ingest_dir()
    r = analyze_project(name, entries)
    assert r["schema_version"] == PROJECT_SCHEMA_VERSION == 6
    for key in ("project", "files", "skipped", "references", "edges",
                "cycles", "per_file", "findings", "coverage",
                "assumptions", "summary", "cross_file"):
        assert key in r
    xf = r["cross_file"]
    for key in ("interfaces", "mappings", "copybook_declarations",
                "coverage", "assumptions", "logical"):
        assert key in xf
    # M4 CALL USING mappings still present and correct
    est = [m for m in xf["mappings"] if m["status"] == "established"]
    assert [(m["from"], m["to"]) for m in est] == [
        ("src/FEEDER.cbl", "src/AUDITER.cbl")]
    # impact data-flow still distinct and populated
    imp = impact(r, "src/GLUPDATE.cbl")
    assert len(imp["data_flow"]["receives_data_from"]) == 4


def test_scan_moves_moves_without_to_recorded():
    moves, unsup = scan_moves(
        "t", "       IDENTIFICATION DIVISION.\n"
             "       PROCEDURE DIVISION.\n"
             "           MOVE LK-ID\n")
    assert moves == [] and len(unsup) == 1
    assert unsup[0]["structure"] == "MOVE without TO"
