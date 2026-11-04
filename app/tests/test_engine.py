"""NecroSpec engine tests — fixtures, layer semantics, envelope shape.

Run:  /tmp/env0venv/bin/python -m pytest app/tests/ -v
(or:  python3 -m pytest app/tests/ -v  with pytest installed)
"""
import copy
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from necro.analyzer import analyze  # noqa: E402
from necro.fixtures import NEGATIVE_SAMPLES, POSITIVE_SAMPLES, SAMPLES  # noqa: E402


def codes(result):
    return [d["code"] for d in result["diagnostics"]]


# ---------------------------------------------------------------------------
# fixture corpus behavior
# ---------------------------------------------------------------------------

def test_every_positive_fixture_parses_clean():
    # Milestone 2: positives may carry semantic WARNINGS (truncation,
    # precision, sign-discard are possibilities, not rejections); the
    # product guarantee is zero ERRORS, i.e. accepted by the subset.
    for s in POSITIVE_SAMPLES:
        r = analyze(s["source"], s["filename"])
        assert r["summary"]["ok"], f"{s['id']}: expected clean, got {codes(r)}"
        assert r["summary"]["failed_layer"] is None
        assert not [d for d in r["diagnostics"] if d["severity"] == "error"]


def test_every_negative_fixture_is_rejected():
    for s in NEGATIVE_SAMPLES:
        r = analyze(s["source"], s["filename"])
        assert not r["summary"]["ok"], f"{s['id']}: expected rejection"
        assert r["summary"]["failed_layer"] is not None
        assert len(r["diagnostics"]) >= 1


def test_negative_fixture_layers():
    expected_layer = {
        "NEG_COL73": "Preflight",
        "NEG_BADIND": "Preflight",
        "EXT-TAB": "Preflight",
        "T2CRASH": "Lexical",
        "T2STOP": "Grammar",
        "NEG_UNTERM_SE": "Grammar",
        "EXT-NOENDIF": "Grammar",
        "NEG_PIC19": "AST",
        "EXT-DUPSYM": "AST",
        "EXT-UNDECL": "AST",
        "EXT-GROUPTGT": "AST",
        "EXT-DIVZERO": "Semantic",
    }
    for s in NEGATIVE_SAMPLES:
        r = analyze(s["source"], s["filename"])
        assert (
            r["summary"]["failed_layer"] == expected_layer[s["id"]]
        ), f"{s['id']}: layer {r['summary']['failed_layer']} != {expected_layer[s['id']]}"


# ---------------------------------------------------------------------------
# preflight (L1)
# ---------------------------------------------------------------------------

def test_col73_rejected_at_exact_position():
    src = "       IDENTIFICATION DIVISION.\n" + " " * 65 + "DATA DIVISION.   X\n"
    # line 2: 7 spaces + 'DATA DIVISION.' (14) + 51 pad = 72, X at col 73
    r = analyze(src, "X.cbl")
    assert not r["summary"]["ok"]
    d = r["diagnostics"][0]
    assert d["code"] == "ERR_COL73_OVERFLOW"
    assert d["line"] == 2 and d["col"] == 73


def test_bad_indicator_rejected():
    src = "      -01  BADIND           PIC 9.\n"
    r = analyze(src, "BADIND.cbl")
    assert not r["summary"]["ok"]
    assert r["diagnostics"][0]["code"] == "ERR_INVALID_INDICATOR"
    assert r["diagnostics"][0]["line"] == 1 and r["diagnostics"][0]["col"] == 7


def test_tab_rejected():
    r = analyze("\t   PROGRAM-ID. X.", "TAB.cbl")
    assert not r["summary"]["ok"]
    assert r["diagnostics"][0]["code"] in ("ERR_INVALID_CHAR",)


def test_comment_line_with_star_indicator_is_accepted():
    src = (
        "      * a comment line\n"
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. CMTOK.\n"
        "       DATA DIVISION.\n"
        "       LINKAGE SECTION.\n"
        "       01  LK-X             PIC 9.\n"
        "       PROCEDURE DIVISION USING LK-X.\n"
        "           GOBACK.\n"
    )
    r = analyze(src, "CMTOK.cbl")
    assert r["summary"]["ok"], codes(r)


# ---------------------------------------------------------------------------
# lexical (L2)
# ---------------------------------------------------------------------------

def test_reserved_word_return_code_rejected_in_procedure():
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T2STOP.\n"
        "       DATA DIVISION.\n"
        "       LINKAGE SECTION.\n"
        "       01  LK-DUMMY         PIC 9.\n"
        "       PROCEDURE DIVISION USING LK-DUMMY.\n"
        "           MOVE 42 TO RETURN-CODE\n"
        "           STOP RUN.\n"
    )
    r = analyze(src, "T2STOP.cbl")
    assert not r["summary"]["ok"]
    msg = r["diagnostics"][0]["message"]
    assert "RETURN-CODE" in msg or "reserved" in msg


def test_token_stream_columns_and_types():
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TOKCOL.\n"
        "       DATA DIVISION.\n"
        "       LINKAGE SECTION.\n"
        "       01  LK-X             PIC 9.\n"
        "       PROCEDURE DIVISION USING LK-X.\n"
        "           GOBACK.\n"
    )
    r = analyze(src, "TOKCOL.cbl")
    toks = r["tokens"]
    assert toks[0] == {"type": "KEYWORD", "text": "IDENTIFICATION", "line": 1, "col": 8}
    ident = [t for t in toks if t["type"] == "IDENT"]
    assert ident, "expected at least one USER_IDENT token"
    assert ident[0]["text"] == "TOKCOL" and ident[0]["line"] == 2


# ---------------------------------------------------------------------------
# grammar (L3)
# ---------------------------------------------------------------------------

def test_missing_end_compute_rejected():
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. NEGUNTSE.\n"
        "       DATA DIVISION.\n"
        "       LINKAGE SECTION.\n"
        "       01  LK-IO.\n"
        "           05  LK-A         PIC S9(5)V99  COMP-3.\n"
        "           05  LK-B         PIC S9(5)V99  COMP-3.\n"
        "           05  LK-UNSG-SE   PIC 9(3)V99   COMP-3.\n"
        "           05  LK-ERR-FLAG  PIC 9.\n"
        "       PROCEDURE DIVISION USING LK-IO.\n"
        "           COMPUTE LK-UNSG-SE = LK-A - LK-B\n"
        "               ON SIZE ERROR\n"
        "                   MOVE 1 TO LK-ERR-FLAG\n"
        "           GOBACK.\n"
    )
    r = analyze(src, "NEGUNTSE.cbl")
    assert not r["summary"]["ok"]
    assert r["summary"]["failed_layer"] == "Grammar"


def test_missing_end_if_rejected():
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. NOENDIF.\n"
        "       DATA DIVISION.\n"
        "       LINKAGE SECTION.\n"
        "       01  LK-IO.\n"
        "           05  LK-A         PIC S9(5)V99  COMP-3.\n"
        "           05  LK-B         PIC S9(5)V99  COMP-3.\n"
        "       PROCEDURE DIVISION USING LK-IO.\n"
        "           IF LK-A < LK-B\n"
        "               MOVE LK-B TO LK-A\n"
        "           GOBACK.\n"
    )
    r = analyze(src, "NOENDIF.cbl")
    assert not r["summary"]["ok"]
    assert "END-IF" in r["diagnostics"][0]["message"]


def test_linkage_section_mandatory():
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. NOLINK.\n"
        "       PROCEDURE DIVISION.\n"
        "           GOBACK.\n"
    )
    r = analyze(src, "NOLINK.cbl")
    assert not r["summary"]["ok"]
    assert r["summary"]["failed_layer"] == "Grammar"


# ---------------------------------------------------------------------------
# AST semantics (L4)
# ---------------------------------------------------------------------------

def test_pic_expansion_all_forms():
    from necro.ast_build import expand_pic

    assert expand_pic("S9(5)V99") == {"signed": True, "int_digits": 5, "frac_digits": 2}
    assert expand_pic("SV999") == {"signed": True, "int_digits": 0, "frac_digits": 3}
    assert expand_pic("9(3)V99") == {"signed": False, "int_digits": 3, "frac_digits": 2}
    assert expand_pic("9") == {"signed": False, "int_digits": 1, "frac_digits": 0}
    assert expand_pic("S9(10)V9(9)") == {"signed": True, "int_digits": 10, "frac_digits": 9}
    # expansion is syntactic; the 18-digit LIMIT is a semantic rule (tested below)
    assert expand_pic("S9(19)") == {"signed": True, "int_digits": 19, "frac_digits": 0}
    assert expand_pic("9X") is None
    assert expand_pic("V") is None


def test_pic_digit_limit_18_ok_19_rejected():
    def src_with(pic):
        return (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. LIMIT.\n"
            "       DATA DIVISION.\n"
            "       LINKAGE SECTION.\n"
            f"       01  LK-X             PIC {pic} COMP-3.\n"
            "       PROCEDURE DIVISION USING LK-X.\n"
            "           GOBACK.\n"
        )

    r18 = analyze(src_with("S9(18)"), "L18.cbl")
    assert r18["summary"]["ok"], codes(r18)
    r19 = analyze(src_with("S9(19)"), "L19.cbl")
    assert not r19["summary"]["ok"]
    assert r19["summary"]["failed_layer"] == "AST"
    assert r19["diagnostics"][0]["code"] == "ERR_PIC_DIGIT_LIMIT"


def test_duplicate_symbol_rejected_case_insensitive():
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DUP.\n"
        "       DATA DIVISION.\n"
        "       LINKAGE SECTION.\n"
        "       01  LK-IO.\n"
        "           05  LK-AMOUNT    PIC S9(5)V99  COMP-3.\n"
        "           05  LK-amount    PIC S9(5)V99  COMP-3.\n"
        "       PROCEDURE DIVISION USING LK-IO.\n"
        "           GOBACK.\n"
    )
    r = analyze(src, "DUP.cbl")
    assert not r["summary"]["ok"]
    assert "ERR_DUPLICATE_SYMBOL" in codes(r)


def test_undeclared_identifier_rejected():
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. UNDECL.\n"
        "       DATA DIVISION.\n"
        "       LINKAGE SECTION.\n"
        "       01  LK-IO.\n"
        "           05  LK-AMOUNT    PIC S9(5)V99  COMP-3.\n"
        "       PROCEDURE DIVISION USING LK-IO.\n"
        "           COMPUTE LK-AMOUNT = LK-GHOST + 1\n"
        "           GOBACK.\n"
    )
    r = analyze(src, "UNDECL.cbl")
    assert not r["summary"]["ok"]
    assert "ERR_UNDECLARED_IDENT" in codes(r)


def test_group_item_as_target_rejected():
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. GRPTGT.\n"
        "       DATA DIVISION.\n"
        "       LINKAGE SECTION.\n"
        "       01  LK-IO.\n"
        "           05  LK-AMOUNT    PIC S9(5)V99  COMP-3.\n"
        "       PROCEDURE DIVISION USING LK-IO.\n"
        "           COMPUTE LK-IO = 1\n"
        "           GOBACK.\n"
    )
    r = analyze(src, "GRPTGT.cbl")
    assert not r["summary"]["ok"]
    assert "ERR_NON_ELEMENTARY_TARGET" in codes(r)


def test_using_resolves_to_distinct_linkage_roots():
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T2MULTI.\n"
        "       DATA DIVISION.\n"
        "       LINKAGE SECTION.\n"
        "       01  LK-A             PIC S9(5)V99  COMP-3.\n"
        "       01  LK-B             PIC S9(5)V99  COMP-3.\n"
        "       01  LK-SUM           PIC S9(5)V99  COMP-3.\n"
        "       PROCEDURE DIVISION USING LK-A LK-B LK-SUM.\n"
        "           COMPUTE LK-SUM = LK-A + LK-B\n"
        "           GOBACK.\n"
    )
    r = analyze(src, "T2MULTI.cbl")
    assert r["summary"]["ok"], codes(r)
    assert r["summary"]["using"] == ["LK-A", "LK-B", "LK-SUM"]
    sym = r["ast"]["symbols"]
    assert [s["name"] for s in sym["linkage"]] == ["LK-A", "LK-B", "LK-SUM"]


def test_sign_separate_rules():
    # signed DISPLAY without SIGN SEPARATE -> error
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. SIGNMISS.\n"
        "       DATA DIVISION.\n"
        "       LINKAGE SECTION.\n"
        "       01  LK-X             PIC S9(4)V99.\n"
        "       PROCEDURE DIVISION USING LK-X.\n"
        "           GOBACK.\n"
    )
    r = analyze(src, "SIGNMISS.cbl")
    assert not r["summary"]["ok"], "signed DISPLAY without SIGN SEPARATE must be rejected"

    # COMP-3 with SIGN SEPARATE -> error
    src = src.replace("PIC S9(4)V99.", "PIC S9(4)V99 SIGN IS LEADING SEPARATE COMP-3.")
    r = analyze(src, "SIGNCOMP3.cbl")
    assert not r["summary"]["ok"], "COMP-3 with SIGN SEPARATE must be rejected"


# ---------------------------------------------------------------------------
# envelope / product contract
# ---------------------------------------------------------------------------

def test_envelope_shape():
    r = analyze(SAMPLES[0]["source"], SAMPLES[0]["filename"])
    # Milestone 2 adds symbols/references/semantic_counts (semantic products)
    assert set(r.keys()) == {"meta", "schema_version", "layers", "diagnostics",
                             "tokens", "ast", "symbols", "references",
                             "semantic_counts", "coverage", "assumptions",
                             "summary"}
    assert r["schema_version"] == 2
    assert set(r["layers"][0].keys()) <= {"layer", "status", "diagnostics"}
    for d in r["diagnostics"]:
        assert set(d.keys()) == {"severity", "code", "message", "line", "col",
                                 "layer", "hint", "context_line", "evidence",
                                 "classification", "detail", "finding_id"}
        assert d["classification"] in ("violation", "risk", "note",
                                       "unsupported")
        assert d["finding_id"]
    assert set(r["meta"].keys()) == {"name", "bytes", "lines", "columns_per_line"}
    assert set(r["summary"].keys()) == {
        "ok", "errors", "warnings", "infos", "token_count",
        "failed_layer", "program_name", "is_initial", "using",
    }
    for layer in r["layers"]:
        assert set(layer.keys()) <= {"layer", "status", "diagnostics"}
        assert layer["status"] in ("passed", "failed", "skipped")


def test_layer_stop_at_first_failure():
    # invalid frame must short-circuit: no tokens, no ast, no semantic products
    r = analyze("      -01  BADIND           PIC 9.\n", "BADIND.cbl")
    assert r["tokens"] == []
    assert r["ast"] is None
    assert r["symbols"] is None and r["references"] is None
    statuses = [l["status"] for l in r["layers"]]
    passed = statuses.count("passed")
    assert statuses[passed] == "failed"
    assert all(s == "skipped" for s in statuses[passed + 1:])


def test_semantic_layer_skipped_when_ast_fails():
    r = analyze(SAMPLES[16]["source"], SAMPLES[16]["filename"])  # NEG_PIC19 (AST)
    assert r["summary"]["failed_layer"] == "AST"
    assert [l["status"] for l in r["layers"]] == [
        "passed", "passed", "passed", "failed", "skipped"]
    assert r["symbols"] is None


def test_diagnostics_are_deterministic():
    r1 = analyze(SAMPLES[0]["source"], SAMPLES[0]["filename"])
    r2 = analyze(SAMPLES[0]["source"], SAMPLES[0]["filename"])
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


def test_diagnostics_carry_source_context_at_every_layer():
    # Grammar-layer failure (T2STOP, line 8) must embed the source line
    r = analyze(SAMPLES[12]["source"], SAMPLES[12]["filename"])
    assert r["summary"]["failed_layer"] == "Grammar"
    for d in r["diagnostics"]:
        assert d["context_line"], f"{d['code']} missing context"
        assert d["context_line"].strip(), "context must be the real source line"

    # Preflight-layer failure too
    r2 = analyze(SAMPLES[14]["source"], SAMPLES[14]["filename"])
    assert r2["summary"]["failed_layer"] == "Preflight"
    assert r2["diagnostics"][0]["context_line"]


def test_empty_linkage_section_rejected():
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. EMPTYLINK.\n"
        "       DATA DIVISION.\n"
        "       LINKAGE SECTION.\n"
        "       PROCEDURE DIVISION.\n"
        "           GOBACK.\n"
    )
    r = analyze(src, "EMPTYLINK.cbl")
    assert not r["summary"]["ok"]
    assert "ERR_GRAMMAR_INCOMPLETE" in codes(r)


def test_diagnostic_codes_are_stable():
    known = {
        "ERR_COL73_OVERFLOW", "ERR_INVALID_INDICATOR", "ERR_INVALID_CHAR",
        "ERR_PIC_DIGIT_LIMIT", "ERR_DUPLICATE_SYMBOL", "ERR_UNDECLARED_IDENT",
        "ERR_NON_ELEMENTARY_TARGET", "ERR_GRAMMAR_MISSING_TERMINATOR",
        "ERR_GRAMMAR_UNEXPECTED_TOKEN", "ERR_GRAMMAR_INCOMPLETE",
        "ERR_LEX_INVALID_WORD", "ERR_OVERPUNCH_UNSUPPORTED",
        "ERR_SIGN_CLAUSE_UNSUPPORTED",
    }
    seen = set()
    for s in SAMPLES:
        r = analyze(s["source"], s["filename"])
        seen.update(codes(r))
    # engineered rejections for the sign rules
    seen.update(codes(analyze(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. S1.\n"
        "       DATA DIVISION.\n"
        "       LINKAGE SECTION.\n"
        "       01  LK-X             PIC S9(4)V99.\n"
        "       PROCEDURE DIVISION USING LK-X.\n"
        "           GOBACK.\n", "S1.cbl")))
    seen.update(codes(analyze(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. S2.\n"
        "       DATA DIVISION.\n"
        "       LINKAGE SECTION.\n"
        "       01  LK-X        PIC S9(4)V99 COMP-3 SIGN IS LEADING SEPARATE.\n"
        "       PROCEDURE DIVISION USING LK-X.\n"
        "           GOBACK.\n", "S2.cbl")))
    seen.update(codes(analyze(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. S3.\n"
        "       DATA DIVISION.\n"
        "       LINKAGE SECTION.\n"
        "       PROCEDURE DIVISION.\n"
        "           GOBACK.\n", "S3.cbl")))
    missing = known - seen
    assert not missing, f"stable codes never exercised: {missing}"
