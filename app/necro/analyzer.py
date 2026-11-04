"""NecroSpec NVS-0 analysis pipeline: preflight -> lexical -> grammar -> AST.

Pipeline stops at the first layer that produces errors (later layers consume
the previous layer's output). The structured response is the single source
of truth for the UI — no results are ever fabricated client-side.
"""
import re
from typing import List
from . import preflight, lexer, grammar, ast_build
from .diagnostics import Diagnostic, LAYER_PREFLIGHT, LAYER_LEXICAL, \
    LAYER_GRAMMAR, LAYER_AST
from . import semantic
from .lexer import Token


class SourceMeta:
    pass


def analyze(source: str, name: str = "<source>") -> dict:
    lines = source.split("\n")
    diags: List[Diagnostic] = []

    meta = {
        "name": name,
        "bytes": len(source.encode("utf-8", errors="surrogateescape")),
        "lines": len(lines),
        "columns_per_line": 80,
    }

    # Layer 1
    pre = preflight.run_preflight(source)
    if pre:
        return _respond(meta, source, None, None, pre, 1, None)

    # Layer 2
    tokens, lexDiags = lexer.tokenize(lines)
    if lexDiags:
        return _respond(meta, source, tokens, None, lexDiags, 2, None)

    # Layer 3
    ast, gramDiags = grammar.parse(tokens)
    if gramDiags:
        return _respond(meta, source, tokens, None, gramDiags, 3, None)

    # Layer 4
    ast, _symbols = ast_build.analyze_ast(ast, diags)
    astDiags = [d for d in diags]
    if any(d.severity == "error" for d in astDiags):
        return _respond(meta, source, tokens, ast, astDiags, 4, None)

    # Layer 5 — semantic analysis (runs only on a structurally clean AST;
    # its products ship even when it raises findings of its own)
    products, semDiags = semantic.analyze(ast)
    return _respond(meta, source, tokens, ast, semDiags, 5, products)


def _respond(meta: dict, source, tokens: List[Token], ast, diags: List[Diagnostic],
             failed_layer: int, products: dict | None) -> dict:
    layer_names = ["Preflight", "Lexical", "Grammar", "AST", "Semantic"]
    layer_status = []
    for idx, lname in enumerate(layer_names, start=1):
        if idx < failed_layer:
            layer_status.append({"layer": lname, "status": "passed"})
        elif idx == failed_layer:
            errors = [d for d in diags if d.severity == "error"]
            layer_status.append({
                "layer": lname,
                "status": "failed" if errors else "passed",
                "diagnostics": len(errors),
            })
        else:
            layer_status.append({"layer": lname, "status": "skipped"})

    ordered = sorted(diags, key=lambda d: (d.line is None, d.line or 0, d.col or 0))
    error_count = sum(1 for d in ordered if d.severity == "error")
    warning_count = sum(1 for d in ordered if d.severity == "warning")

    # attach one line of source context to located diagnostics
    if source:
        src_lines = source.split("\n")
        for d in ordered:
            if d.line and 1 <= d.line <= len(src_lines):
                d.context_line = src_lines[d.line - 1][:80]

    summary = {
        "ok": error_count == 0,
        "errors": error_count,
        "warnings": warning_count,
        "infos": len(ordered) - error_count - warning_count,
        "token_count": len(tokens) if tokens else 0,
        "failed_layer": layer_names[failed_layer - 1] if error_count else None,
    }
    if ast:
        summary["program_name"] = ast["identification_division"]["program_name"]
        summary["is_initial"] = ast["identification_division"]["is_initial"]
        sym = ast.get("symbols", {})
        summary["using"] = sym.get("using_resolved", [])

    return {
        "meta": meta,
        "layers": layer_status,
        "diagnostics": [d.to_json() for d in ordered],
        "tokens": [t.to_json() for t in (tokens or [])],
        "ast": ast,
        "symbols": products.get("symbols") if products else None,
        "references": products.get("references") if products else None,
        "semantic_counts": products.get("counts") if products else None,
        "summary": summary,
    }
