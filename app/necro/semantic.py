"""NecroSpec semantic analysis (layer 5) — Milestone 2 + platform model.

Consumes the JSON AST produced by grammar+ast_build (which guarantee: every
referenced identifier resolves to a declared elementary numeric item; group
items, duplicates, undeclared names, PICTURE limits and sign-clause misuse
are already rejected at layer 4). This layer adds migration-preparation
insight on top of that guaranteed-clean baseline:

  * data dictionary — categories, byte lengths, digits, precision, hierarchy
  * references     — every identifier use with role and exact location
  * risks          — capacity/precision findings as CLASSIFIED, QUANTIFIED
                     records (separation of concerns: risk classification is
                     machine-readable; explanation is rendered separately)

Separation of concerns (platform requirement): analysis produces `Risk`
records carrying only codes, severity, location, machine-readable `detail`
quantities and explanation *inputs*. `explain()` renders the human text.
Future consumers (risk aggregation, migration readiness, multi-file reports)
consume `detail` — never the prose.

Determinism: every finding is derived from declared PICTUREs, literal text
and fixed arithmetic bounds — no heuristics, no randomness. Severity policy:
definite violations are ERROR; capacity/precision possibilities that COBOL
would silently truncate are WARNING; deliberately guarded code is INFO.

Scope honesty (frozen Rev6.4.2 subset): every elementary item in this subset
is numeric (the pic_str EBNF admits only 9/V/S forms). Group items are
recorded in the dictionary with category "group (alphanumeric)" because that
is their COBOL class, but the grammar already rejects their use as operands.
Alphanumeric elementary PICTUREs (X/…), editing symbols and other usages are
outside the frozen grammar and are NOT invented here. `assumptions` records
every model limit a consumer must know; `coverage` states what was analyzed
and how much needs human review.

All codes below are [EXT] — agent-stable extensions, never corpus codes.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional

from .diagnostics import (CLASS_NOTE, CLASS_RISK, CLASS_VIOLATION,
                          Diagnostic, LAYER_SEMANTIC,
                          SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARNING,
                          _SEVERITY_CLASSIFICATION)

# ---- stable semantic diagnostic codes ([EXT]) ---------------------------
SEM_DIVISOR_ZERO = "SEM_DIVISOR_ZERO"                # literal 0 divisor
SEM_MOVE_SPACES_TO_NUMERIC = "SEM_MOVE_SPACES_TO_NUMERIC"  # SPACES -> numeric
SEM_TRUNCATION_HIGH = "SEM_TRUNCATION_HIGH"          # high-order digits lost
SEM_PRECISION_LOSS = "SEM_PRECISION_LOSS"            # low-order digits lost
SEM_SIGN_DISCARD = "SEM_SIGN_DISCARD"                # unsigned receiver, signed result
SEM_SIZE_ERROR_GUARD = "SEM_SIZE_ERROR_GUARD"        # overflow handled (info)

# Model assumptions and limits, published with every analysis: "what remains
# uncertain" is part of the result, not a footnote.
ASSUMPTIONS = [
    {
        "id": "divide-precision",
        "topic": "DIVIDE-derived precision",
        "detail": ("Quotient precision cannot be established statically; "
                   "receivers of division results are not truncation- or "
                   "precision-checked. Needs human review."),
    },
    {
        "id": "add-carry",
        "topic": "ADD capacity bound",
        "detail": ("The integer bound adds one carry digit to the widest "
                   "established operand; multi-digit carry propagation "
                   "beyond one digit is not modeled."),
    },
    {
        "id": "subtract-sum",
        "topic": "SUBTRACT capacity bound",
        "detail": ("Subtrahends are summed before subtraction; the bound "
                   "adds (n-1) carry digits for n subtrahends."),
    },
    {
        "id": "comp3-length",
        "topic": "COMP-3 byte length",
        "detail": ("Storage is ceil((digits+1)/2) bytes: one sign nibble "
                   "plus two digits per byte, per the subset's "
                   "packed-decimal rule."),
    },
    {
        "id": "display-sign-storage",
        "topic": "DISPLAY byte length",
        "detail": ("A separate sign character adds one byte only when SIGN "
                   "SEPARATE is declared; overpunch sign forms are outside "
                   "the subset."),
    },
]


# =========================================================================
# data dictionary
# =========================================================================

def _usage_label(usage: Optional[str]) -> str:
    if usage == "comp3":
        return "COMP-3 (packed decimal)"
    return "DISPLAY"


def _byte_length(elem: dict) -> Optional[int]:
    """Storage bytes for an elementary item, per subset representation rules
    (validated against the corpus byte annotations in rev4_extract §3.1)."""
    if elem.get("digits") is None:
        return None
    digits = elem["digits"]
    if elem.get("usage") == "comp3":
        return (digits + 1 + 1) // 2  # + sign nibble, ceil
    # DISPLAY: one byte per digit; separate sign adds one byte
    if elem.get("signed") and elem.get("sign"):
        return digits + 1
    return digits


def _dictionary(symbols_json: dict) -> List[dict]:
    """Build the data dictionary from the AST symbol table (parent links are
    derived during the walk; children keep declaration order)."""
    out: List[dict] = []

    def entry(node: dict, parent: Optional[str], section: str) -> dict:
        children = node.get("children") or []
        exp = node.get("expanded")
        e = {
            "name": node["name"],
            "level": node["level"],
            "section": section,
            "line": node["line"],
            "col": node["col"],
            "usage": node.get("usage"),
            "usage_label": _usage_label(node.get("usage")),
            "elementary": node.get("elementary", not children),
            "category": ("numeric" if (not children and exp) else
                         "group (alphanumeric)"),
            "picture": node.get("picture"),
            "signed": exp["signed"] if exp else None,
            "integer_digits": exp["int_digits"] if exp else None,
            "fractional_digits": exp["frac_digits"] if exp else None,
            "digits": (exp["int_digits"] + exp["frac_digits"]) if exp else None,
            "byte_length": None,
            "sign": node.get("sign"),
            "value": node.get("value"),
            "parent": parent,
            "children": [],
        }
        total = 0
        for ch in children:
            ce = entry(ch, node["name"], section)
            e["children"].append(ce)
            total += ce["byte_length"] or 0
        if not children:
            e["byte_length"] = _byte_length(e)
        else:
            e["byte_length"] = total if total > 0 else None
        return e

    for root in symbols_json.get("linkage", []):
        out.append(entry(root, None, root.get("section", "LINKAGE")))
    for root in symbols_json.get("working_storage", []):
        out.append(entry(root, None, root.get("section", "WORKING-STORAGE")))
    return out


def _flatten_dict(entries: List[dict]) -> List[dict]:
    out: List[dict] = []

    def walk(e: dict):
        out.append(e)
        for c in e["children"]:
            walk(c)
    for e in entries:
        walk(e)
    return out


# =========================================================================
# numeric capacity model
# =========================================================================

class Cap:
    """Established numeric capacity of an operand: integer/fractional digit
    bounds. `unknown` marks division-derived values whose precision the
    analyzer refuses to invent."""

    __slots__ = ("int_d", "frac_d", "signed", "unknown")

    def __init__(self, int_d: Optional[int], frac_d: Optional[int],
                 signed: bool, unknown: bool = False):
        self.int_d = int_d
        self.frac_d = frac_d
        self.signed = signed
        self.unknown = unknown


def _literal_cap(text: str) -> Cap:
    t = text.lstrip("+-")
    if "." in t:
        i, f = t.split(".", 1)
        return Cap(len(i) or 1, len(f), False)
    return Cap(len(t), 0, False)


def _ident_cap(item: dict) -> Cap:
    # dictionary entries carry integer_digits/fractional_digits/signed
    if item.get("digits") is None:
        return Cap(None, None, False, unknown=True)
    return Cap(item["integer_digits"], item["fractional_digits"],
               bool(item.get("signed")))


def _figurative_cap(text: str) -> Cap:
    up = text.upper()
    if up in ("ZERO", "ZEROS", "ZEROES"):
        return Cap(1, 0, False)
    # SPACE/QUOTE/HIGH-VALUE/... are nonnumeric figuratives
    return Cap(None, None, False, unknown=True)


def _is_zero_literal(node: dict) -> bool:
    return (node.get("kind") == "literal"
            and _literal_cap(node["text"]).int_d == 1
            and _literal_cap(node["text"]).frac_d == 0
            and node["text"].lstrip("+-") == "0")


def expr_cap(node: dict, by_name: dict) -> Cap:
    """Derived capacity of an expression; deterministic bounds only."""
    kind = node.get("kind")
    if kind == "literal":
        return _literal_cap(node["text"])
    if kind == "figurative":
        return _figurative_cap(node["text"])
    if kind == "identifier":
        item = by_name.get(node["name"].upper())
        return _ident_cap(item) if item else Cap(None, None, True, unknown=True)
    if kind == "binary":
        l = expr_cap(node["left"], by_name)
        r = expr_cap(node["right"], by_name)
        op = node["op"]
        if l.unknown or r.unknown:
            return Cap(None, None, l.signed or r.signed, unknown=True)
        if op == "+":
            return Cap(max(l.int_d, r.int_d) + 1, max(l.frac_d, r.frac_d),
                       l.signed or r.signed)
        if op == "-":
            return Cap(max(l.int_d, r.int_d), max(l.frac_d, r.frac_d),
                       l.signed or r.signed or True)
        if op == "*":
            return Cap(l.int_d + r.int_d, l.frac_d + r.frac_d,
                       l.signed or r.signed)
        if op == "/":
            # quotient precision cannot be established statically
            return Cap(None, None, l.signed or r.signed, unknown=True)
    return Cap(None, None, True, unknown=True)


def _describe(item: dict) -> str:
    # dictionary entries carry integer_digits/fractional_digits/signed
    if not item.get("elementary") or item.get("digits") is None:
        return f"{item['name']} (group, line {item['line']})"
    sign = "signed" if item.get("signed") else "unsigned"
    return (f"{item['name']} is PIC {item.get('picture')} ({sign}, "
            f"{item['integer_digits']} int + {item['fractional_digits']} "
            f"frac digits, declared at line {item['line']})")


# =========================================================================
# risk records (classification) and their explanation (rendering)
# =========================================================================

@dataclass
class Risk:
    """A classified, quantified finding. `detail` is the stable
    machine-readable contract; `ctx` carries the inputs explain() needs."""
    code: str
    severity: str
    line: Optional[int]
    col: Optional[int]
    detail: Dict[str, object]
    ctx: Dict[str, object]

    @property
    def classification(self) -> str:
        return _SEVERITY_CLASSIFICATION[self.severity]


def explain(risk: Risk) -> Diagnostic:
    """Render a Risk as a user-facing diagnostic. Explanation only — the
    classification and quantities live in the Risk itself."""
    code = risk.code
    ctx = risk.ctx

    if code == SEM_TRUNCATION_HIGH:
        message = (f"Result can need {ctx['cap_int']} integer digits but "
                   f"{ctx['name']} holds {ctx['r_int']} — potential "
                   f"high-order truncation.")
        evidence = (f"Receiver {ctx['receiver_desc']};{ctx['origin']} "
                    f"established result bound {ctx['cap_int']} integer + "
                    f"{ctx['cap_frac']} fractional digits from the operands' "
                    f"declared PICTUREs. COBOL stores the low-order digits "
                    f"and discards the excess high-order digits without an "
                    f"ON SIZE ERROR clause.")
    elif code == SEM_PRECISION_LOSS:
        treatment = "rounded" if ctx["rounded"] else "truncated"
        message = (f"Result carries {ctx['cap_frac']} fractional digits but "
                   f"{ctx['name']} holds {ctx['r_frac']} — low-order digits "
                   f"will be {treatment}.")
        evidence = (f"Receiver {ctx['receiver_desc']};{ctx['origin']} "
                    f"established result bound {ctx['cap_int']} integer + "
                    f"{ctx['cap_frac']} fractional digits. The receiver "
                    f"stores {ctx['r_frac']} fractional digits"
                    + (", and ROUNDED is in effect" if ctx["rounded"] else
                       "; without ROUNDED COBOL truncates") + ".")
    elif code == SEM_SIGN_DISCARD:
        message = (f"{ctx['name']} is unsigned but the result can be "
                   f"negative — the sign would be discarded.")
        evidence = (f"Receiver {ctx['receiver_desc']};{ctx['origin']} at "
                    f"least one operand is signed or the operation is a "
                    f"subtraction, so a negative result is possible. "
                    f"Storing it in an unsigned item drops the sign and "
                    f"keeps the absolute digits.")
    elif code == SEM_SIZE_ERROR_GUARD:
        message = (f"{ctx['st_type']} into {ctx['name']} is guarded by ON "
                   f"SIZE ERROR.")
        evidence = (f"Receiver {ctx['receiver_desc']}; established result "
                    f"bound {ctx['cap_int']} int + {ctx['cap_frac']} frac "
                    f"digits; the statement carries an ON SIZE ERROR clause, "
                    f"so overflow takes the guarded path instead of silently "
                    f"truncating.")
    elif code == SEM_MOVE_SPACES_TO_NUMERIC:
        message = (f"MOVE SPACES to {ctx['receiver']} stores non-numeric "
                   f"characters in a numeric item.")
        evidence = (f"Source is the figurative constant SPACES; receiver "
                    f"{ctx['receiver_desc']}. The field will not contain "
                    f"valid numeric display data; later arithmetic reads it "
                    f"as invalid.")
    elif code == SEM_DIVISOR_ZERO:
        message = ("Division by the literal 0 — the program will fail at "
                   "run time if this path executes.")
        if ctx.get("mode") is not None:
            evidence = (f"DIVIDE statement at line {risk.line} uses a "
                        f"literal 0 as the divisor (mode {ctx['mode']}); "
                        f"the divisor is a constant, so every execution of "
                        f"this statement divides by zero.")
        else:
            evidence = (f"The expression divides by a constant 0 (operand "
                        f"at line {ctx['loc_line']}); every evaluation of "
                        f"this expression divides by zero.")
    else:  # pragma: no cover — every code has a renderer
        raise ValueError(f"no explanation renderer for {code}")

    return Diagnostic(
        risk.severity, code, message, risk.line, risk.col, LAYER_SEMANTIC,
        evidence=evidence, classification=risk.classification,
        detail=dict(risk.detail))


# =========================================================================
# reference collection + statement analysis
# =========================================================================

class _Refs:
    def __init__(self):
        self.rows: List[dict] = []

    def add(self, name: str, role: str, statement: str, node: dict):
        span = node.get("span") or {}
        self.rows.append({
            "name": name,
            "resolved": name.upper(),
            "role": role,
            "statement": statement,
            "line": span.get("line"),
            "col": span.get("col"),
        })

    def add_target(self, t: dict, role: str, statement: str):
        self.rows.append({
            "name": t["name"],
            "resolved": t["name"].upper(),
            "role": role,
            "statement": statement,
            "line": t["span"]["line"],
            "col": t["span"]["col"],
        })


def _receiver_risks(st_type: str, line, col, target: dict, cap: Cap,
                    rounded: bool, guarded: bool,
                    receiver: dict, risks: List[Risk],
                    origin: str = ""):
    """Capacity risks for one receiver, from established bounds only.
    `origin` names the sending operand(s) for the evidence trail."""
    if origin:
        origin = f" {origin}"

    r_int = receiver.get("integer_digits")
    r_frac = receiver.get("fractional_digits")
    if r_int is None or cap.unknown or cap.int_d is None:
        return
    name = receiver["name"]
    receiver_desc = _describe(receiver)
    detail = {
        "statement": st_type,
        "receiver": name,
        "receiver_int_digits": r_int,
        "receiver_frac_digits": r_frac,
        "bound_int_digits": cap.int_d,
        "bound_frac_digits": cap.frac_d,
        "rounded": rounded,
        "guarded": guarded,
    }
    ctx = {"name": name, "r_int": r_int, "r_frac": r_frac,
           "cap_int": cap.int_d, "cap_frac": cap.frac_d,
           "rounded": rounded, "receiver_desc": receiver_desc,
           "origin": origin, "st_type": st_type}

    if guarded:
        risks.append(Risk(SEM_SIZE_ERROR_GUARD, SEVERITY_INFO, line, col,
                          detail, dict(ctx)))
        return

    if cap.int_d > r_int:
        risks.append(Risk(SEM_TRUNCATION_HIGH, SEVERITY_WARNING, line, col,
                          detail, dict(ctx)))
    if cap.frac_d > r_frac:
        risks.append(Risk(SEM_PRECISION_LOSS, SEVERITY_WARNING, line, col,
                          detail, dict(ctx)))
    if not receiver.get("signed") and cap.signed:
        risks.append(Risk(SEM_SIGN_DISCARD, SEVERITY_WARNING, line, col,
                          detail, dict(ctx)))


def _expr_origin(node: dict, by_name: dict) -> str:
    """Short description of an expression's operands for evidence trails."""
    names: List[str] = []

    def walk(n):
        if n.get("kind") == "identifier":
            item = by_name.get(n["name"].upper())
            if item and item.get("digits") is not None:
                names.append(f"{item['name']} PIC {item.get('picture')}")
            else:
                names.append(n["name"])
        elif n.get("kind") == "literal":
            names.append(f"literal {n['text']}")
        elif n.get("kind") == "binary":
            walk(n["left"])
            walk(n["right"])
    walk(node)
    return "Operands: " + ", ".join(names) + "." if names else ""


def _analyze_statement(st: dict, by_name: dict, refs: _Refs,
                       risks: List[Risk]) -> None:
    t = st.get("type")

    if t == "Move":
        src = st["source"]
        kind = src.get("kind")
        if kind == "identifier":
            refs.add(src["name"], "sender", "MOVE", src)
        for tgt in st["targets"]:
            refs.add_target(tgt, "receiver", "MOVE")
            receiver = by_name.get(tgt["name"].upper())
            if not receiver or receiver.get("digits") is None:
                continue
            # category / capacity risks
            if kind == "figurative" and src["text"].upper() in ("SPACE", "SPACES"):
                risks.append(Risk(
                    SEM_MOVE_SPACES_TO_NUMERIC, SEVERITY_WARNING,
                    st["span"]["line"], st["span"]["col"],
                    {"statement": "MOVE", "receiver": tgt["name"]},
                    {"receiver": tgt["name"],
                     "receiver_desc": _describe(receiver)}))
            elif kind == "literal":
                cap = _literal_cap(src["text"])
                _receiver_risks("MOVE", st["span"]["line"],
                                st["span"]["col"], tgt, cap, False,
                                False, receiver, risks,
                                origin=f"Sender is the literal {src['text']}.")
            elif kind == "identifier":
                sender = by_name.get(src["name"].upper())
                if sender and sender.get("digits") is not None:
                    cap = Cap(sender["integer_digits"],
                              sender["fractional_digits"],
                              bool(sender.get("signed")))
                    _receiver_risks("MOVE", st["span"]["line"],
                                    st["span"]["col"], tgt, cap, False,
                                    False, receiver, risks,
                                    origin=f"Sender is {_describe(sender)}.")

    elif t == "Compute":
        refs.add_target(st["target"], "receiver", "COMPUTE")
        _collect_expr_refs(st["expr"], "operand", "COMPUTE", refs)
        receiver = by_name.get(st["target"]["name"].upper())
        if receiver:
            cap = expr_cap(st["expr"], by_name)
            _receiver_risks("COMPUTE", st["span"]["line"],
                            st["span"]["col"], st["target"], cap,
                            st["target"].get("rounded", False),
                            st.get("size_error", False),
                            receiver, risks,
                            origin=_expr_origin(st["expr"], by_name))
        _division_zero(st["expr"], risks, st["span"], statement="COMPUTE")

    elif t == "Add":
        for a in st["operands"]:
            if a.get("kind") == "identifier":
                refs.add(a["name"], "operand", "ADD", a)
        refs.add_target(st["target"], "receiver", "ADD")
        receiver = by_name.get(st["target"]["name"].upper())
        if receiver:
            caps = []
            for a in st["operands"]:
                caps.append(expr_cap(a, by_name))
            caps.append(expr_cap({"kind": "identifier",
                                  "name": st["target"]["name"],
                                  "span": st["target"]["span"]}, by_name))
            known = [c for c in caps if not c.unknown]
            if known and not st.get("size_error"):
                # ADD stores operand-sum + target: bound is max int + 1 carry
                int_bound = max(c.int_d for c in known) + 1
                frac_bound = max(c.frac_d for c in known)
                cap = Cap(int_bound, frac_bound,
                          any(c.signed for c in caps))
                _receiver_risks("ADD", st["span"]["line"],
                                st["span"]["col"], st["target"], cap,
                                st["target"].get("rounded", False), False,
                                receiver, risks)
            elif st.get("size_error"):
                _receiver_risks("ADD", st["span"]["line"],
                                st["span"]["col"], st["target"],
                                Cap(None, None, False, unknown=True),
                                False, True, receiver, risks)

    elif t == "Subtract":
        for a in st["subtrahends"]:
            if a.get("kind") == "identifier":
                refs.add(a["name"], "operand", "SUBTRACT", a)
        if st.get("minuend") is not None and st["minuend"].get("kind") == "identifier":
            refs.add(st["minuend"]["name"], "operand", "SUBTRACT",
                     st["minuend"])
        refs.add_target(st["target"], "receiver", "SUBTRACT")
        receiver = by_name.get(st["target"]["name"].upper())
        if receiver:
            ints, fracs, signed = [], [], False
            if st.get("minuend") is not None:
                c = expr_cap(st["minuend"], by_name)
                if not c.unknown:
                    ints.append(c.int_d)
                    fracs.append(c.frac_d)
                signed = signed or c.signed
            sub = [expr_cap(a, by_name) for a in st["subtrahends"]]
            known_sub = [c for c in sub if not c.unknown]
            if known_sub:
                # subtrahends are summed before subtraction
                ints.append(max(c.int_d for c in known_sub)
                            + (len(known_sub) - 1))
                fracs.append(max(c.frac_d for c in known_sub))
            signed = signed or any(c.signed for c in sub) or len(sub) > 0
            if ints and not st.get("size_error"):
                cap = Cap(max(ints), max(fracs), signed)
                _receiver_risks("SUBTRACT", st["span"]["line"],
                                st["span"]["col"], st["target"], cap,
                                st["target"].get("rounded", False),
                                False, receiver, risks)
            elif st.get("size_error"):
                _receiver_risks("SUBTRACT", st["span"]["line"],
                                st["span"]["col"], st["target"],
                                Cap(None, None, False, unknown=True),
                                False, True, receiver, risks)

    elif t == "Multiply":
        if st["left"].get("kind") == "identifier":
            refs.add(st["left"]["name"], "operand", "MULTIPLY", st["left"])
        if st["right"].get("kind") == "identifier":
            refs.add(st["right"]["name"], "operand", "MULTIPLY", st["right"])
        refs.add_target(st["target"], "receiver", "MULTIPLY")
        receiver = by_name.get(st["target"]["name"].upper())
        if receiver:
            lc = expr_cap(st["left"], by_name)
            rc = expr_cap(st["right"], by_name)
            if not lc.unknown and not rc.unknown:
                cap = Cap(lc.int_d + rc.int_d, lc.frac_d + rc.frac_d,
                          lc.signed or rc.signed)
                _receiver_risks("MULTIPLY", st["span"]["line"],
                                st["span"]["col"], st["target"], cap,
                                st["target"].get("rounded", False),
                                st.get("size_error", False),
                                receiver, risks)
            elif st.get("size_error"):
                _receiver_risks("MULTIPLY", st["span"]["line"],
                                st["span"]["col"], st["target"],
                                Cap(None, None, False, unknown=True),
                                False, True, receiver, risks)

    elif t == "Divide":
        if st["first"].get("kind") == "identifier":
            refs.add(st["first"]["name"], "operand", "DIVIDE", st["first"])
        if st["second"].get("kind") == "identifier":
            refs.add(st["second"]["name"], "operand", "DIVIDE", st["second"])
        refs.add_target(st["target"], "receiver", "DIVIDE")
        divisor = st["second"] if st["mode"] == "BY" else st["first"]
        if divisor.get("kind") == "literal" and _is_zero_literal(divisor):
            risks.append(Risk(
                SEM_DIVISOR_ZERO, SEVERITY_ERROR,
                st["span"]["line"], st["span"]["col"],
                {"statement": "DIVIDE", "mode": st["mode"],
                 "divisor_literal": "0"},
                {"mode": st["mode"]}))
        # quotient precision is not established statically: no truncation
        # claims for DIVIDE receivers (no invented semantics)

    elif t == "If":
        if st["condition"]["left"].get("kind") == "identifier":
            refs.add(st["condition"]["left"]["name"], "operand", "IF",
                     st["condition"]["left"])
        if st["condition"]["right"].get("kind") == "identifier":
            refs.add(st["condition"]["right"]["name"], "operand", "IF",
                     st["condition"]["right"])


def _collect_expr_refs(node: dict, role: str, statement: str,
                       refs: _Refs) -> None:
    if node.get("kind") == "identifier":
        refs.add(node["name"], role, statement, node)
    elif node.get("kind") == "binary":
        _collect_expr_refs(node["left"], role, statement, refs)
        _collect_expr_refs(node["right"], role, statement, refs)


def _division_zero(node: dict, risks: List[Risk],
                   st_span: dict | None = None, statement: str = "COMPUTE"):
    if node.get("kind") == "binary" and node["op"] == "/":
        if _is_zero_literal(node["right"]):
            # locate at the literal divisor when its span exists, else the
            # enclosing statement
            loc = node["right"].get("span") or st_span or {}
            risks.append(Risk(
                SEM_DIVISOR_ZERO, SEVERITY_ERROR,
                loc.get("line"), loc.get("col"),
                {"statement": statement, "mode": None,
                 "divisor_literal": "0"},
                {"loc_line": loc.get("line")}))
        _division_zero(node["left"], risks, st_span, statement)
        _division_zero(node["right"], risks, st_span, statement)


def _walk_statements(stmts: List[dict], by_name: dict, refs: _Refs,
                     risks: List[Risk]) -> None:
    for st in stmts:
        _analyze_statement(st, by_name, refs, risks)
        if st.get("type") == "If":
            _walk_statements(st.get("then") or [], by_name, refs, risks)
            _walk_statements(st.get("else") or [], by_name, refs, risks)


def _count_statements(stmts: List[dict]) -> int:
    n = 0
    for st in stmts:
        n += 1
        if st.get("type") == "If":
            n += _count_statements(st.get("then") or [])
            n += _count_statements(st.get("else") or [])
    return n


# =========================================================================
# entry point
# =========================================================================

def analyze(ast: dict) -> tuple[dict, List[Diagnostic]]:
    """Run semantic analysis over a clean AST (layers 1–4 produced no
    errors). Returns (semantic products, diagnostics)."""
    symbols_json = ast.get("symbols", {})
    dictionary = _dictionary(symbols_json)
    by_name = {e["name"].upper(): e for e in _flatten_dict(dictionary)}

    refs = _Refs()
    # USING parameters reference their linkage records
    proc = ast.get("procedure_division", {})
    for pname in proc.get("using", []) or []:
        refs.rows.append({
            "name": pname,
            "resolved": pname.upper(),
            "role": "parameter",
            "statement": "USING",
            "line": proc.get("span", {}).get("line"),
            "col": proc.get("span", {}).get("col"),
        })

    risks: List[Risk] = []
    sentences = proc.get("sentences", []) or []
    for sentence in sentences:
        _walk_statements(sentence.get("statements", []), by_name, refs, risks)

    # classification counts + coverage: what was analyzed, what needs a human
    findings = {CLASS_VIOLATION: 0, CLASS_RISK: 0, CLASS_NOTE: 0}
    for r in risks:
        findings[r.classification] += 1
    statements_total = sum(_count_statements(s.get("statements", []))
                           for s in sentences)
    coverage = {
        "statements_total": statements_total,
        "statements_analyzed": statements_total,  # full coverage of the
        # parsed subset by construction; if a future limit skips statements,
        # this field is where the gap becomes visible
        "findings": findings,
        "needs_human_review": findings[CLASS_RISK],
    }

    products = {
        "symbols": dictionary,
        "references": refs.rows,
        "counts": {
            "data_items": len(_flatten_dict(dictionary)),
            "references": len(refs.rows),
            "declared_identifiers": len(by_name),
        },
        "coverage": coverage,
        "assumptions": ASSUMPTIONS,
    }
    return products, [explain(r) for r in risks]
