"""NecroSpec project-intelligence tests (Milestone 3).

Covers: deterministic ingestion, path safety, duplicate basenames,
COPY/CALL discovery from source evidence, resolution (resolved / missing /
ambiguous / dynamic), nested copybooks, cycles, per-file analysis results,
impact analysis, determinism, API integration, CLI exit-code contract.
The example project under examples/sample-project is the shared fixture
(a realistic multi-file application); synthetic projects in temp dirs cover
ingestion failure modes.
"""
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from necro.project import (analyze_project, discover_references,
                           ingest_directory, impact)  # noqa: E402

EXAMPLE = APP.parent / "examples" / "sample-project"
CLI = [sys.executable, str(APP / "cli.py")]


def example_project():
    name, entries = ingest_directory(str(EXAMPLE))
    return analyze_project(name, entries)


def edge(r, **kw):
    out = [e for e in r["edges"]
           if all(e.get(k) == v for k, v in kw.items())]
    return out


def finding(r, code):
    return [d for d in r["findings"] if d["code"] == code]


# ---------------------------------------------------------------------------
# ingestion
# ---------------------------------------------------------------------------

def test_example_project_exists_and_ingests():
    assert EXAMPLE.is_dir()
    r = example_project()
    assert r["summary"]["programs"] == 12  # M8.1.1 adds EVALFIX
    assert r["summary"]["copybooks"] == 6


def test_ingestion_deterministic_and_paths_preserved():
    r1 = example_project()
    r2 = example_project()
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)
    ids = [f["file_id"] for f in r1["files"]]
    assert ids == sorted(ids)
    assert "copybooks/EMPREC.cpy" in ids and "src/PAYROLL.cbl" in ids


def test_unsafe_paths_rejected_not_silently_ignored():
    r = analyze_project("t", [
        {"path": "../evil.cbl", "content": "       IDENTIFICATION DIVISION.\n"},
        {"path": "/abs/path.cbl", "content": "x"},
        {"path": "a/../b.cbl", "content": "x"},
        {"path": "ok/note.txt", "content": "hello"},
    ])
    assert len(finding(r, "DEP_PATH_REJECTED")) == 3
    assert all(f["file_id"] != "../evil.cbl" for f in r["files"])
    assert any(s["path"] == "ok/note.txt" and s["code"] == "DEP_EXT_UNSUPPORTED"
               for s in r["skipped"])


def test_unreadable_files_reported():
    r = analyze_project("t", [
        {"path": "src/BAD.cbl", "error": "PermissionError"},
        {"path": "src/OK.cbl",
         "content": "       IDENTIFICATION DIVISION.\n"},
    ])
    misses = finding(r, "DEP_FILE_UNREADABLE")
    assert len(misses) == 1
    assert any(s["path"] == "src/BAD.cbl" for s in r["skipped"])
    assert misses[0]["classification"] == "violation"


def test_duplicate_basenames_flagged():
    r = example_project()
    dups = finding(r, "DEP_DUPLICATE_BASENAME")
    assert len(dups) == 1
    assert set(dups[0]["detail"]["files"]) == {
        "libA/USRINFO.cpy", "libB/USRINFO.cpy"}


# ---------------------------------------------------------------------------
# COPY discovery + resolution
# ---------------------------------------------------------------------------

def test_copy_discovery_records_evidence_and_location():
    r = example_project()
    e = edge(r, kind="copy", **{"from": "src/EMPREC.cbl"})[0]
    assert e["to"] == "copybooks/EMPREC.cpy"
    assert e["resolution"] == "resolved"
    assert e["line"] == 6 and e["target"] == "EMPREC"
    assert e["text"].startswith("COPY EMPREC")
    # the reference list carries the same evidence
    ref = [x for x in r["references"]
           if x["file"] == "src/EMPREC.cbl" and x["kind"] == "copy"][0]
    assert ref["line"] == 6


def test_copy_prefers_copybook_over_same_name_program():
    # src/EMPREC.cbl COPYs EMPREC while a program with the same stem exists:
    # resolution must pick the .cpy file, not the program
    r = example_project()
    e = edge(r, kind="copy", **{"from": "src/EMPREC.cbl"})[0]
    assert e["to"] == "copybooks/EMPREC.cpy"


def test_missing_copybook_is_violation():
    r = example_project()
    e = edge(r, kind="copy", target="PAYCODES")[0]
    assert e["resolution"] == "missing" and e["to"] is None
    d = finding(r, "DEP_COPYBOOK_MISSING")[0]
    assert d["severity"] == "error" and d["classification"] == "violation"
    assert d["line"] == 5  # inside copybooks/EMPREC.cpy
    assert d["context_line"] is None or "COPY PAYCODES" in (d["evidence"] or "")


def test_ambiguous_copybook_lists_candidates():
    r = example_project()
    e = edge(r, kind="copy", **{"from": "src/REPORT.cbl"})[0]
    assert e["resolution"] == "ambiguous"
    assert set(e["candidates"]) == {"libA/USRINFO.cpy", "libB/USRINFO.cpy"}
    d = finding(r, "DEP_COPYBOOK_AMBIGUOUS")[0]
    assert d["severity"] == "warning" and d["classification"] == "risk"


def test_nested_copy_discovered_inside_copybooks():
    r = example_project()
    assert edge(r, kind="copy", **{"from": "copybooks/EMPREC.cpy",
                                   "to": None, "target": "PAYCODES"})
    assert edge(r, kind="copy", **{"from": "copybooks/P.cpy",
                                   "to": "copybooks/Q.cpy"})


def test_cycle_detection():
    r = example_project()
    assert r["cycles"] == [["copybooks/P.cpy", "copybooks/Q.cpy"]]
    d = finding(r, "DEP_CYCLE")[0]
    assert d["classification"] == "risk"
    assert "copybooks/P.cpy -> copybooks/Q.cpy" in d["message"]


def test_replacing_form_recorded_but_marked_unsupported():
    refs = discover_references("X", "       COPY SOMEREC REPLACING A BY B.\n")
    assert refs[0]["target"] == "SOMEREC" and refs[0]["form"] == "replacing"
    r = analyze_project("t", [
        {"path": "p.cbl", "content": "       COPY SOMEREC REPLACING A BY B.\n"}])
    assert finding(r, "DEP_COPY_REPLACING_UNSUPPORTED")


def test_comment_lines_are_not_discovered():
    refs = discover_references("X", "      * COPY GHOST.\n")
    assert refs == []


def test_similarity_never_resolves():
    r = analyze_project("t", [
        {"path": "p.cbl", "content": "       COPY TOTALS.\n"},
        {"path": "c/TOTALS-BACKUP.cpy", "content": "x"},
        {"path": "c/TOTALZ.cpy", "content": "x"},
    ])
    e = edge(r, kind="copy")[0]
    assert e["resolution"] == "missing"  # no exact stem match


# ---------------------------------------------------------------------------
# CALL discovery + resolution
# ---------------------------------------------------------------------------

def test_static_call_resolved_with_evidence():
    r = example_project()
    e = edge(r, kind="call", **{"from": "src/PAYROLL.cbl",
                                "target": "GLUPDATE"})[0]
    assert e["to"] == "src/GLUPDATE.cbl" and e["resolution"] == "resolved"
    assert e["target_form"] == "literal"
    assert e["line"] == 11


def test_dynamic_call_reported_unresolved():
    r = example_project()
    e = edge(r, kind="call", target="WS-PGM")[0]
    assert e["resolution"] == "dynamic" and e["to"] is None
    assert e["target_form"] == "identifier"
    d = finding(r, "DEP_CALL_DYNAMIC")[0]
    assert d["classification"] == "risk"


def test_static_call_without_target_program():
    r = analyze_project("t", [
        {"path": "p.cbl",
         "content": '       CALL "NOWHERE" USING X\n'},
    ])
    e = edge(r, kind="call")[0]
    assert e["resolution"] == "unresolved"
    assert finding(r, "DEP_CALL_STATIC_UNRESOLVED")


# ---------------------------------------------------------------------------
# per-file analysis + project envelope
# ---------------------------------------------------------------------------

def test_per_file_full_analysis_with_semantic_finding():
    r = example_project()
    pf = r["per_file"]["src/GLUPDATE.cbl"]
    assert pf["status"] == "analyzed"
    assert pf["result"]["schema_version"] == 2  # embedded single-file envelope
    codes = [d["code"] for d in pf["result"]["diagnostics"]]
    assert "SEM_PRECISION_LOSS" in codes  # existing semantic finding preserved


def test_per_file_rejected_carry_reason_and_no_downgrade():
    r = example_project()
    pf = r["per_file"]["src/PAYROLL.cbl"]
    assert pf["status"] == "rejected"
    # the quoted CALL literal is outside the frozen lexicon, so the file is
    # rejected at the Lexical layer — the reason states the layer and codes
    assert "Lexical" in pf["reason"]
    # the embedded diagnostics keep their severity — no silent downgrade
    assert pf["result"]["summary"]["failed_layer"] == "Lexical"
    copybook = r["per_file"]["copybooks/P.cpy"]
    assert copybook["status"] == "copybook"


def test_project_envelope_shape_and_coverage():
    r = example_project()
    assert r["schema_version"] == 8  # v8 adds migration readiness
    for key in ("project", "files", "skipped", "references", "edges",
                "cycles", "per_file", "findings", "coverage", "assumptions",
                "summary", "overview", "migration_readiness"):
        assert key in r
    cov = r["coverage"]
    assert cov["files_total"] == 18  # M7 DECISIONS + M8.1.1 EVALFIX
    assert cov["files_analyzed"] == 1 and cov["files_rejected"] == 11
    assert cov["files_copybook"] == 6
    assert cov["dependencies_total"] == 18
    assert cov["dependencies_resolved"] == 14
    assert cov["dependencies_unresolved"] == 3
    assert cov["dependencies_ambiguous"] == 1
    assert cov["cycles"] == 1
    ids = {a["id"] for a in r["assumptions"]}
    assert {"no-copy-expansion", "resolution-by-stem", "calls-not-executed",
            "impact-not-runtime", "subset-per-file"} <= ids


def test_project_findings_carry_ids_and_classification():
    r = example_project()
    for d in r["findings"]:
        assert d["finding_id"] and d["classification"] in (
            "violation", "risk", "note", "unsupported")
        assert d["evidence"]


# ---------------------------------------------------------------------------
# graph + impact
# ---------------------------------------------------------------------------

def test_direct_and_transitive_impact():
    r = example_project()
    imp = impact(r, "copybooks/Q.cpy")
    assert imp["direct_dependencies"] == [
        {"to": "copybooks/P.cpy", "kind": "copy", "line": 4,
         "evidence": "COPY P."}]
    assert imp["direct_dependants"] == [
        {"from": "copybooks/P.cpy", "kind": "copy", "line": 4,
         "evidence": "COPY Q."}]
    assert imp["transitive_dependants"] == [
        "copybooks/P.cpy", "src/CYCTEST.cbl"]
    assert "not proof" in imp["note"]


def test_forward_transitive_dependencies_across_cycle():
    # CYCTEST -> P -> Q (cycle): forward closure must terminate and include
    # both copybooks; a copybook in the cycle transitively depends on its
    # partner but never on itself
    r = example_project()
    imp = impact(r, "src/CYCTEST.cbl")
    assert imp["transitive_dependencies"] == [
        "copybooks/P.cpy", "copybooks/Q.cpy"]
    imp_q = impact(r, "copybooks/Q.cpy")
    assert imp_q["transitive_dependencies"] == ["copybooks/P.cpy"]
    assert imp_q["transitive_dependants"] == [
        "copybooks/P.cpy", "src/CYCTEST.cbl"]


def test_coverage_reports_items_needing_human_review():
    # risk-class findings (dynamic CALL, ambiguous COPY, cycle) are the
    # review items; the missing-copybook violation is not a review item
    r = example_project()
    assert r["coverage"]["needs_human_review"] == 14  # +DECISIONS CALL size mismatch
    # single-file schema uses the same semantics: risks, not violations
    gl = r["per_file"]["src/GLUPDATE.cbl"]["result"]
    assert gl["coverage"]["needs_human_review"] == \
        gl["coverage"]["findings"]["risk"]


def test_single_file_cli_unchanged():
    # Milestone 3 must not reinterpret the single-file command
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "OK.cbl"
        p.write_text(
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. OKP.\n"
            "       DATA DIVISION.\n"
            "       LINKAGE SECTION.\n"
            "       01  LK-X             PIC 9.\n"
            "       PROCEDURE DIVISION USING LK-X.\n"
            "           GOBACK.\n")
        clean = subprocess.run(CLI + ["analyze", str(p)],
                               capture_output=True, text=True, timeout=30)
        assert clean.returncode == 0 and "OKP" in clean.stdout
        (p.parent / "BAD.cbl").write_text(
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. BADP.\n"
            "       DATA DIVISION.\n"
            "       LINKAGE SECTION.\n"
            "       PROCEDURE DIVISION.\n"
            "           GOBACK.\n")
        bad = subprocess.run(CLI + ["analyze", str(p.parent / "BAD.cbl")],
                             capture_output=True, text=True, timeout=30)
        assert bad.returncode == 1  # grammar violation -> exit 1


def test_impact_lists_unresolved_relationships():
    r = example_project()
    imp = impact(r, "src/PAYROLL.cbl")
    unres = {u["target"]: u["resolution"] for u in imp["unresolved_relationships"]}
    assert unres == {"WS-PGM": "dynamic"}
    imp2 = impact(r, "src/REPORT.cbl")
    assert any(u["resolution"] == "ambiguous" for u in imp2["unresolved_relationships"])


def test_graph_edges_sorted_and_stable():
    r = example_project()
    keys = [(e["from"], e["line"], e["kind"], e["target"]) for e in r["edges"]]
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------

def _post_project(base, body):
    req = urllib.request.Request(
        base + "/api/project", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.load(res)


def test_api_project_and_example_endpoints():
    import threading
    import server as server_mod
    srv = server_mod.ThreadingHTTPServer(("127.0.0.1", 0), server_mod.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/api/project/example",
                                    timeout=10) as res:
            ex = json.load(res)
        assert ex["name"] == "sample-project" and len(ex["files"]) == 18
        r = _post_project(base, {"name": ex["name"], "files": ex["files"]})
        assert r["schema_version"] == 8  # v8 adds migration readiness
        assert len(r["edges"]) == 18
        assert len(r["impact"]) == 18
        imp = r["impact"]["copybooks/Q.cpy"]
        assert imp["transitive_dependants"] == [
            "copybooks/P.cpy", "src/CYCTEST.cbl"]
        bad = _post_project(base, {"files": [
            {"path": "../x.cbl", "content": "y"}]})
        assert bad["findings"][0]["code"] == "DEP_PATH_REJECTED"
    finally:
        srv.shutdown()


# ---------------------------------------------------------------------------
# CLI contract
# ---------------------------------------------------------------------------

def test_cli_project_exit_codes_and_json():
    r = subprocess.run(CLI + ["project", "analyze", str(EXAMPLE), "--json"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 1  # missing copybook = violation-class finding
    env = json.loads(r.stdout)
    assert env["schema_version"] == 8
    assert env["coverage"]["dependencies_resolved"] == 14

    # human mode: still exit 1, findings printed
    r2 = subprocess.run(CLI + ["project", "analyze", str(EXAMPLE)],
                        capture_output=True, text=True, timeout=60)
    assert r2.returncode == 1
    assert "DEP_COPYBOOK_MISSING" in r2.stdout

    # not a directory -> exit 2
    r3 = subprocess.run(CLI + ["project", "analyze", "/tmp/no-such-dir-x9"],
                        capture_output=True, text=True, timeout=60)
    assert r3.returncode == 2


def test_cli_project_clean_project_exit_zero():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "c").mkdir()
        (root / "p.cbl").write_text(
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. P.\n"
            "       DATA DIVISION.\n"
            "       LINKAGE SECTION.\n"
            "       01  LK-X             PIC 9.\n"
            "       PROCEDURE DIVISION USING LK-X.\n"
            "           GOBACK.\n")
        (root / "c" / "WSREC.cpy").write_text("       05  F-A PIC 9.\n")
        r = subprocess.run(CLI + ["project", "analyze", str(root)],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0
