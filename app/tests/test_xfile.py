"""Milestone 4: cross-file program understanding.

Covers the required matrix: resolved CALL + matching USING, fewer/more
args, unresolved and dynamic targets, positional correspondence, passing
conventions, LINKAGE decls, copybook-defined params, nested/ambiguous/
missing copybooks, unsupported declaration syntax, duplicate names,
both-side evidence, determinism, and v1 compatibility. Uncertainty is
asserted to stay visible — no weakened assertions.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from necro.project import (PROJECT_SCHEMA_VERSION, analyze_project,
                           impact, ingest_directory)


def run(*entries):
    return analyze_project("t", [
        {"path": p, "content": c} for p, c in entries])


def one_mapping(env, frm):
    ms = [m for m in env["cross_file"]["mappings"] if m["from"] == frm]
    assert len(ms) == 1
    return ms[0]


CALLEE = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLEE.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-P.
           05  LK-AMT       PIC S9(4)V9 COMP-3.
       PROCEDURE DIVISION USING LK-P.
           GOBACK.
"""

CALLER = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-A            PIC S9(4)V9 COMP-3.
       PROCEDURE DIVISION.
           CALL "CALLEE" USING WS-A
           GOBACK.
"""


def test_resolved_call_matching_using_established():
    r = run(("src/CALLER.cbl", CALLER), ("src/CALLEE.cbl", CALLEE))
    m = one_mapping(r, "src/CALLER.cbl")
    assert m["status"] == "established"
    assert m["to"] == "src/CALLEE.cbl"
    p = m["positions"][0]
    assert p["status"] == "established"
    assert p["caller"]["name"] == "WS-A"
    assert p["receiver"]["name"] == "LK-P"
    assert p["size_status"] == "equal"
    assert p["size_caller"] == p["size_receiver"] == 3
    assert p["caller_decl"]["file"] == "src/CALLER.cbl"
    assert p["caller_decl"]["line"] == 5
    assert p["receiver_decl"]["file"] == "src/CALLEE.cbl"
    assert p["receiver_decl"]["origin"] == "parsed"
    assert m["line"] == 7 and "CALL \"CALLEE\" USING WS-A" in m["text"]


def test_size_mismatch_is_warning_with_both_side_detail():
    caller = CALLER.replace("S9(4)V9", "S9(3)V9")   # 4 digits -> 3 bytes
    callee = CALLEE.replace("S9(4)V9", "S9(5)V9")   # 6 digits -> 4 bytes
    r = run(("src/CALLER.cbl", caller), ("src/CALLEE.cbl", callee))
    m = one_mapping(r, "src/CALLER.cbl")
    assert m["status"] == "incomplete"
    p = m["positions"][0]
    assert p["status"] == "established" and p["size_status"] == "mismatch"
    f = [d for d in r["findings"]
         if d["code"] == "XFD_PARAM_SIZE_MISMATCH"]
    assert len(f) == 1
    assert f[0]["severity"] == "warning"
    assert f[0]["classification"] == "risk"
    assert f[0]["detail"]["caller_bytes"] == 3
    assert f[0]["detail"]["receiver_bytes"] == 4
    assert f[0]["detail"]["caller_file"] == "src/CALLER.cbl"
    assert f[0]["detail"]["receiver_file"] == "src/CALLEE.cbl"
    assert f[0]["detail"]["passing"] == "by reference"
    assert f[0]["line"] == 7


def test_fewer_args_than_params():
    callee2 = CALLEE.replace(
        "PROCEDURE DIVISION USING LK-P.",
        "PROCEDURE DIVISION USING LK-P LK-Q.")
    callee2 = callee2.replace(
        "       PROCEDURE DIVISION USING LK-P LK-Q.",
        "       01  LK-Q PIC 9(3).\n"
        "       PROCEDURE DIVISION USING LK-P LK-Q.")
    r = run(("src/CALLER.cbl", CALLER), ("src/CALLEE.cbl", callee2))
    m = one_mapping(r, "src/CALLER.cbl")
    assert m["status"] == "incomplete"
    assert m["positions"][1]["status"] == "unmatched-parameter"
    assert m["positions"][1]["receiver"]["name"] == "LK-Q"
    f = [d for d in r["findings"]
         if d["code"] == "XFD_ARG_COUNT_MISMATCH"]
    assert len(f) == 1
    assert f[0]["detail"]["argument_count"] == 1
    assert f[0]["detail"]["parameter_count"] == 2


def test_more_args_than_params():
    caller2 = CALLER.replace(
        "USING WS-A", "USING WS-A WS-B").replace(
        "01  WS-A            PIC S9(4)V9 COMP-3.",
        "01  WS-A            PIC S9(4)V9 COMP-3.\n"
        "       01  WS-B            PIC 9(3).")
    r = run(("src/CALLER.cbl", caller2), ("src/CALLEE.cbl", CALLEE))
    m = one_mapping(r, "src/CALLER.cbl")
    assert m["status"] == "incomplete"
    assert m["positions"][1]["status"] == "unmatched-argument"
    assert m["positions"][1]["caller"]["name"] == "WS-B"
    f = [d for d in r["findings"]
         if d["code"] == "XFD_ARG_COUNT_MISMATCH"]
    assert f[0]["detail"]["argument_count"] == 2
    assert f[0]["detail"]["parameter_count"] == 1


def test_unresolved_call_target_mapping():
    r = run(("src/CALLER.cbl",
             CALLER.replace("CALL \"CALLEE\"", "CALL \"NOPE\"")))
    m = one_mapping(r, "src/CALLER.cbl")
    assert m["status"] == "unresolved"
    assert m["reason"] == "unresolved" and m["to"] is None
    assert m["positions"] == []


def test_dynamic_call_unresolved_mapping():
    caller_dyn = CALLER.replace(
        "CALL \"CALLEE\" USING WS-A", "CALL WS-PGM").replace(
        "01  WS-A            PIC S9(4)V9 COMP-3.",
        "01  WS-A            PIC S9(4)V9 COMP-3.\n"
        "       01  WS-PGM          PIC X(8).")
    r = run(("src/CALLER.cbl", caller_dyn), ("src/CALLEE.cbl", CALLEE))
    m = one_mapping(r, "src/CALLER.cbl")
    assert m["status"] == "unresolved"
    assert m["reason"] == "dynamic" and m["target"] == "WS-PGM"
    assert m["positions"] == []


def test_multi_arg_positional_correspondence():
    callee3 = CALLEE.replace(
        "       PROCEDURE DIVISION USING LK-P.",
        "       01  LK-Q.\n"
        "           05  LK-Q1       PIC 9(3).\n"
        "       01  LK-R.\n"
        "           05  LK-R1       PIC 9(5).\n"
        "       PROCEDURE DIVISION USING LK-P LK-Q LK-R.")
    caller3 = CALLER.replace(
        "       01  WS-A            PIC S9(4)V9 COMP-3.",
        "       01  WS-A            PIC S9(4)V9 COMP-3.\n"
        "       01  WS-B            PIC 9(3).\n"
        "       01  WS-C            PIC 9(5).").replace(
        "USING WS-A", "USING WS-A WS-B WS-C")
    r = run(("src/CALLER.cbl", caller3), ("src/CALLEE.cbl", callee3))
    m = one_mapping(r, "src/CALLER.cbl")
    assert m["status"] == "established"
    pairs = [(p["caller"]["name"], p["receiver"]["name"],
              p["size_status"]) for p in m["positions"]]
    assert pairs == [("WS-A", "LK-P", "equal"),
                     ("WS-B", "LK-Q", "equal"),
                     ("WS-C", "LK-R", "equal")]


def test_passing_conventions_recorded():
    caller_pass = CALLER.replace(
        "       01  WS-A            PIC S9(4)V9 COMP-3.",
        "       01  WS-A            PIC S9(4)V9 COMP-3.\n"
        "       01  WS-B            PIC 9(3).\n"
        "       01  WS-C            PIC 9(3).").replace(
        "USING WS-A", "USING BY CONTENT WS-A BY VALUE WS-B WS-C")
    r = run(("src/CALLER.cbl", caller_pass), ("src/CALLEE.cbl", CALLEE))
    m = one_mapping(r, "src/CALLER.cbl")
    args = [p["caller"] for p in m["positions"]]
    assert args[0]["passing"] == "by content"
    assert args[0]["passing_explicit"] is True
    assert args[1]["passing"] == "by value"
    assert args[1]["passing_explicit"] is True
    # the BY VALUE phrase stays in effect for WS-C (no new BY marker)
    assert args[2]["passing"] == "by value"
    assert args[2]["passing_explicit"] is True  # written in the source


def test_unsupported_declaration_clause_recorded_not_interpreted():
    caller_r = CALLER.replace(
        "       01  WS-A            PIC S9(4)V9 COMP-3.",
        "       01  WS-A            PIC S9(4)V9 COMP-3.\n"
        "       01  WS-A-RED REDEFINES WS-A PIC 9(4).").replace(
        "USING WS-A", "USING WS-A-RED")
    r = run(("src/CALLER.cbl", caller_r), ("src/CALLEE.cbl", CALLEE))
    m = one_mapping(r, "src/CALLER.cbl")
    p = m["positions"][0]
    assert p["caller_decl"]["unsupported_clause"] == "REDEFINES"
    assert p["caller_decl"]["byte_length"] is None
    assert p["size_status"] == "unknown"
    assert not [d for d in r["findings"]
                if d["code"] == "XFD_PARAM_SIZE_MISMATCH"]


def test_caller_linkage_declaration_scanned():
    caller_lk = CALLER.replace(
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A            PIC S9(4)V9 COMP-3.",
        "       LINKAGE SECTION.\n"
        "       01  LK-C.\n"
        "           05  LK-AMT      PIC S9(4)V9 COMP-3.").replace(
        "USING WS-A", "USING LK-C")
    r = run(("src/CALLER.cbl", caller_lk), ("src/CALLEE.cbl", CALLEE))
    p = one_mapping(r, "src/CALLER.cbl")["positions"][0]
    assert p["caller_decl"]["section"] == "LINKAGE"
    assert p["caller_decl"]["byte_length"] == 3
    assert p["size_status"] == "equal"


def test_receiver_interface_parsed_origin():
    r = run(("src/CALLER.cbl", CALLER), ("src/CALLEE.cbl", CALLEE))
    iface = r["cross_file"]["interfaces"]["src/CALLEE.cbl"]
    assert iface["origin"] == "parsed"
    assert [p["name"] for p in iface["params"]] == ["LK-P"]
    assert iface["params"][0]["declaration"]["origin"] == "parsed"


def test_copybook_defined_receiving_params():
    audrec = """      * audited record
       01  LK-REC.
           05  LK-ID        PIC 9(5).
           05  LK-AMT       PIC S9(5)V99 COMP-3.
"""
    prog_a = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. FEEDER.
       DATA DIVISION.
       LINKAGE SECTION.
       COPY AUDREC.
       PROCEDURE DIVISION USING LK-REC.
           CALL "AUDITER" USING LK-REC
           GOBACK.
"""
    prog_b = prog_a.replace("FEEDER", "AUDITER").replace(
        "CALL \"AUDITER\" USING LK-REC", "GOBACK")
    r = run(("src/FEEDER.cbl", prog_a), ("src/AUDITER.cbl", prog_b),
            ("cpy/AUDREC.cpy", audrec))
    m = one_mapping(r, "src/FEEDER.cbl")
    assert m["status"] == "established"
    p = m["positions"][0]
    assert p["caller_decl"]["file"] == "cpy/AUDREC.cpy"
    assert p["receiver_decl"]["file"] == "cpy/AUDREC.cpy"
    assert p["size_caller"] == p["size_receiver"] == 9
    assert p["size_status"] == "equal"
    iface = r["cross_file"]["interfaces"]["src/FEEDER.cbl"]
    assert iface["copybooks"] == [
        {"copybook": "cpy/AUDREC.cpy", "via": "direct",
         "chain": ["cpy/AUDREC.cpy"]}]
    cb = r["cross_file"]["copybook_declarations"]["cpy/AUDREC.cpy"]
    assert [(d["name"], d["byte_length"]) for d in cb] == [
        ("LK-REC", 9), ("LK-ID", 5), ("LK-AMT", 4)]


def test_nested_copybook_association_and_lookup():
    outer = """       01  LK-OUT.
           05  LK-O1        PIC 9(2).
       COPY INNER.
"""
    inner = """       01  LK-IN.
           05  LK-I1        PIC 9(3).
"""
    caller = CALLER.replace(
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A            PIC S9(4)V9 COMP-3.",
        "       WORKING-STORAGE SECTION.\n"
        "       COPY OUTER.").replace(
        "USING WS-A", "USING LK-IN")
    r = run(("src/CALLER.cbl", caller), ("src/CALLEE.cbl", CALLEE),
            ("cpy/OUTER.cpy", outer), ("cpy/INNER.cpy", inner))
    iface = r["cross_file"]["interfaces"]["src/CALLER.cbl"]
    assert {"copybook": "cpy/OUTER.cpy", "via": "direct",
            "chain": ["cpy/OUTER.cpy"]} in iface["copybooks"]
    assert {"copybook": "cpy/INNER.cpy", "via": "nested",
            "chain": ["cpy/OUTER.cpy", "cpy/INNER.cpy"]} \
        in iface["copybooks"]
    p = one_mapping(r, "src/CALLER.cbl")["positions"][0]
    assert p["caller_decl"]["file"] == "cpy/INNER.cpy"
    assert p["caller_decl"]["byte_length"] == 3


def test_copybook_cycle_associated_without_duplication_or_loop():
    a = "       01  LK-A.\n       COPY B.\n"
    b = "       01  LK-B.\n       COPY A.\n"
    prog = CALLER.replace("01  WS-A            PIC S9(4)V9 COMP-3.",
                          "COPY A.")
    r = run(("src/CALLER.cbl", prog), ("src/CALLEE.cbl", CALLEE),
            ("cpy/A.cpy", a), ("cpy/B.cpy", b))
    iface = r["cross_file"]["interfaces"]["src/CALLER.cbl"]
    assert {"copybook": "cpy/A.cpy", "via": "direct",
            "chain": ["cpy/A.cpy"]} in iface["copybooks"]
    assert {"copybook": "cpy/B.cpy", "via": "nested",
            "chain": ["cpy/A.cpy", "cpy/B.cpy"]} in iface["copybooks"]
    # the cycle is reported at the dependency level, not duplicated here
    assert r["cycles"] == [["cpy/A.cpy", "cpy/B.cpy"]]


def test_ambiguous_copybook_yields_no_association():
    lib = "       01  LK-U PIC 9(3).\n"
    prog = CALLER.replace("01  WS-A            PIC S9(4)V9 COMP-3.",
                          "COPY USRINFO OF LIBA.")
    r = run(("src/CALLER.cbl", prog), ("src/CALLEE.cbl", CALLEE),
            ("libA/USRINFO.cpy", lib), ("libB/USRINFO.cpy", lib))
    iface = r["cross_file"]["interfaces"]["src/CALLER.cbl"]
    assert iface["copybooks"] == []
    assert sorted(r["cross_file"]["copybook_declarations"]) == \
        ["libA/USRINFO.cpy", "libB/USRINFO.cpy"]


def test_missing_copybook_yields_no_association():
    prog = CALLER.replace("01  WS-A            PIC S9(4)V9 COMP-3.",
                          "COPY GHOST.")
    r = run(("src/CALLER.cbl", prog), ("src/CALLEE.cbl", CALLEE))
    assert r["cross_file"]["interfaces"]["src/CALLER.cbl"]["copybooks"] == []
    assert "cpy/GHOST.cpy" not in r["cross_file"]["copybook_declarations"]


def test_duplicate_names_scoped_to_own_copybook():
    cb1 = "       01  LK-W PIC 9(3).\n"
    cb2 = "       01  LK-W PIC 9(5).\n"
    c1 = CALLER.replace("01  WS-A            PIC S9(4)V9 COMP-3.",
                        "COPY CBONE.").replace("USING WS-A", "USING LK-W")
    c2 = CALLER.replace("CALLER", "CALLER2").replace(
        "01  WS-A            PIC S9(4)V9 COMP-3.", "COPY CBTWO.").replace(
        "USING WS-A", "USING LK-W")
    r = run(("src/CALLER.cbl", c1), ("src/CALLER2.cbl", c2),
            ("src/CALLEE.cbl", CALLEE),
            ("cpy/CBONE.cpy", cb1), ("cpy/CBTWO.cpy", cb2))
    p1 = [m for m in r["cross_file"]["mappings"]
          if m["from"] == "src/CALLER.cbl"][0]["positions"][0]
    p2 = [m for m in r["cross_file"]["mappings"]
          if m["from"] == "src/CALLER2.cbl"][0]["positions"][0]
    assert p1["caller_decl"]["file"] == "cpy/CBONE.cpy"
    assert p1["caller_decl"]["byte_length"] == 3
    assert p2["caller_decl"]["file"] == "cpy/CBTWO.cpy"
    assert p2["caller_decl"]["byte_length"] == 5


def test_param_decl_unresolved_is_info_and_mapping_incomplete():
    callee_np = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. NP.
       DATA DIVISION.
       PROCEDURE DIVISION USING LK-Z.
           CALL "X" USING LK-Z
           GOBACK.
"""
    caller = CALLER.replace("CALL \"CALLEE\"", "CALL \"NP\"")
    r = run(("src/CALLER.cbl", caller), ("src/NP.cbl", callee_np))
    m = one_mapping(r, "src/CALLER.cbl")
    assert m["status"] == "incomplete"
    assert m["positions"][0]["receiver_decl"] is None
    f = [d for d in r["findings"]
         if d["code"] == "XFD_PARAM_DECL_UNRESOLVED"]
    assert len(f) == 1 and f[0]["severity"] == "info"
    assert f[0]["classification"] == "note"
    assert f[0]["detail"]["receiver_file"] == "src/NP.cbl"


def test_example_project_cross_file_flagship_end_to_end():
    name, entries = ingest_directory("examples/sample-project")
    r = analyze_project(name, entries)
    xf = r["cross_file"]
    # flagship: evidence-backed relationship with both source locations
    m = [m for m in xf["mappings"]
         if m["from"] == "src/PAYROLL.cbl" and m["to"] == "src/GLUPDATE.cbl"]
    assert len(m) == 1 and m[0]["status"] == "incomplete"
    p = m[0]["positions"][0]
    assert p["caller"]["name"] == "LK-IO"
    assert p["caller_decl"]["file"] == "src/PAYROLL.cbl"
    assert p["caller_decl"]["line"] == 8
    assert p["receiver"]["name"] == "LK-IO"
    assert p["receiver_decl"]["file"] == "src/GLUPDATE.cbl"
    assert p["receiver_decl"]["origin"] == "parsed"
    assert p["size_status"] == "mismatch"
    assert (p["size_caller"], p["size_receiver"]) == (4, 10)
    # fully established relationship through a copybook
    est = [m for m in xf["mappings"] if m["status"] == "established"]
    assert [(m["from"], m["to"]) for m in est] == \
        [("src/FEEDER.cbl", "src/AUDITER.cbl")]
    assert est[0]["positions"][0]["size_status"] == "equal"
    assert est[0]["positions"][0]["caller_decl"]["file"] == \
        "copybooks/AUDREC.cpy"
    cov = xf["coverage"]
    assert cov["call_edges"] == 7 and cov["mappings_total"] == 7
    assert cov["mappings_established"] == 1
    assert cov["mappings_incomplete"] == 4
    assert cov["mappings_unresolved"] == 2
    assert cov["interfaces_documented"] == 12  # M8.1.1 adds EVALFIX
    assert cov["copybooks_indexed"] == 6
    # M5: logical model coverage
    assert cov["logical_programs"] == 12  # M8.1.1 adds EVALFIX
    assert cov["copybook_semantic_findings"] == 3
    assert cov["references_resolved"] == 16  # +EVALFIX MOVE refs


def test_impact_data_flow_distinct_from_dependencies():
    name, entries = ingest_directory("examples/sample-project")
    r = analyze_project(name, entries)
    imp = impact(r, "src/GLUPDATE.cbl")
    df = imp["data_flow"]
    assert [(d["with"], d["status"]) for d in df["receives_data_from"]] == [
        ("src/AUDTOTAL.cbl", "incomplete"), ("src/BILLING.cbl", "incomplete"),
        ("src/DECISIONS.cbl", "incomplete"),
        ("src/PAYROLL.cbl", "incomplete")]
    assert df["sends_data_to"] == []
    assert df["unresolved_data_relationships"] == []
    assert imp["direct_dependants"]  # dependency view is separate
    assert "not proof of runtime impact" in imp["note"]
    pay = impact(r, "src/PAYROLL.cbl")["data_flow"]
    assert [(d["with"], d["status"]) for d in pay["sends_data_to"]] == [
        ("src/GLUPDATE.cbl", "incomplete")]
    assert pay["unresolved_data_relationships"][0]["target"] == "WS-PGM"


def test_cross_file_determinism():
    name, entries = ingest_directory("examples/sample-project")
    a = json.dumps(analyze_project(name, entries), sort_keys=True)
    b = json.dumps(analyze_project(name, entries), sort_keys=True)
    assert a == b


def test_schema_v3_is_additive_over_v1():
    name, entries = ingest_directory("examples/sample-project")
    r = analyze_project(name, entries)
    assert r["schema_version"] == PROJECT_SCHEMA_VERSION == 7
    for key in ("project", "files", "skipped", "references", "edges",
                "cycles", "per_file", "findings", "coverage", "assumptions",
                "summary", "overview"):
        assert key in r
    for key in ("files_total", "files_indexed", "files_analyzed",
                "files_rejected", "files_copybook", "files_skipped",
                "dependencies_total", "dependencies_resolved",
                "dependencies_unresolved", "dependencies_ambiguous",
                "cycles", "needs_human_review", "findings"):
        assert key in r["coverage"]
    assert isinstance(r["findings"], list) and r["findings"]
    d = r["findings"][0]
    for key in ("severity", "code", "message", "line", "col", "layer",
                "hint", "context_line", "evidence", "classification",
                "detail", "finding_id"):
        assert key in d


def test_single_file_envelope_untouched():
    from necro.analyzer import analyze
    src = open("examples/sample-project/src/GLUPDATE.cbl").read()
    r = analyze(src, "GLUPDATE")
    assert r["schema_version"] == 2
    assert r["summary"]["ok"] is True
    assert "cross_file" not in r


def test_example_project_assumptions_grew_additively():
    name, entries = ingest_directory("examples/sample-project")
    r = analyze_project(name, entries)
    ids = [a["id"] for a in r["assumptions"]]
    # the five M3 project assumptions are preserved verbatim
    for kept in ("no-copy-expansion", "resolution-by-stem",
                 "calls-not-executed", "impact-not-runtime",
                 "subset-per-file"):
        assert kept in ids
    # the cross-file assumptions are appended, not replaced
    for new in ("positional-args", "by-reference-default",
                "scanned-declarations", "copybooks-not-integrated",
                "static-structure-only"):
        assert new in ids


def test_xfd_findings_carry_finding_id_and_hint():
    caller = CALLER.replace("S9(4)V9", "S9(3)V9")   # 3 bytes
    callee = CALLEE.replace("S9(4)V9", "S9(5)V9")   # 4 bytes
    r = run(("src/CALLER.cbl", caller), ("src/CALLEE.cbl", callee))
    f = [d for d in r["findings"] if d["code"] == "XFD_PARAM_SIZE_MISMATCH"]
    assert f and f[0]["finding_id"] and len(f[0]["finding_id"]) == 12
    assert f[0]["hint"]
    assert f[0]["evidence"] and "default, not written" in f[0]["evidence"]
