#!/usr/bin/env python3
"""Generate app/necro/fixtures.py from spike_evidence/spec/rev4_extract.md.

Positive fixtures #1-#12 (§3.1) and negative fixtures #13-#18 (§3.2) are
extracted VERBATIM from the published code fences. Five additional
engineered negatives are appended, marked [EXT] (agent extensions, not from
the corpus). The generator records per-fixture provenance.
"""
import re
import sys

EXTRACT = "spike_evidence/spec/rev4_extract.md"
OUT = "app/necro/fixtures.py"

text = open(EXTRACT, encoding="utf-8").read()

# --- parse ```cobol fences with a "#N:" header comment -------------------
blocks = []
for m in re.finditer(r"```cobol\n(.*?)```", text, re.S):
    body = m.group(1)
    hdr = re.match(r"\s*\*\s*=== #(\d+): (\S+?\.cbl) \((.*?)\) ===", body)
    if hdr:
        blocks.append({
            "num": int(hdr.group(1)),
            "filename": hdr.group(2),
            "note": hdr.group(3),
            "source": body.rstrip("\n"),
        })
nums = {b["num"] for b in blocks}
assert set(range(1, 19)) <= nums, f"missing fixtures: {sorted(set(range(1,19)) - nums)}"
blocks.sort(key=lambda b: b["num"])

# section provenance: 1-12 §3.1 positive, 13-18 §3.2 negative
POS_DESC = {
    1: "Fee product: COMP-3 receivers, multiply into S9(5)V99.",
    2: "ROUNDED multiply into S9(4)V9.",
    3: "Division then multiply, integer notional (S9(5)).",
    4: "Division then multiply, fractional notional (S9(5)V99).",
    5: "Unsigned/signed receivers; SIZE ERROR with END-COMPUTE.",
    6: "Three distinct 01 linkage parameters; ADD GIVING.",
    7: "Hyphenated PROGRAM-ID (CALC-FEE).",
    8: "COMP-3 plus integer literal in COMPUTE.",
    9: "Non-INITIAL state: ADD TO working-storage accumulators.",
    10: "IS INITIAL program attribute; same accumulators.",
    11: "Two distinct 01 params; MOVE between them.",
    12: "SIGN IS LEADING/TRAILING SEPARATE DISPLAY items; IF/ELSE.",
}
NEG_DESC = {
    13: "Reserved words RETURN-CODE and STOP outside the subset.",
    14: "Reserved word CALL outside the subset.",
    15: "Preflight: content past column 72 (line 4, col 73).",
    16: "Preflight: '-' in the indicator area is not space/* (line 6, col 7).",
    17: "AST: PICTURE S9(10)V9(9) expands to 19 digits (limit 18).",
    18: "Grammar: size-error COMPUTE without mandatory END-COMPUTE.",
}

EXT_NEGATIVES = [
    {
        "id": "EXT-TAB",
        "filename": "EXT_TAB.cbl",
        "description": "Preflight: TAB character in the source (not allowed in fixed format).",
        "source": (
            "       IDENTIFICATION DIVISION.\n"
            "\t   PROGRAM-ID. EXTTAB.\n"
            "       DATA DIVISION.\n"
            "       LINKAGE SECTION.\n"
            "       01  LK-DUMMY         PIC 9.\n"
            "       PROCEDURE DIVISION USING LK-DUMMY.\n"
            "           GOBACK.\n"
        ).rstrip("\n"),
        "expect_layer": "Preflight",
    },
    {
        "id": "EXT-NOENDIF",
        "filename": "EXT_NOENDIF.cbl",
        "description": "Grammar: IF without the mandatory END-IF terminator.",
        "source": (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. EXTNOENDIF.\n"
            "       DATA DIVISION.\n"
            "       LINKAGE SECTION.\n"
            "       01  LK-IO.\n"
            "           05  LK-A         PIC S9(5)V99  COMP-3.\n"
            "           05  LK-B         PIC S9(5)V99  COMP-3.\n"
            "       PROCEDURE DIVISION USING LK-IO.\n"
            "           IF LK-A < LK-B\n"
            "               MOVE LK-B TO LK-A\n"
            "           GOBACK.\n"
        ).rstrip("\n"),
        "expect_layer": "Grammar",
    },
    {
        "id": "EXT-DUPSYM",
        "filename": "EXT_DUPSYM.cbl",
        "description": "AST: duplicate data name LK-AMOUNT declared twice (case-insensitive).",
        "source": (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. EXTDUPSYM.\n"
            "       DATA DIVISION.\n"
            "       LINKAGE SECTION.\n"
            "       01  LK-IO.\n"
            "           05  LK-AMOUNT    PIC S9(5)V99  COMP-3.\n"
            "           05  LK-amount    PIC S9(5)V99  COMP-3.\n"
            "       PROCEDURE DIVISION USING LK-IO.\n"
            "           COMPUTE LK-AMOUNT = LK-AMOUNT + 1\n"
            "           GOBACK.\n"
        ).rstrip("\n"),
        "expect_layer": "AST",
    },
    {
        "id": "EXT-UNDECL",
        "filename": "EXT_UNDECL.cbl",
        "description": "AST: undeclared identifier LK-MISSING referenced in COMPUTE.",
        "source": (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. EXTUNDECL.\n"
            "       DATA DIVISION.\n"
            "       LINKAGE SECTION.\n"
            "       01  LK-IO.\n"
            "           05  LK-AMOUNT    PIC S9(5)V99  COMP-3.\n"
            "       PROCEDURE DIVISION USING LK-IO.\n"
            "           COMPUTE LK-AMOUNT = LK-MISSING + 1\n"
            "           GOBACK.\n"
        ).rstrip("\n"),
        "expect_layer": "AST",
    },
    {
        "id": "EXT-GROUPTGT",
        "filename": "EXT_GROUPTGT.cbl",
        "description": "AST: group item LK-IO used as a COMPUTE receiver (groups are never operands).",
        "source": (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. EXTGROUPTGT.\n"
            "       DATA DIVISION.\n"
            "       LINKAGE SECTION.\n"
            "       01  LK-IO.\n"
            "           05  LK-AMOUNT    PIC S9(5)V99  COMP-3.\n"
            "       PROCEDURE DIVISION USING LK-IO.\n"
            "           COMPUTE LK-IO = 1\n"
            "           GOBACK.\n"
        ).rstrip("\n"),
        "expect_layer": "AST",
    },
]


def pystr(s: str) -> str:
    """Quote a fixture source verbatim as a Python string literal."""
    # keep exact bytes; use repr-style with explicit escapes for backslash/quote
    return repr(s)


lines = []
A = lines.append
A('"""NecroSpec curated sample corpus.')
A('')
A('Positive fixtures #1-#12 (rev4_extract.md §3.1) and negative fixtures')
A('#13-#18 (§3.2) are VERBATIM transcripts from the published')
A('TRANSCRIPT-DERIVED USER-ATTESTED BASELINE (see spike_evidence/spec/).')
A('They are not authenticated originals. Fixtures with id EXT-* are agent-')
A('engineered extensions, marked [EXT]; they are not part of the corpus.')
A('')
A('Generated by tools/gen_fixtures.py - regenerate rather than hand-edit.')
A('"""')
A('')
A('SAMPLES = [')
for b in blocks:
    n = b["num"]
    pos = n <= 12
    A("    {")
    A(f'        "id": "{b["filename"].rsplit(".", 1)[0]}",')
    A(f'        "filename": {b["filename"]!r},')
    A(f'        "title": "Fixture #{n}: {b["filename"]}",')
    A(f'        "origin": "rev4_extract.md §{"3.1" if pos else "3.2"} #{n} '
      f'({"positive" if pos else "negative"}) — verbatim transcript",')
    A(f'        "description": {(POS_DESC[n] if pos else NEG_DESC[n])!r},')
    A(f'        "note": {b["note"]!r},')
    A(f'        "expect_ok": {str(pos)},')
    A(f'        "source": {pystr(b["source"])},')
    A("    },")
for e in EXT_NEGATIVES:
    A("    {")
    A(f'        "id": {e["id"]!r},')
    A(f'        "filename": {e["filename"]!r},')
    A(f'        "title": "[EXT] {e["filename"]}",')
    A('        "origin": "[EXT] agent-engineered extension — not part of the corpus",')
    A(f'        "description": {e["description"]!r},')
    A('        "note": "engineered",')
    A('        "expect_ok": False,')
    A(f'        "source": {pystr(e["source"])},')
    A("    },")
A(']')
A('')
A('SAMPLES_BY_ID = {s["id"]: s for s in SAMPLES}')
A('')
A('POSITIVE_SAMPLES = [s for s in SAMPLES if s["expect_ok"]]')
A('NEGATIVE_SAMPLES = [s for s in SAMPLES if not s["expect_ok"]]')

open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print(f"wrote {OUT}: {len(blocks)} corpus + {len(EXT_NEGATIVES)} [EXT] fixtures")
