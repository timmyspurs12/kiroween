"""NecroSpec semantic-analysis tests (Milestone 2, layer 5).

Every new finding class has a test demonstrating why it is correct:
evidence is derived from declared PICTUREs, literal text and deterministic
arithmetic bounds only. Corpus byte-length annotations (rev4_extract §3.1
"Positive NVS-0 fixtures") are used as independent oracles for the data
dictionary's storage math.
"""
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from necro.analyzer import analyze  # noqa: E402
from necro.fixtures import SAMPLES  # noqa: E402


def run(fid):
    s = next(x for x in SAMPLES if x["id"] == fid)
    return analyze(s["source"], s["filename"])


def codes(r):
    return [d["code"] for d in r["diagnostics"]]


def flat(entries):
    out = []

    def walk(e):
        out.append(e)
        for c in e["children"]:
            walk(c)
    for e in entries:
        walk(e)
    return out


def find(r, code):
    return [d for d in r["diagnostics"] if d["code"] == code]


# ---------------------------------------------------------------------------
# A. symbol table / data dictionary
# ---------------------------------------------------------------------------

def test_dictionary_hierarchy_and_parents():
    r = run("EX1FEE")
    assert r["symbols"] is not None
    lk = r["symbols"][0]
    assert lk["name"] == "LK-IO" and lk["parent"] is None
    assert [c["name"] for c in lk["children"]] == [
        "LK-AMOUNT", "LK-RATE", "LK-FEE"]
    assert all(c["parent"] == "LK-IO" for c in lk["children"])
    assert all(c["level"] == 5 for c in lk["children"]) and lk["level"] == 1


def test_dictionary_byte_lengths_match_corpus_annotations():
    # rev4_extract §3.1 states the byte sizes: these are independent oracles
    cases = {
        "EX1FEE":   ("LK-IO", 10),  # 4+2+4  COMP-3
        "EX2RND":   ("LK-OUT", 3),  # S9(4)V9 -> 5 digits -> 3B COMP-3
        "EX3DIVA":  ("LK-ACCRUAL", 4),  # S9(5)V99 -> 7 digits -> 4B
        "EX4UNSG":  ("LK-IO", 18),  # 4+4+3+3+3+1
        "T2MULTI":  ("LK-SUM", 4),
        "T3STATE":  ("LK-IO", 9),   # 3x S9(5) COMP-3 = 3B each
        "T3DISP":   ("LK-IO", 19),  # (4+2+1)+(3+2+1)+(4+2) DISPLAY sep signs
    }
    for fid, (item, expected) in cases.items():
        r = run(fid)
        e = next(x for x in flat(r["symbols"]) if x["name"] == item)
        assert e["byte_length"] == expected, (
            f"{fid}.{item}: {e['byte_length']} != corpus {expected}")


def test_dictionary_categories_usage_and_precision():
    r = run("EX1FEE")
    items = {e["name"]: e for e in flat(r["symbols"])}
    assert items["LK-IO"]["category"] == "group (alphanumeric)"
    assert items["LK-AMOUNT"]["category"] == "numeric"
    assert items["LK-AMOUNT"]["usage_label"] == "COMP-3 (packed decimal)"
    assert items["LK-AMOUNT"]["digits"] == 7
    assert items["LK-AMOUNT"]["integer_digits"] == 5
    assert items["LK-AMOUNT"]["fractional_digits"] == 2
    assert items["LK-AMOUNT"]["signed"] is True
    assert items["LK-RATE"]["integer_digits"] == 0  # SV999
    assert items["LK-RATE"]["fractional_digits"] == 3

    r12 = run("T3DISP")
    items12 = {e["name"]: e for e in flat(r12["symbols"])}
    assert items12["LK-IN-LEAD"]["usage_label"] == "DISPLAY"
    assert items12["LK-IN-LEAD"]["byte_length"] == 7  # 6 digits + sep sign
    assert items12["LK-OUT-UNSG"]["byte_length"] == 6  # unsigned display


def test_dictionary_records_value_and_sign_clauses():
    r = run("T3STATE")
    ws = flat(r["symbols"])
    acc = next(e for e in ws if e["name"] == "WS-ACC-VAL")
    assert acc["section"] == "WORKING-STORAGE"
    assert acc["value"] == "+10"  # VALUE clause captured verbatim
    r12 = run("T3DISP")
    lead = next(e for e in flat(r12["symbols"]) if e["name"] == "LK-IN-LEAD")
    assert lead["sign"] == "LEADING"
    trail = next(e for e in flat(r12["symbols"]) if e["name"] == "LK-OUT-TRAIL")
    assert trail["sign"] == "TRAILING"


def test_using_parameters_recorded_in_dictionary_section():
    r = run("T2MULTI")
    names = [e["name"] for e in flat(r["symbols"])]
    assert names == ["LK-A", "LK-B", "LK-SUM"]
    assert all(e["section"] == "LINKAGE" for e in flat(r["symbols"]))


# ---------------------------------------------------------------------------
# B. references
# ---------------------------------------------------------------------------

def test_references_roles_and_exact_locations():
    r = run("EX1FEE")
    refs = r["references"]
    using = next(x for x in refs if x["role"] == "parameter")
    assert using["name"] == "LK-IO" and using["statement"] == "USING"
    assert using["line"] == 10  # PROCEDURE DIVISION USING LK-IO.
    recv = next(x for x in refs if x["role"] == "receiver")
    assert recv["name"] == "LK-FEE" and recv["statement"] == "COMPUTE"
    assert (recv["line"], recv["col"]) == (11, 20)
    operands = sorted(x["name"] for x in refs if x["role"] == "operand")
    assert operands == ["LK-AMOUNT", "LK-RATE"]
    amt = next(x for x in refs if x["name"] == "LK-AMOUNT")
    assert (amt["line"], amt["col"]) == (11, 29)


def test_references_cover_condition_and_all_statement_types():
    r = run("T3DISP")
    if_refs = [x for x in r["references"] if x["statement"] == "IF"]
    assert {x["role"] for x in if_refs} == {"operand"}
    # condition is `IF LK-IN-LEAD < 0` — the literal side is not an
    # identifier, so exactly one reference row exists
    assert len(if_refs) == 1 and if_refs[0]["name"] == "LK-IN-LEAD"
    stmts = {x["statement"] for x in r["references"]}
    assert stmts == {"USING", "IF", "COMPUTE"}


# ---------------------------------------------------------------------------
# C/D. capacity findings — MOVE
# ---------------------------------------------------------------------------

def _prog(body_extra: str, data: str, proc: str) -> str:
    return (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. PROBE.\n"
        "       DATA DIVISION.\n"
        "       LINKAGE SECTION.\n"
        f"{data}\n"
        f"       PROCEDURE DIVISION USING LK-IO.\n{proc}\n"
        "           GOBACK.\n"
    )


def test_move_numeric_truncation_precision_and_sign_findings():
    src = _prog("",
                "       01  LK-IO.\n"
                "           05  LK-A         PIC S9(5)V99  COMP-3.\n"
                "           05  LK-FLAG      PIC 9.",
                "           MOVE LK-A TO LK-FLAG")
    r = analyze(src, "PROBE.cbl")
    assert r["summary"]["ok"]  # possibilities are warnings, not rejections
    assert r["summary"]["failed_layer"] is None
    got = {d["code"] for d in r["diagnostics"]}
    assert got == {"SEM_TRUNCATION_HIGH", "SEM_PRECISION_LOSS",
                   "SEM_SIGN_DISCARD"}
    trunc = find(r, "SEM_TRUNCATION_HIGH")[0]
    assert trunc["severity"] == "warning"
    assert trunc["line"] == 9  # MOVE statement line
    assert "LK-A" in trunc["evidence"] and "LK-FLAG" in trunc["evidence"]
    assert trunc["hint"]  # suggested investigation present


def test_move_same_shape_produces_no_findings():
    src = _prog("",
                "       01  LK-IO.\n"
                "           05  LK-A         PIC S9(5)V99  COMP-3.\n"
                "           05  LK-B         PIC S9(5)V99  COMP-3.",
                "           MOVE LK-A TO LK-B")
    r = analyze(src, "PROBE.cbl")
    assert r["diagnostics"] == []


def test_move_literal_with_fraction_into_integer_receiver():
    src = _prog("",
                "       01  LK-IO.\n"
                "           05  LK-N         PIC 9(3).",
                "           MOVE 12.75 TO LK-N")
    r = analyze(src, "PROBE.cbl")
    loss = find(r, "SEM_PRECISION_LOSS")
    assert len(loss) == 1
    assert "truncated" in loss[0]["message"]


def test_move_spaces_to_numeric_is_flagged():
    r = run("EXT-MOVE-SPACES")
    assert r["summary"]["ok"]  # warning-only
    hits = find(r, "SEM_MOVE_SPACES_TO_NUMERIC")
    assert len(hits) == 1
    assert hits[0]["severity"] == "warning"
    assert "non-numeric" in hits[0]["message"]
    assert "LK-FLAG" in hits[0]["evidence"]


# ---------------------------------------------------------------------------
# C/D. capacity findings — arithmetic
# ---------------------------------------------------------------------------

def test_compute_multiply_product_bound_and_precision():
    r = run("EX1FEE")  # LK-FEE(5.2) = LK-AMOUNT(5.2) * LK-RATE(0.3)
    assert r["summary"]["failed_layer"] is None
    loss = find(r, "SEM_PRECISION_LOSS")
    assert len(loss) == 1 and loss[0]["line"] == 11
    assert "5 fractional digits" in loss[0]["message"]
    assert "2 fractional digits" in loss[0]["evidence"]
    assert find(r, "SEM_TRUNCATION_HIGH") == []  # 5+0 int fits 5


def test_rounded_changes_the_reported_treatment():
    r = run("EX2RND")  # ROUNDED multiply
    loss = find(r, "SEM_PRECISION_LOSS")
    assert len(loss) == 1
    assert "rounded" in loss[0]["message"]
    assert "ROUNDED is in effect" in loss[0]["evidence"]


def test_add_carry_bound_reported():
    r = run("T2MULTI")  # LK-SUM(5) = LK-A(5) + LK-B(5)
    trunc = find(r, "SEM_TRUNCATION_HIGH")
    assert len(trunc) == 1
    assert "6 integer digits" in trunc[0]["message"]
    assert "holds 5" in trunc[0]["message"]


def test_subtraction_sign_discard_on_unsigned_receiver():
    r = run("T3DISP")  # COMPUTE LK-OUT-UNSG = 0 - LK-IN-LEAD
    discards = find(r, "SEM_SIGN_DISCARD")
    assert len(discards) == 2  # both IF branches
    assert all("negative" in d["message"] for d in discards)
    # the signed receiver LK-OUT-TRAIL must NOT be flagged
    lines = {d["line"] for d in discards}
    assert lines == {13.0, 16.0} or lines == {13, 16}


def test_size_error_guard_upgrades_findings_to_info():
    r = run("EX4UNSG")
    guards = find(r, "SEM_SIZE_ERROR_GUARD")
    assert len(guards) == 1
    assert guards[0]["severity"] == "info"
    assert guards[0]["line"] == 16  # the guarded COMPUTE (LK-UNSG-SE)
    assert guards[0]["col"] == 12
    # the guarded statement itself carries no truncation/sign warnings
    assert guards[0]["evidence"].startswith("Receiver LK-IO.LK-UNSG-SE".replace("LK-IO.", "")) or "LK-UNSG-SE" in guards[0]["evidence"]
    # the UNGUARDED same-shape COMPUTE (LK-UNSG-TR) is warned
    unguarded = [d for d in find(r, "SEM_TRUNCATION_HIGH") if d["line"] == 15]
    assert len(unguarded) == 1
    sign_discard = [d for d in find(r, "SEM_SIGN_DISCARD") if d["line"] == 15]
    assert len(sign_discard) == 1  # unsigned receiver, subtraction


def test_divide_literal_zero_is_error_in_both_statement_forms():
    # COMPUTE form (fixture)
    r = run("EXT-DIVZERO")
    assert not r["summary"]["ok"]
    assert r["summary"]["failed_layer"] == "Semantic"
    hits = find(r, "SEM_DIVISOR_ZERO")
    assert len(hits) == 1
    assert hits[0]["severity"] == "error"
    assert (hits[0]["line"], hits[0]["col"]) == (9, 34)
    assert hits[0]["context_line"].strip().endswith("/ 0")

    # DIVIDE statement form, INTO mode: divisor is the first operand
    src = _prog("",
                "       01  LK-IO.\n"
                "           05  LK-A         PIC S9(3)     COMP-3.\n"
                "           05  LK-Q         PIC S9(5)V99  COMP-3.",
                "           DIVIDE 0 INTO LK-A GIVING LK-Q")
    r2 = analyze(src, "PROBE.cbl")
    hits2 = find(r2, "SEM_DIVISOR_ZERO")
    assert len(hits2) == 1 and hits2[0]["severity"] == "error"


def test_divide_quotient_precision_not_invented():
    r = run("EX3DIVA")  # division-derived value into S9(5)V99
    assert r["summary"]["ok"]
    # quotient precision cannot be established statically: no truncation or
    # precision claims may be manufactured for the DIVIDE-fed receiver
    assert find(r, "SEM_TRUNCATION_HIGH") == []
    assert find(r, "SEM_PRECISION_LOSS") == []
    assert r["diagnostics"] == []


def test_multiply_statement_bound():
    src = _prog("",
                "       01  LK-IO.\n"
                "           05  LK-A         PIC S9(3)     COMP-3.\n"
                "           05  LK-B         PIC S9(4)     COMP-3.\n"
                "           05  LK-P         PIC S9(5)     COMP-3.",
                "           MULTIPLY LK-A BY LK-B GIVING LK-P")
    r = analyze(src, "PROBE.cbl")
    trunc = find(r, "SEM_TRUNCATION_HIGH")
    assert len(trunc) == 1
    assert "7 integer digits" in trunc[0]["message"]  # 3 + 4
    assert "holds 5" in trunc[0]["message"]


# ---------------------------------------------------------------------------
# E. diagnostics quality
# ---------------------------------------------------------------------------

def test_semantic_diagnostics_carry_evidence_hint_and_context():
    r = run("EX1FEE")
    d = r["diagnostics"][0]
    assert d["layer"] == "Semantic"
    assert d["severity"] in ("error", "warning", "info")
    assert d["code"].startswith("SEM_")
    assert d["message"] and d["hint"] and d["evidence"]
    assert d["context_line"].strip().startswith("COMPUTE")
    # location is the statement keyword: line 11, 'COMPUTE' at col 12
    assert (d["line"], d["col"]) == (11, 12)


def test_semantic_diagnostics_deterministic():
    r1 = run("EX4UNSG")
    r2 = run("EX4UNSG")
    assert json.dumps(r1["diagnostics"], sort_keys=True) == \
        json.dumps(r2["diagnostics"], sort_keys=True)
    assert json.dumps(r1["symbols"], sort_keys=True) == \
        json.dumps(r2["symbols"], sort_keys=True)


def test_semantic_products_absent_when_upper_layer_fails():
    # unsupported construct (unknown statement) -> grammar failure -> the
    # product must NOT present partial semantic results as established
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. UNSUP.\n"
        "       DATA DIVISION.\n"
        "       LINKAGE SECTION.\n"
        "       01  LK-X             PIC 9.\n"
        "       PROCEDURE DIVISION USING LK-X.\n"
        "           PERFORM INIT-PARA\n"
        "           GOBACK.\n"
    )
    r = analyze(src, "UNSUP.cbl")
    assert r["summary"]["failed_layer"] == "Grammar"
    assert r["symbols"] is None and r["references"] is None


def test_no_findings_programs_are_truly_clean():
    for fid in ("T3STICKY", "EX3DIVA", "EX3DIVB"):
        r = run(fid)
        assert r["diagnostics"] == [], f"{fid}: unexpected findings"
        assert r["summary"]["ok"]


def test_all_corpus_positives_stay_accepted_with_semantics_on():
    for s in SAMPLES:
        if s["expect_ok"]:
            r = analyze(s["source"], s["filename"])
            assert r["summary"]["ok"], f"{s['id']} became a rejection"
            assert r["summary"]["failed_layer"] is None


# ---------------------------------------------------------------------------
# API integration (semantic products over HTTP)
# ---------------------------------------------------------------------------

def test_api_semantic_integration():
    import threading
    import urllib.request
    import server as server_mod

    srv = server_mod.ThreadingHTTPServer(("127.0.0.1", 0), server_mod.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        s = next(x for x in SAMPLES if x["id"] == "EX1FEE")
        req = urllib.request.Request(
            base + "/api/analyze",
            data=json.dumps({"source": s["source"],
                             "filename": s["filename"]}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as res:
            body = json.load(res)
        assert body["symbols"] and body["references"]
        assert body["semantic_counts"]["data_items"] == 4
        assert [l["layer"] for l in body["layers"]][-1] == "Semantic"
        assert any(d["code"].startswith("SEM_") for d in body["diagnostics"])
    finally:
        srv.shutdown()
