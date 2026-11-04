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
    assert len(body["samples"]) == 23
    fields = {"id", "filename", "title", "origin", "description", "note", "expect_ok", "source"}
    assert fields <= set(body["samples"][0].keys())


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
