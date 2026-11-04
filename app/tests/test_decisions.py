"""Milestone 7: control-flow and decision-path analysis.

Covers: scanner decision structure (IF / ELSE / END-IF, inline
segments, nesting), parsed decisions from the frozen parser's IF AST,
per-branch operation membership, convergence and join evidence,
post-decision sequence, copybook provenance through decisions,
unterminated IF and EVALUATE boundaries, GO TO / PERFORM transfers,
deterministic decision identity, and M6 operation/data-flow stability.
No ELSE is ever invented and no business meaning is inferred:
summaries quote only source-backed operands and recorded operations.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from necro.project import analyze_project
from necro.decisions import (assign_branches, build_summaries,
                             resolve_convergence, scan_decisions)

# shared copybook (same content as the M6 suite's AUDREC)
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


def decisions_of(env, fid):
    return flow_of(env, fid)["decisions"]


def ops_of(env, fid):
    return flow_of(env, fid)["operations"]


def ingest_dir():
    from necro.project import ingest_directory
    return ingest_directory("examples/sample-project")


def example_project():
    name, entries = ingest_dir()
    return analyze_project(name, entries)


# -- scanner-path helpers ------------------------------------------------

def scanned_decision(env, fid, line):
    for d in decisions_of(env, fid):
        if d["line"] == line:
            return d
    raise AssertionError("no decision at line %d" % line)


# a scanned program with a COPY (outside the frozen subset)
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


def test_scanner_simple_if_then_membership():
    r = run(("cpy/AUDREC.cpy", AUDREC), ("src/SCIF.cbl", SCANNED_IF))
    ds = decisions_of(r, "src/SCIF.cbl")
    assert len(ds) == 1
    d = ds[0]
    assert d["origin"] == "scanned"
    assert d["has_else"] is False          # no ELSE in source: none invented
    assert d["summary"]["else"] is None
    assert len(d["then_ops"]) == 1
    inner = ops_of(r, "src/SCIF.cbl")
    then_op = [o for o in inner if o["op_id"] == d["then_ops"][0]][0]
    assert (then_op["type"], then_op["line"]) == ("MOVE", 10)
    assert then_op["guards"] == [{"cond_id": d["condition_id"],
                                  "branch": "then", "line": 9}]
    # the decision's condition is the M6 condition record (shared id)
    conds = flow_of(r, "src/SCIF.cbl")["conditions"]
    assert [c["cond_id"] for c in conds] == [d["condition_id"]]
    assert conds[0]["left"]["name"] == "LK-ID" and conds[0]["op"] == ">"


def test_scanner_if_else_branch_membership_and_summary():
    src = SCANNED_IF.replace(
        "           END-IF\n",
        "           ELSE\n               SUBTRACT 2 FROM LK-AMT\n"
        "           END-IF\n")
    r = run(("cpy/AUDREC.cpy", AUDREC), ("src/SCIF.cbl", src))
    d = scanned_decision(r, "src/SCIF.cbl", 9)
    assert d["has_else"] is True
    assert len(d["then_ops"]) == 1 and len(d["else_ops"]) == 1
    else_op = [o for o in ops_of(r, "src/SCIF.cbl")
               if o["op_id"] == d["else_ops"][0]][0]
    assert (else_op["type"], else_op["line"], else_op["status"]) == \
        ("SUBTRACT", 12, "established")
    assert else_op["guards"][0]["branch"] == "else"
    s = d["summary"]
    assert s["condition"] == "LK-ID > 5"
    assert s["then"] == ["MOVE at L10 writes LK-ID"]
    assert s["else"] == ["SUBTRACT at L12 writes LK-AMT"]


def test_nested_decisions_innermost_membership():
    r = example_project()
    ds = decisions_of(r, "src/DECISIONS.cbl")
    outer = scanned_decision(r, "src/DECISIONS.cbl", 13)
    inner = scanned_decision(r, "src/DECISIONS.cbl", 15)
    assert inner["parent_decision"] == outer["decision_id"]
    assert outer["nested_decisions"] == [inner["decision_id"]]
    assert outer["parent_decision"] is None
    # LK-ID write inside the nested IF belongs to the INNERMOST decision
    assert len(inner["then_ops"]) == 1
    inner_op = [o for o in ops_of(r, "src/DECISIONS.cbl")
                if o["op_id"] == inner["then_ops"][0]][0]
    assert inner_op["line"] == 16
    # and is not a direct member of the outer branch
    assert inner["then_ops"][0] not in outer["then_ops"]
    # statements after the nested END-IF but before the outer END-IF
    # belong to the outer THEN branch
    assert len(outer["then_ops"]) == 3
    late = [o for o in ops_of(r, "src/DECISIONS.cbl")
            if o["op_id"] == outer["then_ops"][1]][0]
    assert late["line"] == 18
    assert all(o["line"] != 16 for o in
               [x for x in ops_of(r, "src/DECISIONS.cbl")
                if x["op_id"] in outer["then_ops"]])


def test_convergence_and_join_edges():
    r = example_project()
    fl = flow_of(r, "src/DECISIONS.cbl")
    outer = scanned_decision(r, "src/DECISIONS.cbl", 13)
    # convergence: first supported operation after END-IF (L21)
    conv = outer["convergence"]
    assert conv["kind"] == "operation" and conv["line"] == 24
    assert "converge" in conv["evidence"] and "END-IF at L23" in \
        conv["evidence"]
    assert outer["summary"]["after"] == "MOVE at L24 writes LK-ID"
    jid = "j:" + outer["decision_id"]
    join_nodes = [n for n in fl["graph"]["nodes"] if n["id"] == jid]
    assert len(join_nodes) == 1 and join_nodes[0]["line"] == 23
    kinds = {}
    for e in fl["graph"]["edges"]:
        if e["to"] == jid or e["from"] == jid:
            kinds.setdefault(e["kind"], []).append(e)
    # then-ops and else-ops converge into the join; the condition
    # decides; the following operation continues after it
    assert sorted(e["role"] for e in kinds["joins"]) == \
        ["else", "then", "then", "then"]
    assert len(kinds["decides"]) == 1
    assert kinds["decides"][0]["from"] == "c:" + outer["condition_id"]
    assert kinds["continues"][0]["to"] == "o:" + conv["op_id"]


def test_post_decision_sequence_order():
    r = example_project()
    fl = flow_of(r, "src/DECISIONS.cbl")
    ops = {o["op_id"]: o for o in fl["operations"]}
    seq = fl["sequence"]
    assert seq == [o["op_id"] for o in
                   sorted(fl["operations"],
                          key=lambda x: (x["line"], x["col"]))]
    lines = [ops[oid]["line"] for oid in seq]
    assert lines == sorted(lines) == [11, 12, 14, 16, 18, 19, 22, 24]


def test_parser_backed_decisions_from_ast():
    # frozen-subset program: decisions must come from the parser's IF
    # AST (nesting and spans), not from text scanning
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
    ds = decisions_of(r, "src/PDEC.cbl")
    assert [d["origin"] for d in ds] == ["parsed", "parsed"]
    outer = [d for d in ds if d["parent_decision"] is None][0]
    inner = [d for d in ds if d["parent_decision"]][0]
    assert inner["parent_decision"] == outer["decision_id"]
    assert outer["nested_decisions"] == [inner["decision_id"]]
    assert outer["has_else"] is True and inner["has_else"] is False
    ops = {o["op_id"]: o for o in ops_of(r, "src/PDEC.cbl")}
    assert [ops[i]["line"] for i in outer["then_ops"]] == [12]
    assert [ops[i]["line"] for i in inner["then_ops"]] == [14]
    assert [ops[i]["line"] for i in outer["else_ops"]] == [17]
    assert outer["convergence"]["kind"] == "operation"
    assert outer["convergence"]["line"] == 19
    assert outer["summary"]["condition"] == "A > 1"
    assert outer["summary"]["then"] == ["MOVE at L12 writes B"]
    assert outer["summary"]["else"] == ["MOVE at L17 writes P"]
    # guard attribution on the parsed op stacks every enclosing
    # condition (M6 model): outer THEN guard first, then the inner one
    inner_op = ops[inner["then_ops"][0]]
    assert [(g["branch"], g["line"]) for g in inner_op["guards"]] == \
        [("then", 11), ("then", 13)]
    assert inner_op["guards"][-1]["cond_id"] == inner["condition_id"]
    assert inner_op["guards"][0]["cond_id"] == outer["condition_id"]


def test_inline_if_else_endif_single_line():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. INL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  X PIC 9(3).
       PROCEDURE DIVISION.
           IF X = 1 MOVE 1 TO X ELSE MOVE 2 TO X END-IF.
           MOVE 9 TO X
           GOBACK.
"""
    r = run(("src/INL.cbl", src))
    fl = flow_of(r, "src/INL.cbl")
    ds = decisions_of(r, "src/INL.cbl")
    assert len(ds) == 1
    d = ds[0]
    assert d["has_else"] is True
    # inline statements become partial MOVE ops attributed by column
    inline = [o for o in fl["operations"] if o["line"] == 7]
    assert [(o["col"], o["status"]) for o in inline] == \
        [(17, "partial"), (34, "partial")]
    assert len(d["then_ops"]) == 1 and len(d["else_ops"]) == 1
    then_op = [o for o in inline if o["op_id"] == d["then_ops"][0]][0]
    else_op = [o for o in inline if o["op_id"] == d["else_ops"][0]][0]
    assert then_op["guards"][0]["branch"] == "then"
    assert else_op["guards"][0]["branch"] == "else"
    assert d["summary"]["then"] == ["MOVE at L7 writes X"]
    assert d["summary"]["else"] == ["MOVE at L7 writes X"]
    assert d["summary"]["after"] == "MOVE at L8 writes X"


def test_copybook_provenance_through_decisions():
    r = example_project()
    fl = flow_of(r, "src/DECISIONS.cbl")
    d = scanned_decision(r, "src/DECISIONS.cbl", 13)
    cond = [c for c in fl["conditions"]
            if c["cond_id"] == d["condition_id"]][0]
    # the condition record is the M6 evidence row (identity preserved)
    assert cond["left"]["name"] == "WS-ADJ"
    assert cond["origin"] == "scanned"
    # branch operation receiver keeps its copybook provenance
    then_op = [o for o in fl["operations"]
               if o["op_id"] == d["then_ops"][0]][0]
    recv = then_op["receivers"][0]
    assert recv["name"] == "LK-ID"
    assert recv["decl"]["source_file"] == "copybooks/AUDREC.cpy"
    assert recv["decl"]["origin"] == "copybook"
    # M6 condition identity is unchanged: guards and decisions share it
    assert then_op["guards"][0]["cond_id"] == d["condition_id"]


def test_unterminated_if_reported_not_fabricated():
    src = SCANNED_IF.replace("           END-IF\n", "")
    r = run(("cpy/AUDREC.cpy", AUDREC), ("src/SCIF.cbl", src))
    ds = decisions_of(r, "src/SCIF.cbl")
    assert ds == []                       # no decision fabricated
    fl = flow_of(r, "src/SCIF.cbl")
    unsup = [u for u in fl["unsupported_statements"]
             if u["structure"] == "unterminated IF"]
    assert len(unsup) == 1 and unsup[0]["line"] == 9
    assert "END-IF" in unsup[0]["reason"]
    # the guarded op still carries its guard evidence (M6 behaviour)
    inner = [o for o in fl["operations"] if o["line"] == 10][0]
    assert inner["guards"] and inner["guards"][0]["branch"] == "then"


def test_evaluate_body_never_becomes_decisions():
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
               WHEN OTHER
                   MOVE 2 TO B
           END-EVALUATE
           IF A = 9
               MOVE 3 TO B
           END-IF
           GOBACK.
"""
    r = run(("src/EVALSUP.cbl", src))
    fl = flow_of(r, "src/EVALSUP.cbl")
    # WHEN bodies are not operations and not decisions
    assert [o["line"] for o in fl["operations"]] == [15]
    ds = decisions_of(r, "src/EVALSUP.cbl")
    assert len(ds) == 1 and ds[0]["line"] == 14
    ev = [u for u in fl["unsupported_statements"]
          if u["structure"] == "EVALUATE"]
    assert len(ev) == 1 and ev[0]["line"] == 8
    # suppressed WHEN bodies carry no guard attribution
    assert all(o["line"] != 10 and o["line"] != 12
               for o in fl["operations"])


def test_transfers_recorded_not_interpreted():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. XFER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  A PIC 9(3).
       PROCEDURE DIVISION.
           IF A = 1
               GO TO DONE
           END-IF
           MOVE 1 TO A
           DONE.
           GOBACK.
"""
    r = run(("src/XFER.cbl", src))
    fl = flow_of(r, "src/XFER.cbl")
    ds = decisions_of(r, "src/XFER.cbl")
    assert len(ds) == 1 and ds[0]["then_ops"] == []
    gt = [u for u in fl["unsupported_statements"]
          if u["structure"] == "GO transfer"]
    assert len(gt) == 1 and gt[0]["line"] == 8
    assert "not established" in gt[0]["reason"]
    # the transfer did not become an operation or a branch member
    assert all(o["type"] != "GO" for o in fl["operations"])


def test_decision_ids_deterministic_and_distinct():
    r1 = example_project()
    r2 = example_project()
    a = decisions_of(r1, "src/DECISIONS.cbl")
    b = decisions_of(r2, "src/DECISIONS.cbl")
    assert [d["decision_id"] for d in a] == \
        [d["decision_id"] for d in b]
    assert len({d["decision_id"] for d in a}) == len(a)
    # identity is positional: shifting the IF down one line changes it
    src = SCANNED_IF.replace("       PROCEDURE DIVISION.",
                             "       PROCEDURE DIVISION.\n")
    r3 = run(("cpy/AUDREC.cpy", AUDREC), ("src/SCIF.cbl", src))
    d3 = decisions_of(r3, "src/SCIF.cbl")[0]
    base = run(("cpy/AUDREC.cpy", AUDREC), ("src/SCIF.cbl", SCANNED_IF))
    d1 = decisions_of(base, "src/SCIF.cbl")[0]
    assert d3["decision_id"] != d1["decision_id"]
    assert len(d3["decision_id"]) == 12


def test_m6_operations_and_links_unchanged():
    r = example_project()
    fl = flow_of(r, "src/AUDTOTAL.cbl")
    # M6 flagship chain shape intact; decisions are purely additive
    assert [(o["type"], o["line"], o["status"], o["origin"])
            for o in fl["operations"]] == [
        ("MOVE", 11, "established", "scanned"),
        ("COMPUTE", 12, "established", "scanned"),
        ("MOVE", 14, "established", "scanned")]
    comp = fl["operations"][1]
    assert comp["op_id"]          # stable M6 identity (hashed, not new)
    move14 = fl["operations"][2]
    assert move14["guards"] == [{"cond_id": move14["guards"][0]["cond_id"],
                                 "branch": "then", "line": 13}]
    # the AUDTOTAL decision references the same condition record
    ds = decisions_of(r, "src/AUDTOTAL.cbl")
    assert len(ds) == 1
    assert ds[0]["condition_id"] == move14["guards"][0]["cond_id"]
    assert ds[0]["has_else"] is False
    assert ds[0]["then_ops"] == [move14["op_id"]]
    # cross-program link M6 anchor: caller_writes == the COMPUTE op
    link = [l for l in
            r["cross_file"]["dataflow"]["cross_program_links"]
            if l["caller"] == "src/AUDTOTAL.cbl"][0]
    assert link["caller_writes"][0]["op_id"] == comp["op_id"]
    # risk findings unchanged in count and anchors
    sems = [d for d in r["findings"]
            if d["code"] == "SEM_TRUNCATION_HIGH"
            and (d["detail"] or {}).get("receiver") == "WS-TOTAL"]
    assert len(sems) == 1
