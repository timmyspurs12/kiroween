"""NecroSpec platform-model tests — traceability, classification, coverage,
assumptions, schema contract, and the CLI (Milestone 2 foundation pass).

These pin the structured-output contracts the platform direction requires:
findings must be machine-consumable (ids, classification, quantities) and
the analysis must state what it covered, what it assumed, and what needs
human investigation.
"""
import json
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from necro.analyzer import analyze  # noqa: E402
from necro.diagnostics import (CLASS_NOTE, CLASS_RISK, CLASS_UNSUPPORTED,
                               CLASS_VIOLATION)  # noqa: E402
from necro.fixtures import SAMPLES  # noqa: E402

CLI = [sys.executable, str(APP / "cli.py")]


def run(fid):
    s = next(x for x in SAMPLES if x["id"] == fid)
    return analyze(s["source"], s["filename"])


def by_code(r, code):
    return [d for d in r["diagnostics"] if d["code"] == code]


# ---------------------------------------------------------------------------
# classification: proven vs risk vs note vs unsupported
# ---------------------------------------------------------------------------

def test_classification_map_across_layers():
    # layers 1-3 reject constructs outside the supported frame/grammar
    r = run("NEG_COL73")  # Preflight
    assert r["diagnostics"][0]["classification"] == CLASS_UNSUPPORTED
    r = run("T2STOP")     # Grammar (reserved word outside subset)
    assert r["diagnostics"][0]["classification"] == CLASS_UNSUPPORTED
    # layer 4 violations are definite against the declared subset rules
    r = run("EXT-UNDECL")
    assert r["diagnostics"][0]["classification"] == CLASS_VIOLATION
    # semantic severities map: error->violation, warning->risk, info->note
    r = run("EXT-DIVZERO")
    assert by_code(r, "SEM_DIVISOR_ZERO")[0]["classification"] == CLASS_VIOLATION
    r = run("EX1FEE")
    assert by_code(r, "SEM_PRECISION_LOSS")[0]["classification"] == CLASS_RISK
    r = run("EX4UNSG")
    assert by_code(r, "SEM_SIZE_ERROR_GUARD")[0]["classification"] == CLASS_NOTE


def test_risks_are_not_presented_as_proven():
    # a warning-classified finding must never be counted as an error nor fail
    # the program: severity and classification stay distinct
    r = run("EX1FEE")
    assert r["summary"]["ok"] is True
    assert r["summary"]["errors"] == 0
    d = by_code(r, "SEM_PRECISION_LOSS")[0]
    assert d["severity"] == "warning" and d["classification"] == "risk"


# ---------------------------------------------------------------------------
# finding identity: deterministic, stable, unique
# ---------------------------------------------------------------------------

def test_finding_ids_deterministic_and_stable():
    r1 = run("EX4UNSG")
    r2 = run("EX4UNSG")
    ids1 = [d["finding_id"] for d in r1["diagnostics"]]
    ids2 = [d["finding_id"] for d in r2["diagnostics"]]
    assert ids1 == ids2
    assert all(len(i) == 12 for i in ids1)
    # distinct findings carry distinct ids
    assert len(set(ids1)) == len(ids1)


def test_finding_ids_differ_when_location_differs():
    r = run("EX4UNSG")
    trunc = by_code(r, "SEM_TRUNCATION_HIGH")
    assert len(trunc) == 2  # L15 and L20
    assert trunc[0]["finding_id"] != trunc[1]["finding_id"]


# ---------------------------------------------------------------------------
# structured detail: machine-readable quantities, not prose
# ---------------------------------------------------------------------------

def test_truncation_detail_carries_quantities():
    r = run("EX4UNSG")
    d = by_code(r, "SEM_TRUNCATION_HIGH")[0]  # LK-UNSG-TR (3.2), bound 5.2
    det = d["detail"]
    assert det["statement"] == "COMPUTE"
    assert det["receiver"] == "LK-UNSG-TR"
    assert det["receiver_int_digits"] == 3 and det["receiver_frac_digits"] == 2
    assert det["bound_int_digits"] == 5 and det["bound_frac_digits"] == 2
    assert det["rounded"] is False and det["guarded"] is False


def test_guarded_detail_marks_guard():
    r = run("EX4UNSG")
    d = by_code(r, "SEM_SIZE_ERROR_GUARD")[0]
    assert d["detail"]["guarded"] is True
    assert d["detail"]["receiver"] == "LK-UNSG-SE"


def test_divisor_zero_detail_records_mode():
    r = run("EXT-DIVZERO")
    det = by_code(r, "SEM_DIVISOR_ZERO")[0]["detail"]
    assert det["statement"] == "COMPUTE" and det["divisor_literal"] == "0"
    # DIVIDE statement form records its mode
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. PROBE.\n"
        "       DATA DIVISION.\n"
        "       LINKAGE SECTION.\n"
        "       01  LK-A             PIC S9(3)     COMP-3.\n"
        "       01  LK-Q             PIC S9(5)V99  COMP-3.\n"
        "       PROCEDURE DIVISION USING LK-A LK-Q.\n"
        "           DIVIDE 0 INTO LK-A GIVING LK-Q\n"
        "           GOBACK.\n"
    )
    r2 = analyze(src, "PROBE.cbl")
    det2 = by_code(r2, "SEM_DIVISOR_ZERO")[0]["detail"]
    assert det2["statement"] == "DIVIDE" and det2["mode"] == "INTO"


# ---------------------------------------------------------------------------
# coverage and assumptions: what was analyzed, what remains uncertain
# ---------------------------------------------------------------------------

def test_coverage_counts_nested_statements():
    r = run("T3DISP")  # IF + 2 then + 2 else + GOBACK = 6
    cov = r["coverage"]
    assert cov["statements_total"] == 6
    assert cov["statements_analyzed"] == 6
    assert cov["needs_human_review"] == 2  # two sign-discard risks


def test_coverage_findings_breakdown_by_classification():
    r = run("EX4UNSG")  # 3 risks + 1 note
    cov = r["coverage"]
    assert cov["findings"] == {"violation": 0, "risk": 3, "note": 1}
    assert cov["needs_human_review"] == 3


def test_assumptions_registry_is_published():
    for fid in ("EX1FEE", "EX4UNSG"):
        r = run(fid)
        ids = {a["id"] for a in r["assumptions"]}
        assert {"divide-precision", "add-carry", "subtract-sum",
                "comp3-length", "display-sign-storage"} <= ids
        assert all(a["topic"] and a["detail"] for a in r["assumptions"])


def test_coverage_absent_when_semantics_not_reached():
    r = run("NEG_PIC19")  # AST-layer rejection
    assert r["coverage"] is None and r["assumptions"] is None


# ---------------------------------------------------------------------------
# schema contract
# ---------------------------------------------------------------------------

def test_schema_version_is_two():
    for fid in ("EX1FEE", "NEG_COL73"):
        assert run(fid)["schema_version"] == 2


def test_explanation_separation_holds_for_every_semantic_code():
    # every rendered semantic diagnostic must carry BOTH the machine model
    # (detail) and the human layer (message/evidence) — classification is
    # derivable without parsing text
    seen = set()
    for s in SAMPLES:
        r = analyze(s["source"], s["filename"])
        for d in r["diagnostics"]:
            if d["code"].startswith("SEM_"):
                seen.add(d["code"])
                assert d["detail"] is not None
                assert d["message"] and d["evidence"]
                assert d["classification"] in ("violation", "risk", "note")
    assert {"SEM_TRUNCATION_HIGH", "SEM_PRECISION_LOSS", "SEM_SIGN_DISCARD",
            "SEM_SIZE_ERROR_GUARD", "SEM_MOVE_SPACES_TO_NUMERIC",
            "SEM_DIVISOR_ZERO"} <= seen


# ---------------------------------------------------------------------------
# CLI: independent, scriptable engine access
# ---------------------------------------------------------------------------

def _write_fixture(tmp: Path, fid: str) -> Path:
    s = next(x for x in SAMPLES if x["id"] == fid)
    p = tmp / s["filename"]
    p.write_text(s["source"])
    return p


def test_cli_clean_program_exit_zero():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = _write_fixture(Path(td), "T3STICKY")
        r = subprocess.run(CLI + ["analyze", str(p)], capture_output=True,
                           text=True, timeout=30)
        assert r.returncode == 0
        assert "EX1FEE" not in r.stdout and "T3STICKY" in r.stdout


def test_cli_violation_exit_one_and_json_mode():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = _write_fixture(Path(td), "EXT-DIVZERO")
        r = subprocess.run(CLI + ["analyze", str(p)], capture_output=True,
                           text=True, timeout=30)
        assert r.returncode == 1
        assert "SEM_DIVISOR_ZERO" in r.stdout and "(violation)" in r.stdout
        rj = subprocess.run(CLI + ["analyze", str(p), "--json"],
                            capture_output=True, text=True, timeout=30)
        env = json.loads(rj.stdout)
        assert env["schema_version"] == 2
        assert env["coverage"]["needs_human_review"] == 0  # violation, not risk
        assert env["summary"]["ok"] is False


def test_cli_risk_only_program_exits_zero():
    # risks (warnings) are possibilities: they must not fail batch runs
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = _write_fixture(Path(td), "EX1FEE")
        r = subprocess.run(CLI + ["analyze", str(p)], capture_output=True,
                           text=True, timeout=30)
        assert r.returncode == 0
        assert "(risk)" in r.stdout


def test_cli_missing_file_exit_two():
    r = subprocess.run(CLI + ["analyze", "/tmp/definitely-missing.cbl"],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 2
