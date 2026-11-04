"""Layer 4 — AST semantic analysis. Rev5 §2.2 Layer 4 (frozen rules).

- symbol table over WS + LINKAGE (case-insensitive duplicates -> ERR_DUPLICATE_SYMBOL)
- level-number hierarchy (01/77 roots; 02-49 nest under the nearest smaller level)
- group items (no PIC) propagate USAGE; groups are never statement operands
  (ERR_NON_ELEMENTARY_TARGET)
- elementary items require PIC (ERR_PIC_REQUIRED [EXT]) with 1 <= I+F <= 18
  (ERR_PIC_DIGIT_LIMIT)
- signed DISPLAY requires SIGN SEPARATE (ERR_OVERPUNCH_UNSUPPORTED);
  COMP-3 rejects SIGN SEPARATE (ERR_SIGN_CLAUSE_UNSUPPORTED [EXT])
- every PROCEDURE USING name resolves to a distinct LINKAGE 01/77 entry
- every identifier referenced in the procedure exists (ERR_UNDECLARED_IDENT)
"""
import re
from typing import List, Optional
from .diagnostics import (Diagnostic, err, ERR_DUPLICATE_SYMBOL,
                          ERR_PIC_DIGIT_LIMIT, ERR_OVERPUNCH_UNSUPPORTED,
                          ERR_SIGN_CLAUSE_UNSUPPORTED, ERR_PIC_REQUIRED,
                          ERR_UNDECLARED_IDENT, ERR_NON_ELEMENTARY_TARGET,
                          ERR_LEVEL_STRUCTURE, LAYER_AST)

# PIC digit run: one or more of '9' or '9(n)'
_RUN = r"(?:9(?:\(\d+\))?)+"
PIC_INT_MIXED_RE = re.compile(r"^(S?)(%s)(V(%s))?$" % (_RUN, _RUN))
PIC_FRAC_ONLY_RE = re.compile(r"^(S?)V(%s)$" % _RUN)


def _run_digits(run: str) -> int:
    total = 0
    for m in re.finditer(r"9(?:\((\d+)\))?", run):
        total += int(m.group(1)) if m.group(1) else 1
    return total


def expand_pic(pic: str) -> Optional[dict]:
    """'S9(5)V99' -> {signed, int_digits, frac_digits}; None if malformed.
    Forms (corpus pic_str): [S] 9-run [V 9-run]  |  [S] V 9-run."""
    p = pic.upper()
    if not p:
        return None
    m = PIC_FRAC_ONLY_RE.match(p)
    if m:
        f = _run_digits(m.group(2))
        if f <= 0:
            return None
        return {"signed": m.group(1) == "S", "int_digits": 0, "frac_digits": f}
    m = PIC_INT_MIXED_RE.match(p)
    if m:
        i = _run_digits(m.group(2))
        f = _run_digits(m.group(4)) if m.group(3) else 0
        if i <= 0:
            return None
        return {"signed": m.group(1) == "S", "int_digits": i, "frac_digits": f}
    return None


class Item:
    __slots__ = ("name", "level", "line", "col", "pic", "usage", "sign",
                 "value", "children", "parent", "section", "expanded",
                 "elementary")

    def __init__(self, entry: dict, section: str):
        self.name = entry["name"]
        self.level = entry["level"]
        self.line, self.col = entry["line"], entry["col"]
        self.pic = entry.get("pic")
        self.usage = (entry.get("usage") or {}).get("usage")
        self.sign = entry.get("sign")
        self.value = entry.get("value")
        self.children: List["Item"] = []
        self.parent: Optional["Item"] = None
        self.section = section
        self.expanded: Optional[dict] = None
        self.elementary = False


def _build_hierarchy(entries: List[dict], section: str, diags: List[Diagnostic]) -> List[Item]:
    roots: List[Item] = []
    stack: List[Item] = []
    for e in entries:
        item = Item(e, section)
        while stack and stack[-1].level >= item.level:
            stack.pop()
        if item.level == 1 or item.level == 77:
            stack.clear()
            roots.append(item)
        elif stack:
            item.parent = stack[-1]
            stack[-1].children.append(item)
        else:
            diags.append(err(ERR_LEVEL_STRUCTURE,
                             f"Item {item.name} (level {item.level}) has no parent group.",
                             LAYER_AST, item.line, item.col))
        stack.append(item)
    return roots


def _finalize(items: List[Item], inherited_usage: Optional[str],
              diags: List[Diagnostic]) -> None:
    for it in items:
        usage = it.usage or inherited_usage
        if it.children:
            # group item: PIC/SIGN/VALUE are grammar-rejected upstream; it
            # propagates its (possibly inherited) usage to children
            if it.pic:
                diags.append(err(ERR_NON_ELEMENTARY_TARGET,
                                 f"Group item {it.name} cannot carry a PICTURE.",
                                 LAYER_AST, it.line, it.col))
            it.elementary = False
            _finalize(it.children, usage, diags)
        else:
            it.elementary = True
            if not it.pic:
                diags.append(err(ERR_PIC_REQUIRED,
                                 f"Elementary item {it.name} requires a PIC clause.",
                                 LAYER_AST, it.line, it.col))
            else:
                exp = expand_pic(it.pic["picture"])
                if exp is None:
                    diags.append(err(ERR_PIC_DIGIT_LIMIT,
                                     f"Malformed PICTURE {it.pic['picture']!r} on {it.name}.",
                                     LAYER_AST, it.pic["line"], it.pic["col"]))
                else:
                    it.expanded = exp
                    total = exp["int_digits"] + exp["frac_digits"]
                    if not (1 <= total <= 18):
                        diags.append(err(
                            ERR_PIC_DIGIT_LIMIT,
                            f"{it.name}: PICTURE {it.pic['picture']} expands to {total} digits; the limit is 18.",
                            LAYER_AST, it.pic["line"], it.pic["col"]))
                    if exp["signed"] and usage in (None, "display") and not it.sign:
                        diags.append(err(
                            ERR_OVERPUNCH_UNSUPPORTED,
                            f"{it.name}: signed DISPLAY requires SIGN IS LEADING/TRAILING SEPARATE.",
                            LAYER_AST, it.line, it.col))
            if usage == "comp3" and it.sign:
                diags.append(err(
                    ERR_SIGN_CLAUSE_UNSUPPORTED,
                    f"{it.name}: COMP-3 items do not take a SIGN SEPARATE clause.",
                    LAYER_AST, it.line, it.col))


def _flatten(items: List[Item]) -> List[Item]:
    out: List[Item] = []
    for it in items:
        out.append(it)
        out.extend(_flatten(it.children))
    return out


class Symbols:
    def __init__(self):
        self.by_name: dict = {}

    def add(self, item: Item, diags: List[Diagnostic]) -> None:
        key = item.name.upper()
        if key in self.by_name:
            first = self.by_name[key]
            diags.append(err(
                ERR_DUPLICATE_SYMBOL,
                f"Data-item name {item.name} duplicates {first.name} ({first.section}).",
                LAYER_AST, item.line, item.col))
        else:
            self.by_name[key] = item

    def lookup(self, name: str) -> Optional[Item]:
        return self.by_name.get(name.upper())


def _walk(node, diags: List[Diagnostic], symbols: Symbols) -> None:
    if isinstance(node, dict):
        if node.get("kind") in ("identifier",):
            item = symbols.lookup(node["name"])
            if item is None:
                diags.append(err(ERR_UNDECLARED_IDENT,
                                 f"{node['name']} is not declared in the Data Division.",
                                 LAYER_AST,
                                 node.get("span", {}).get("line"),
                                 node.get("span", {}).get("col")))
            elif not item.elementary:
                diags.append(err(ERR_NON_ELEMENTARY_TARGET,
                                 f"{node['name']} is a group item; statements operate on elementary items.",
                                 LAYER_AST,
                                 node.get("span", {}).get("line"),
                                 node.get("span", {}).get("col")))
            node["resolved"] = item.name if item else None
        for v in node.values():
            _walk(v, diags, symbols)
    elif isinstance(node, list):
        for v in node:
            _walk(v, diags, symbols)


def _check_target(name: str, span: dict, symbols: Symbols, diags: List[Diagnostic],
                  what: str) -> None:
    item = symbols.lookup(name)
    if item is None:
        diags.append(err(ERR_UNDECLARED_IDENT,
                         f"{name} is not declared in the Data Division.",
                         LAYER_AST, span.get("line"), span.get("col")))
    elif not item.elementary:
        diags.append(err(ERR_NON_ELEMENTARY_TARGET,
                         f"{what} {name} is a group item; statements operate on elementary items.",
                         LAYER_AST, span.get("line"), span.get("col")))


def _walk_statements(stmts: List[dict], symbols: Symbols, diags: List[Diagnostic]) -> None:
    for st in stmts:
        t = st.get("type")
        if t == "Move":
            _walk(st["source"], diags, symbols)
            for tgt in st["targets"]:
                _check_target(tgt["name"], tgt["span"], symbols, diags, "MOVE target")
        elif t == "Compute":
            _check_target(st["target"]["name"], st["target"]["span"], symbols, diags,
                          "COMPUTE target")
            _walk(st["expr"], diags, symbols)
        elif t == "Add":
            for a in st["operands"]:
                _walk(a, diags, symbols)
            _check_target(st["target"]["name"], st["target"]["span"], symbols, diags,
                          "ADD target")
        elif t == "Subtract":
            for a in st["subtrahends"]:
                _walk(a, diags, symbols)
            if st["form"] == "giving":
                _walk(st["minuend"], diags, symbols)
            _check_target(st["target"]["name"], st["target"]["span"], symbols, diags,
                          "SUBTRACT target")
        elif t == "Multiply":
            _walk(st["left"], diags, symbols)
            _walk(st["right"], diags, symbols)
            _check_target(st["target"]["name"], st["target"]["span"], symbols, diags,
                          "MULTIPLY target")
        elif t == "Divide":
            _walk(st["first"], diags, symbols)
            _walk(st["second"], diags, symbols)
            _check_target(st["target"]["name"], st["target"]["span"], symbols, diags,
                          "DIVIDE target")
        elif t == "If":
            _walk(st["condition"]["left"], diags, symbols)
            _walk(st["condition"]["right"], diags, symbols)
            _walk_statements(st["then"], symbols, diags)
            _walk_statements(st["else"], symbols, diags)
        elif t == "Goback":
            pass


def analyze_ast(ast: dict, diags: List[Diagnostic]) -> tuple[dict, Symbols]:
    dd = ast["data_division"]
    ws_roots = _build_hierarchy(dd["working_storage"]["entries"] if dd["working_storage"] else [],
                                "WORKING-STORAGE", diags)
    lk_roots = _build_hierarchy(dd["linkage"]["entries"], "LINKAGE", diags)
    _finalize(ws_roots, None, diags)
    _finalize(lk_roots, None, diags)

    symbols = Symbols()
    for it in _flatten(ws_roots) + _flatten(lk_roots):
        symbols.add(it, diags)

    pd = ast["procedure_division"]
    using_items = []
    seen = set()
    for name in pd["using"]:
        item = symbols.lookup(name)
        if item is None or item.section != "LINKAGE" or item.level not in (1, 77):
            diags.append(err(ERR_UNDECLARED_IDENT,
                             f"USING name {name} does not resolve to a distinct LINKAGE 01/77 entry.",
                             LAYER_AST, pd["span"]["line"], pd["span"]["col"]))
        else:
            key = item.name.upper()
            if key in seen:
                diags.append(err(ERR_DUPLICATE_SYMBOL,
                                 f"USING lists {name} more than once.",
                                 LAYER_AST, pd["span"]["line"], pd["span"]["col"]))
            seen.add(key)
            using_items.append(item.name)

    for sentence in pd["sentences"]:
        _walk_statements(sentence["statements"], symbols, diags)

    ast["symbols"] = {
        "using_resolved": using_items,
        "working_storage": [_item_json(i) for i in ws_roots],
        "linkage": [_item_json(i) for i in lk_roots],
    }
    return ast, symbols


def _item_json(it: Item) -> dict:
    node = {
        "name": it.name, "level": it.level, "section": it.section,
        "line": it.line, "col": it.col, "usage": it.usage,
        "elementary": it.elementary,
    }
    if it.pic:
        node["picture"] = it.pic["picture"]
    if it.expanded:
        node["expanded"] = it.expanded
    if it.sign:
        node["sign"] = "LEADING" if it.sign["leading"] else "TRAILING"
    if it.value:
        node["value"] = it.value["value"]
    if it.children:
        node["children"] = [_item_json(c) for c in it.children]
    return node
