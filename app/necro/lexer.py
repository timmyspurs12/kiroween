"""Layer 2 — Lexical (columns 8-72 of non-comment lines). Rev4 §2.2.2.

Comment lines (indicator '*' or '/') are skipped entirely. Token classes:
  LEVEL    ^0[1-9]$ | ^[1-4][0-9]$ | ^77$          (66/88 excluded)
  NUMBER   SIGNED_DEC_LIT / POS_INT shapes
  KEYWORD  well-formed word whose uppercase is in RESERVED_WORDS
  IDENT    USER_IDENT shape, not reserved
  PUNCT    . ( ) = + - * / < > <= >= <>
Malformed words -> ERR_LEX_INVALID_WORD at the word's start column.
"""
import re
from typing import List, Optional
from .diagnostics import (Diagnostic, err, ERR_LEX_INVALID_WORD,
                          LAYER_LEXICAL)

RESERVED_WORDS = {
    # (a) NVS-0 grammar keywords
    "IDENTIFICATION", "DIVISION", "PROGRAM-ID", "IS", "INITIAL", "DATA",
    "WORKING-STORAGE", "SECTION", "PIC", "PICTURE", "USAGE", "COMP-3",
    "PACKED-DECIMAL", "DISPLAY", "SIGN", "LEADING", "TRAILING", "SEPARATE",
    "CHARACTER", "VALUE", "PROCEDURE", "USING", "MOVE", "TO", "COMPUTE",
    "ROUNDED", "ON", "NOT", "SIZE", "ERROR", "END-COMPUTE", "ADD", "GIVING",
    "END-ADD", "SUBTRACT", "FROM", "END-SUBTRACT", "MULTIPLY", "BY",
    "END-MULTIPLY", "DIVIDE", "INTO", "END-DIVIDE", "IF", "THEN", "ELSE",
    "END-IF", "GOBACK",
    # (b) banned COBOL keywords
    "STOP", "RUN", "CALL", "COPY", "REPLACE", "REDEFINES", "RENAMES",
    "OCCURS", "DEPENDING", "EXTERNAL", "GLOBAL", "SYNCHRONIZED", "SYNC",
    "JUSTIFIED", "BLANK", "POINTER", "COMP", "COMP-1", "COMP-2", "COMP-4",
    "COMP-5", "BINARY", "GO", "PERFORM", "THRU", "THROUGH", "EVALUATE",
    "WHEN", "ACCEPT", "OPEN", "READ", "WRITE", "CLOSE", "EXEC", "EXIT",
    "ALTER",
    # (c) special registers & figurative constants
    "RETURN-CODE", "TALLY", "SORT-RETURN", "WHEN-COMPILED", "LINAGE-COUNTER",
    "SHIFT-IN", "SHIFT-OUT", "DEBUG-ITEM", "ADDRESS", "LENGTH", "FUNCTION",
    "ZERO", "ZEROS", "ZEROES", "SPACE", "SPACES", "HIGH-VALUE",
    "HIGH-VALUES", "LOW-VALUE", "LOW-VALUES", "QUOTE", "QUOTES", "NULL",
    "NULLS",
}

# Figurative constants usable as operand literals (subset of RESERVED_WORDS).
FIGURATIVE_CONSTANTS = {
    "ZERO", "ZEROS", "ZEROES", "SPACE", "SPACES", "HIGH-VALUE",
    "HIGH-VALUES", "LOW-VALUE", "LOW-VALUES", "QUOTE", "QUOTES",
    "NULL", "NULLS",
}

# Grammar literal strings from the Rev4 §2.2.2 EBNF that are not members of
# RESERVED_WORDS. In the corpus's Lark grammar these are anonymous literals
# with priority over USER_IDENT; LINKAGE is the one such literal.
GRAMMAR_LITERALS = {"LINKAGE"}

WORD_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{0,29}$")
LEVEL_RE = re.compile(r"^(0[1-9]|[1-4][0-9]|77)$")
SIGNED_DEC_RE = re.compile(r"^[+-]?([0-9]+(\.[0-9]+)?|\.[0-9]+)$")
POS_INT_RE = re.compile(r"^[1-9][0-9]*$")

PUNCT2 = ("<=", ">=", "<>")
PUNCT1 = tuple("().=+-*/<>")

# token types
T_LEVEL = "LEVEL"
T_NUMBER = "NUMBER"
T_KEYWORD = "KEYWORD"
T_IDENT = "IDENT"
T_PUNCT = "PUNCT"


class Token:
    __slots__ = ("type", "text", "line", "col")

    def __init__(self, ttype: str, text: str, line: int, col: int):
        self.type, self.text, self.line, self.col = ttype, text, line, col

    def upper(self) -> str:
        return self.text.upper()

    def to_json(self) -> dict:
        return {"type": self.type, "text": self.text,
                "line": self.line, "col": self.col}


def _classical_word(raw: str, line: int, col: int, diags: List[Diagnostic]) -> Optional[Token]:
    """Classify an identifier-shaped word; emit ERR_LEX_INVALID_WORD if malformed."""
    if WORD_RE.match(raw) and not raw.endswith("-"):
        upper = raw.upper()
        if upper in RESERVED_WORDS or upper in GRAMMAR_LITERALS:
            return Token(T_KEYWORD, upper, line, col)
        return Token(T_IDENT, raw, line, col)
    if raw.endswith("-"):
        why = "trailing hyphen"
    elif len(raw) > 30:
        why = "longer than 30 characters"
    elif not raw[0].isalpha():
        why = "does not start with a letter"
    elif any(ch < " " for ch in raw):
        why = "contains a control character"
    else:
        why = "invalid character sequence"
    diags.append(err(ERR_LEX_INVALID_WORD,
                     f"Invalid user-defined word {raw!r} ({why}).",
                     LAYER_LEXICAL, line, col))
    return None


def tokenize(lines: List[str]) -> tuple[List[Token], List[Diagnostic]]:
    tokens: List[Token] = []
    diags: List[Diagnostic] = []

    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        if len(line) >= 7 and line[6] in ("*", "/"):
            continue  # comment line: skipped at the lexical layer
        content = line[7:72] if len(line) > 7 else ""
        i, n = 0, len(content)
        while i < n:
            ch = content[i]
            if ch == " ":
                i += 1
                continue
            col = 8 + i  # 1-based file column
            if ch.isalpha():
                j = i
                while j < n and (content[j].isalnum() or content[j] == "-"):
                    j += 1
                tok = _classical_word(content[i:j], line_no, col, diags)
                if tok:
                    tokens.append(tok)
                i = j
                continue
            if ch.isdigit() or (ch in "+-." and i + 1 < n and
                                (content[i + 1].isdigit() or content[i + 1] == "." and ch in "+-")):
                j = i
                if ch in "+-":
                    j += 1
                digits = False
                while j < n and content[j].isdigit():
                    j += 1
                    digits = True
                # a '.' is a decimal point only when a digit follows;
                # otherwise it is the sentence-ending period
                if j < n and content[j] == "." and j + 1 < n and content[j + 1].isdigit():
                    j += 1
                    while j < n and content[j].isdigit():
                        j += 1
                raw = content[i:j]
                if digits and SIGNED_DEC_RE.match(raw):
                    if LEVEL_RE.match(raw):
                        tokens.append(Token(T_LEVEL, raw, line_no, col))
                    else:
                        tokens.append(Token(T_NUMBER, raw, line_no, col))
                else:
                    diags.append(err(ERR_LEX_INVALID_WORD,
                                     f"Invalid numeric literal {raw!r}.",
                                     LAYER_LEXICAL, line_no, col))
                    i = j
                    continue
                # a number immediately followed by letter/hyphen is malformed
                if j < n and (content[j].isalpha() or content[j] == "-"):
                    diags.append(err(ERR_LEX_INVALID_WORD,
                                     f"Invalid word {content[i:j+1]!r} (cannot mix digits and letters).",
                                     LAYER_LEXICAL, line_no, col))
                    i = j + 1
                    continue
                i = j
                continue
            two = content[i:i + 2]
            if two in PUNCT2:
                tokens.append(Token(T_PUNCT, two, line_no, col))
                i += 2
                continue
            if ch in PUNCT1:
                tokens.append(Token(T_PUNCT, ch, line_no, col))
                i += 1
                continue
            diags.append(err(ERR_LEX_INVALID_WORD,
                             f"Unexpected character {ch!r}.",
                             LAYER_LEXICAL, line_no, col))
            i += 1

    return tokens, diags
