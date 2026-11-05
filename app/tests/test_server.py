"""NecroSpec HTTP API tests — boots the real server on an ephemeral port."""
import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

import server as server_mod  # noqa: E402
from necro.fixtures import SAMPLES  # noqa: E402

_server = None
_base = None


def setup_module(module=None):
    global _server, _base
    _server = server_mod.ThreadingHTTPServer(("127.0.0.1", 0), server_mod.Handler)
    t = threading.Thread(target=_server.serve_forever, daemon=True)
    t.start()
    _base = f"http://127.0.0.1:{_server.server_address[1]}"


def teardown_module(module=None):
    if _server:
        _server.shutdown()


def get(path):
    try:
        with urllib.request.urlopen(_base + path, timeout=5) as res:
            return res.status, json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def post(path, body, raw=False):
    data = body if raw else json.dumps(body).encode()
    req = urllib.request.Request(
        _base + path, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status, json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def test_health():
    status, body = get("/api/health")
    assert status == 200
    assert body["status"] == "ok"
    assert "Rev6.4.2" in body["engine"]


def test_samples_endpoint():
    status, body = get("/api/samples")
    assert status == 200
    assert len(body["samples"]) == 25
    fields = {"id", "filename", "title", "origin", "description", "note", "expect_ok", "source"}
    assert fields <= set(body["samples"][0].keys())


def test_project_api_preserves_controlled_unreadable_input_and_schema():
    status, body = post("/api/project", {
        "name": "controlled-no-source",
        "files": [{
            "path": "src/UNREADABLE.cbl",
            "error": "Controlled demonstration: source intentionally omitted.",
        }],
    })
    assert status == 200
    assert body["schema_version"] == 8
    assert body["files"] == []
    assert body["skipped"] == [{
        "path": "src/UNREADABLE.cbl",
        "reason": "unreadable: Controlled demonstration: source intentionally omitted.",
        "code": "DEP_FILE_UNREADABLE",
    }]
    readiness = body["migration_readiness"]
    assert readiness["project"]["readiness_state"] == "not_assessable"
    assert readiness["project"]["skipped_inputs"][0]["path"] == "src/UNREADABLE.cbl"


def test_readiness_demo_cases_use_normal_project_api_and_rules():
    status, body = get("/api/project/readiness-examples")
    assert status == 200
    assert "not customer code" in body["disclaimer"].lower()
    expected = {
        "ready": "ready_for_planning",
        "investigation": "investigation_required",
        "not_assessable": "not_assessable",
    }
    assert {case["id"] for case in body["cases"]} == set(expected)
    for case in body["cases"]:
        status, result = post("/api/project", {
            "name": case["name"], "files": case["files"],
        })
        assert status == 200
        assert result["schema_version"] == 8
        assert result["migration_readiness"]["project"]["readiness_state"] == expected[case["id"]]
    investigation = next(c for c in body["cases"] if c["id"] == "investigation")
    risk_result = post("/api/project", {
        "name": investigation["name"], "files": investigation["files"],
    })[1]
    risk_program = risk_result["migration_readiness"]["programs"][0]
    assert any(ref.get("code") == "SEM_PRECISION_LOSS"
               and ref.get("classification") == "risk"
               for ref in risk_program["dimensions"]["data_integrity"]["evidence_refs"])
    no_source = next(c for c in body["cases"] if c["id"] == "not_assessable")
    assert "not a real read failure" in no_source["description"].lower()


def test_analyze_clean_program():
    status, body = post("/api/analyze", {
        "source": SAMPLES[0]["source"], "filename": "EX1FEE.cbl",
    })
    assert status == 200
    assert body["summary"]["ok"] is True
    assert body["summary"]["program_name"] == "EX1FEE"


def test_analyze_rejected_program():
    status, body = post("/api/analyze", {
        "source": SAMPLES[14]["source"], "filename": "NEG_COL73.cbl",
    })
    assert status == 200  # a rejected program is a valid analysis result
    assert body["summary"]["ok"] is False


def test_analyze_bad_json():
    status, body = post("/api/analyze", b"this is not json", raw=True)
    assert status == 400
    assert body["error"]["code"] == "BAD_JSON"


def test_analyze_missing_source():
    status, body = post("/api/analyze", {"filename": "x.cbl"})
    assert status == 422
    assert body["error"]["code"] == "MISSING_SOURCE"


def test_unknown_endpoint():
    status, body = get("/api/nope")
    assert status == 404
    assert body["error"]["code"] == "UNKNOWN_ENDPOINT"


def test_static_frontend_served():
    req = urllib.request.Request(_base + "/")
    with urllib.request.urlopen(req, timeout=5) as res:
        html = res.read().decode()
        assert res.status == 200
        assert "NecroSpec" in html
        assert "text/html" in res.headers["Content-Type"]


def test_path_traversal_blocked():
    try:
        with urllib.request.urlopen(_base + "/../server.py", timeout=5) as res:
            body = res.read().decode()
            assert "ThreadingHTTPServer" not in body, "path traversal leak!"
    except urllib.error.HTTPError:
        pass  # 4xx/5xx is fine — content must never leak


def test_sibling_prefix_directory_blocked():
    """A sibling directory whose name shares the web root's string prefix
    (app/web_dist_evil) must NOT be served by the string-prefix check that
    existed before the containment fix."""
    evil = APP / "web_dist_evil"
    marker = "TOP-SECRET-SIBLING-PAYLOAD"
    evil.mkdir(exist_ok=True)
    (evil / "secret.html").write_text(marker)
    try:
        for target in ("/../web_dist_evil/secret.html",
                       "/..%2Fweb_dist_evil%2Fsecret.html"):
            try:
                with urllib.request.urlopen(_base + target, timeout=5) as res:
                    body = res.read().decode()
                    assert marker not in body, f"sibling leak via {target}!"
            except urllib.error.HTTPError:
                pass  # 403/404 — blocked, acceptable
    finally:
        (evil / "secret.html").unlink()
        evil.rmdir()


def test_dot_segments_and_encoded_traversal_blocked():
    marker = "ThreadingHTTPServer"
    server_file = APP / "server.py"
    assert marker in server_file.read_text()
    for target in ("/../server.py",
                   "/..%2Fserver.py",
                   "/%2e%2e/server.py",
                   "/..//server.py",
                   "/../../server.py"):
        try:
            with urllib.request.urlopen(_base + target, timeout=5) as res:
                body = res.read().decode()
                assert marker not in body, f"source leak via {target}!"
        except urllib.error.HTTPError:
            pass


def test_legitimate_static_asset_still_served():
    index = APP / "web_dist" / "index.html"
    asset_match = None
    for line in index.read_text().splitlines():
        if "assets/index-" in line and ".js" in line:
            asset_match = line
            break
    assert asset_match, "built asset reference not found in index.html"
    asset = "assets/" + asset_match.split("assets/")[1].split('"')[0]
    with urllib.request.urlopen(_base + "/" + asset, timeout=5) as res:
        body = res.read().decode()
        assert res.status == 200
        assert "NecroSpec" in body or "root" in body  # real bundle content
