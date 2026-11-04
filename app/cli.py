#!/usr/bin/env python3
"""NecroSpec CLI — independent, scriptable access to the analysis engine.

The engine is deliberately UI-independent; this tool exposes the same
deterministic analysis the workstation uses for batch and pipeline use
(consultancy assessments, CI gates).

Usage:
  python3 app/cli.py analyze FILE [FILE...] [--json]

Exit codes: 0 = no violation-class findings; 1 = violations found;
2 = usage or I/O error. Warnings (risks) do not fail the run by design —
they are possibilities for human review, not proof of breakage.
"""
import argparse
import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

from necro.analyzer import analyze  # noqa: E402

SEV_ORDER = {"error": 0, "warning": 1, "info": 2}


def _print_human(name: str, result: dict) -> None:
    s = result["summary"]
    print(f"\n{name}  —  {s.get('program_name') or '?'}"
          f"{' (IS INITIAL)' if s.get('is_initial') else ''}")
    stages = " -> ".join(
        "{}:{}".format(l["layer"], l["status"][0].upper())
        for l in result["layers"])
    print(f"  layers: {stages}")
    cov = result.get("coverage")
    if cov:
        print(f"  coverage: {cov['statements_analyzed']}/{cov['statements_total']} "
              f"statements analyzed · {cov['needs_human_review']} finding(s) need human review")
    print(f"  verdict: {'accepted' if s['ok'] else 'REJECTED'}"
          f"{' at ' + s['failed_layer'] if s['failed_layer'] else ''}"
          f" · {s['errors']} error(s), {s['warnings']} warning(s), {s['infos']} info")
    if result["diagnostics"]:
        print("  findings:")
        for d in sorted(result["diagnostics"],
                        key=lambda d: (SEV_ORDER.get(d["severity"], 9),
                                       d["line"] is None, d["line"] or 0)):
            loc = f"L{d['line']}" if d["line"] else "—"
            print(f"    [{d['severity']:7}] {d['code']} ({d['classification']}) "
                  f"{loc} [{d['finding_id']}]")
            print(f"        {d['message']}")
            if d["evidence"]:
                print(f"        evidence: {d['evidence']}")
    cov_limits = result.get("assumptions") or []
    if cov_limits:
        print(f"  model limits on record: {', '.join(a['id'] for a in cov_limits)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="necrospec", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="analyze fixed-format COBOL files")
    a.add_argument("files", nargs="+", help=".cbl/.cob files to analyze")
    a.add_argument("--json", action="store_true",
                   help="emit the full structured analysis envelope per file")
    args = ap.parse_args(argv)

    violations = 0
    for path in args.files:
        p = Path(path)
        if not p.is_file():
            print(f"necrospec: cannot read {path}", file=sys.stderr)
            return 2
        result = analyze(p.read_text(encoding="utf-8", errors="strict"),
                         p.name)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            _print_human(p.name, result)
        violations += result["summary"]["errors"]
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
