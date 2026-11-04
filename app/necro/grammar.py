"""Layer 3 — Grammar (recursive descent over the frozen Rev4 §2.2.2 EBNF).

The corpus grammar is LALR(1) with zero conflicts; this hand-written parser
accepts exactly that language and produces the same rejections (reserved
words where USER_IDENT is required, mandatory END-* terminators on
size-error forms, sentence periods).
"""
from typing import List, Optional
from .lexer import (Token, T_KEYWORD, T_IDENT, T_LEVEL,
                    T_NUMBER, T_PUNCT, FIGURATIVE_CONSTANTS)
from .diagnostics import (Diagnostic, err, ERR_GRAMMAR_UNEXPECTED_TOKEN,
                          ERR_GRAMMAR_MISSING_TERMINATOR,
                          ERR_GRAMMAR_MISSING_PERIOD, ERR_GRAMMAR_INCOMPLETE,
                          LAYER_GRAMMAR)

STATEMENT_KEYWORDS = {"MOVE", "COMPUTE", "ADD", "SUBTRACT", "MULTIPLY",
                      "DIVIDE", "GOBACK", "IF"}
CONDITION_OPS = {"=", "<>", "<", "<=", ">", ">="}
DIVISION_HEADS = {"IDENTIFICATION", "DATA", "PROCEDURE"}
SECTION_HEADS = {"WORKING-STORAGE", "LINKAGE", "PROCEDURE"}


class GrammarError(Exception):
    def __init__(self, diag: Diagnostic):
        self.diag = diag
        super().__init__(diag.message)


class Parser:
    def __init__(self, tokens: List[Token]):
        self.toks = tokens
        self.i = 0
        self.ast: dict = {}

    # ---- token helpers -------------------------------------------------
    def peek(self, off: int = 0) -> Optional[Token]:
        j = self.i + off
        return self.toks[j] if j < len(self.toks) else None

    def next(self) -> Optional[Token]:
        t = self.peek()
        if t:
            self.i += 1
        return t

    def at_kw(self, *names: str) -> bool:
        t = self.peek()
        return bool(t and t.type == T_KEYWORD and t.text in names)

    def at_punct(self, ch: str) -> bool:
        t = self.peek()
        return bool(t and t.type == T_PUNCT and t.text == ch)

    def expect_kw(self, name: str, what: str) -> Token:
        if self.at_kw(name):
            return self.next()
        t = self.peek()
        got = f"{t.type} {t.text!r}" if t else "end of source"
        raise GrammarError(err(
            ERR_GRAMMAR_UNEXPECTED_TOKEN,
            f"Expected {what} ('{name}'), found {got}.",
            LAYER_GRAMMAR, t.line if t else None, t.col if t else None))
        # unreachable

    def expect_punct(self, ch: str, what: str) -> Token:
        if self.at_punct(ch):
            return self.next()
        t = self.peek()
        got = f"{t.type} {t.text!r}" if t else "end of source"
        raise GrammarError(err(
            ERR_GRAMMAR_UNEXPECTED_TOKEN,
            f"Expected {what} ('{ch}'), found {got}.",
            LAYER_GRAMMAR, t.line if t else None, t.col if t else None))

    def expect_ident(self, what: str) -> Token:
        t = self.peek()
        if t and t.type == T_IDENT:
            return self.next()
        if t and t.type == T_KEYWORD:
            raise GrammarError(err(
                ERR_GRAMMAR_UNEXPECTED_TOKEN,
                f"Expected {what}, found reserved word '{t.text}' (reserved words cannot be user-defined names).",
                LAYER_GRAMMAR, t.line, t.col))
        got = f"{t.type} {t.text!r}" if t else "end of source"
        raise GrammarError(err(
            ERR_GRAMMAR_UNEXPECTED_TOKEN,
            f"Expected {what}, found {got}.",
            LAYER_GRAMMAR, t.line if t else None, t.col if t else None))

    # ---- program -------------------------------------------------------
    def parse_program(self) -> dict:
        id_div = self.parse_id_div()
        data_div = self.parse_data_div()
        proc_div = self.parse_proc_div()
        t = self.peek()
        if t:
            raise GrammarError(err(
                ERR_GRAMMAR_UNEXPECTED_TOKEN,
                f"Unexpected content after the Procedure Division: {t.type} {t.text!r}.",
                LAYER_GRAMMAR, t.line, t.col))
        return {"type": "Program", "identification_division": id_div,
                "data_division": data_div, "procedure_division": proc_div}

    def parse_id_div(self) -> dict:
        start = self.expect_kw("IDENTIFICATION", "the Identification Division header")
        self.expect_kw("DIVISION", "the Identification Division header")
        self.expect_punct(".", "the header period")
        self.expect_kw("PROGRAM-ID", "the PROGRAM-ID paragraph")
        self.expect_punct(".", "the PROGRAM-ID period")
        name = self.expect_ident("the program name")
        initial = False
        if self.at_kw("IS"):
            self.next()
            self.expect_kw("INITIAL", "'INITIAL' after 'IS'")
            initial = True
        self.expect_punct(".", "the PROGRAM-ID closing period")
        return {"type": "IdentificationDivision", "program_name": name.text,
                "is_initial": initial, "span": {"line": start.line, "col": start.col}}

    def parse_data_div(self) -> dict:
        self.expect_kw("DATA", "the Data Division header")
        self.expect_kw("DIVISION", "the Data Division header")
        self.expect_punct(".", "the header period")
        ws = self.parse_ws_sec() if self.at_kw("WORKING-STORAGE") else None
        linkage = self.parse_linkage_sec()
        return {"type": "DataDivision", "working_storage": ws, "linkage": linkage}

    def parse_ws_sec(self) -> dict:
        head = self.expect_kw("WORKING-STORAGE", "the WORKING-STORAGE SECTION header")
        self.expect_kw("SECTION", "the WORKING-STORAGE SECTION header")
        self.expect_punct(".", "the header period")
        entries = []
        while self.peek() and self.peek().type == T_LEVEL:
            entries.append(self.parse_data_entry())
        return {"type": "WorkingStorageSection", "entries": entries,
                "span": {"line": head.line, "col": head.col}}

    def parse_linkage_sec(self) -> dict:
        head = self.expect_kw("LINKAGE", "the LINKAGE SECTION header")
        self.expect_kw("SECTION", "the LINKAGE SECTION header")
        self.expect_punct(".", "the header period")
        entries = []
        while self.peek() and self.peek().type == T_LEVEL:
            entries.append(self.parse_data_entry())
        if not entries:
            t = self.peek()
            raise GrammarError(err(
                ERR_GRAMMAR_INCOMPLETE,
                "LINKAGE SECTION requires at least one data entry.",
                LAYER_GRAMMAR, t.line if t else None, t.col if t else None))
        return {"type": "LinkageSection", "entries": entries,
                "span": {"line": head.line, "col": head.col}}

    def parse_data_entry(self) -> dict:
        level = self.next()  # LEVEL token (guaranteed by caller)
        name = self.expect_ident("a data-item name after the level number")
        pic = usage = sign = value = None
        while True:
            if pic is None and self.at_kw("PIC", "PICTURE"):
                pic = self.parse_pic_clause()
            elif usage is None and self.at_kw("USAGE", "COMP-3", "PACKED-DECIMAL", "DISPLAY"):
                usage = self.parse_usage_clause()
            elif sign is None and self.at_kw("SIGN"):
                sign = self.parse_sign_clause()
            elif value is None and self.at_kw("VALUE"):
                value = self.parse_value_clause()
            else:
                break
        self.expect_punct(".", "the data-entry period")
        return {"type": "DataEntry", "level": int(level.text), "level_text": level.text,
                "name": name.text, "line": level.line, "col": level.col,
                "pic": pic, "usage": usage, "sign": sign, "value": value}

    def parse_pic_clause(self) -> dict:
        self.next()  # PIC / PICTURE
        if self.at_kw("IS"):
            self.next()
        t = self.peek()
        pic_str = self.parse_pic_string()
        return {"picture": pic_str, "line": t.line if t else None, "col": t.col if t else None}

    def parse_pic_string(self) -> str:
        """Reconstruct the PIC character-string from raw word/number/punct
        tokens. The corpus grammar's pic_str is [S]i digit_run [V digit_run]
        (and [S]i V digit_run); Lark's contextual lexer gives the literals
        priority, which concatenates forms like SV999 / S9(5)V99 / V999.
        We consume raw tokens until the next clause keyword or period and
        validate the reconstructed string in the AST layer."""
        parts: List[str] = []
        stop_at = {"USAGE", "COMP-3", "PACKED-DECIMAL", "DISPLAY",
                   "SIGN", "VALUE"}
        while True:
            t = self.peek()
            if t is None:
                break
            if t.type == T_PUNCT and t.text == ".":
                break
            if t.type == T_KEYWORD and t.text in stop_at:
                break
            if t.type in (T_IDENT, T_NUMBER, T_KEYWORD, T_PUNCT, T_LEVEL):
                parts.append(t.text)
                self.next()
            else:
                break
        if not parts:
            t = self.peek()
            raise GrammarError(err(
                ERR_GRAMMAR_UNEXPECTED_TOKEN,
                "Expected a PICTURE character-string.",
                LAYER_GRAMMAR, t.line if t else None, t.col if t else None))
        return "".join(parts)

    def parse_usage_clause(self) -> dict:
        t = self.peek()
        if self.at_kw("USAGE"):
            self.next()
            if self.at_kw("IS"):
                self.next()
        u = self.next()  # COMP-3 | PACKED-DECIMAL | DISPLAY
        kind = {"COMP-3": "comp3", "PACKED-DECIMAL": "comp3", "DISPLAY": "display"}[u.text]
        return {"usage": kind, "keyword": u.text,
                "line": t.line if t else u.line, "col": t.col if t else u.col}

    def parse_sign_clause(self) -> dict:
        start = self.next()  # SIGN
        if self.at_kw("IS"):
            self.next()
        lead = self.next()
        if not (lead and lead.type == T_KEYWORD and lead.text in ("LEADING", "TRAILING")):
            raise GrammarError(err(
                ERR_GRAMMAR_UNEXPECTED_TOKEN,
                "Expected LEADING or TRAILING in the SIGN clause.",
                LAYER_GRAMMAR, lead.line if lead else None, lead.col if lead else None))
        self.expect_kw("SEPARATE", "'SEPARATE' in the SIGN clause")
        if self.at_kw("CHARACTER"):
            self.next()
        return {"leading": lead.text == "LEADING",
                "line": start.line, "col": start.col}

    def parse_value_clause(self) -> dict:
        start = self.next()  # VALUE
        if self.at_kw("IS"):
            self.next()
        t = self.peek()
        if not (t and t.type == T_NUMBER):
            raise GrammarError(err(
                ERR_GRAMMAR_UNEXPECTED_TOKEN,
                "VALUE requires a signed decimal literal.",
                LAYER_GRAMMAR, t.line if t else None, t.col if t else None))
        lit = self.next()
        return {"value": lit.text, "line": start.line, "col": start.col}

    # ---- procedure division -------------------------------------------
    def parse_proc_div(self) -> dict:
        head = self.expect_kw("PROCEDURE", "the Procedure Division header")
        self.expect_kw("DIVISION", "the Procedure Division header")
        using = []
        if self.at_kw("USING"):
            self.next()
            while True:
                t = self.peek()
                if t and t.type == T_IDENT:
                    using.append(self.next().text)
                else:
                    break
            if not using:
                t = self.peek()
                raise GrammarError(err(
                    ERR_GRAMMAR_UNEXPECTED_TOKEN,
                    "USING requires at least one operand name.",
                    LAYER_GRAMMAR, t.line if t else None, t.col if t else None))
        self.expect_punct(".", "the header period")
        sentences = []
        while self.peek() and not self.at_punct("."):
            sentences.append(self.parse_sentence())
        return {"type": "ProcedureDivision", "using": using,
                "sentences": sentences, "span": {"line": head.line, "col": head.col}}

    def parse_sentence(self) -> dict:
        start = self.peek()
        stmts = []
        while self.peek() and self.peek().type == T_KEYWORD and \
                self.peek().text in STATEMENT_KEYWORDS:
            stmts.append(self.parse_statement())
            if self.at_punct("."):
                break
        if not stmts:
            t = self.peek()
            raise GrammarError(err(
                ERR_GRAMMAR_UNEXPECTED_TOKEN,
                f"Expected a statement, found {t.type} {t.text!r}." if t
                else "Expected a statement.",
                LAYER_GRAMMAR, t.line if t else None, t.col if t else None))
        self.expect_punct(".", "the sentence-ending period")
        return {"type": "Sentence", "statements": stmts,
                "span": {"line": start.line, "col": start.col}}

    # ---- statements ------------------------------------------------------
    def parse_statement(self) -> dict:
        t = self.peek()
        kw = t.text
        if kw == "MOVE":
            return self.parse_move()
        if kw == "COMPUTE":
            return self.parse_compute()
        if kw == "ADD":
            return self.parse_add()
        if kw == "SUBTRACT":
            return self.parse_subtract()
        if kw == "MULTIPLY":
            return self.parse_multiply()
        if kw == "DIVIDE":
            return self.parse_divide()
        if kw == "IF":
            return self.parse_if()
        if kw == "GOBACK":
            self.next()
            return {"type": "Goback", "span": {"line": t.line, "col": t.col}}
        raise GrammarError(err(
            ERR_GRAMMAR_UNEXPECTED_TOKEN,
            f"Unexpected keyword '{kw}' where a statement was expected.",
            LAYER_GRAMMAR, t.line, t.col))

    def parse_if(self) -> dict:
        start = self.next()  # IF
        left = self.parse_expr()
        op = self.peek()
        if not (op and op.type == T_PUNCT and op.text in CONDITION_OPS):
            raise GrammarError(err(
                ERR_GRAMMAR_UNEXPECTED_TOKEN,
                "Expected a comparison operator (=, <>, <, <=, >, >=).",
                LAYER_GRAMMAR, op.line if op else None, op.col if op else None))
        self.next()
        right = self.parse_expr()
        if self.at_kw("THEN"):
            self.next()
        then_body = self.parse_stmt_list()
        else_body = []
        if self.at_kw("ELSE"):
            self.next()
            else_body = self.parse_stmt_list()
        if self.at_kw("END-IF"):
            self.next()
        else:
            t = self.peek()
            raise GrammarError(err(
                ERR_GRAMMAR_MISSING_TERMINATOR,
                "IF requires the END-IF terminator.",
                LAYER_GRAMMAR, start.line, start.col))
        return {"type": "If", "condition": {"op": op.text, "left": left, "right": right},
                "then": then_body, "else": else_body,
                "span": {"line": start.line, "col": start.col}}

    def _atom_start(self, t) -> bool:
        """True if the token can begin an operand atom. The corpus lexer is
        contextual: a level-shaped digit word is a level number in data
        entries but an integer literal in procedure operands (MOVE 42 TO ...).
        Figurative constants (ZERO, SPACE, ...) are reserved keywords used as
        literals."""
        if t is None:
            return False
        if t.type in (T_IDENT, T_NUMBER):
            return True
        if t.type == T_LEVEL and t.text.isdigit():
            return True
        if t.type == T_KEYWORD and t.text in FIGURATIVE_CONSTANTS:
            return True
        return False

    def parse_atom(self) -> dict:
        t = self.peek()
        if t and t.type == T_IDENT:
            self.next()
            return {"kind": "identifier", "name": t.text,
                    "span": {"line": t.line, "col": t.col}}
        if t and t.type == T_NUMBER:
            self.next()
            return {"kind": "literal", "text": t.text,
                    "span": {"line": t.line, "col": t.col}}
        if t and t.type == T_LEVEL and t.text.isdigit():
            self.next()
            return {"kind": "literal", "text": t.text,
                    "span": {"line": t.line, "col": t.col}}
        if t and t.type == T_KEYWORD and t.text in FIGURATIVE_CONSTANTS:
            self.next()
            return {"kind": "figurative", "text": t.text,
                    "span": {"line": t.line, "col": t.col}}
        got = f"{t.type} {t.text!r}" if t else "end of source"
        raise GrammarError(err(
            ERR_GRAMMAR_UNEXPECTED_TOKEN,
            f"Expected an identifier or literal, found {got}.",
            LAYER_GRAMMAR, t.line if t else None, t.col if t else None))

    def parse_target_spec(self) -> dict:
        name = self.expect_ident("a target identifier")
        rounded = False
        if self.at_kw("ROUNDED"):
            self.next()
            rounded = True
        return {"name": name.text, "rounded": rounded,
                "span": {"line": name.line, "col": name.col}}

    def parse_expr(self) -> dict:
        node = self.parse_term()
        while self.at_punct("+") or self.at_punct("-"):
            op = self.next().text
            rhs = self.parse_term()
            node = {"kind": "binary", "op": op, "left": node, "right": rhs}
        return node

    def parse_term(self) -> dict:
        node = self.parse_factor()
        while self.at_punct("*") or self.at_punct("/"):
            op = self.next().text
            rhs = self.parse_factor()
            node = {"kind": "binary", "op": op, "left": node, "right": rhs}
        return node

    def parse_factor(self) -> dict:
        t = self.peek()
        if t and t.type == T_PUNCT and t.text in "+-":
            self.next()
            operand = self.parse_factor()
            return {"kind": "unary", "op": t.text, "operand": operand}
        if t and t.type == T_PUNCT and t.text == "(":
            self.next()
            inner = self.parse_expr()
            self.expect_punct(")", "the closing parenthesis")
            return inner
        return self.parse_atom()

    def parse_move(self) -> dict:
        start = self.next()  # MOVE
        src = self.parse_atom()
        self.expect_kw("TO", "'TO' in the MOVE statement")
        targets = [self.parse_target_spec()]
        while self.peek() and self.peek().type == T_IDENT:
            targets.append(self.parse_target_spec())
        return {"type": "Move", "source": src, "targets": targets,
                "span": {"line": start.line, "col": start.col}}

    def parse_compute(self) -> dict:
        start = self.next()  # COMPUTE
        target = self.parse_target_spec()
        self.expect_punct("=", "'=' in the COMPUTE statement")
        expr = self.parse_expr()
        has_se = False
        if self.at_kw("ON", "NOT", "SIZE"):
            self.parse_size_error_clauses()
            has_se = True
            self.expect_kw("END-COMPUTE", "the mandatory END-COMPUTE terminator")
        elif self.at_kw("END-COMPUTE"):
            self.next()
        return {"type": "Compute", "target": target, "expr": expr,
                "size_error": has_se, "span": {"line": start.line, "col": start.col}}

    def parse_size_error_clauses(self) -> dict:
        start = self.peek()
        if self.at_kw("ON"):
            self.next()
        self.expect_kw("SIZE", "'SIZE ERROR'")
        self.expect_kw("ERROR", "'SIZE ERROR'")
        on_body = self.parse_stmt_list()
        not_body = []
        if self.at_kw("NOT"):
            self.next()
            if self.at_kw("ON"):
                self.next()
            self.expect_kw("SIZE", "'SIZE ERROR' after NOT")
            self.expect_kw("ERROR", "'SIZE ERROR' after NOT")
            not_body = self.parse_stmt_list()
        return {"type": "SizeErrorClauses", "on_body": on_body, "not_body": not_body,
                "span": {"line": start.line, "col": start.col}}

    def parse_stmt_list(self) -> list:
        out = []
        while self.peek() and self.peek().type == T_KEYWORD and \
                self.peek().text in STATEMENT_KEYWORDS:
            out.append(self.parse_statement())
        if not out:
            t = self.peek()
            raise GrammarError(err(
                ERR_GRAMMAR_UNEXPECTED_TOKEN,
                "A SIZE ERROR clause requires at least one statement.",
                LAYER_GRAMMAR, t.line if t else None, t.col if t else None))
        return out

    def parse_add(self) -> dict:
        start = self.next()  # ADD
        atoms = [self.parse_atom()]
        while self._atom_start(self.peek()):
            atoms.append(self.parse_atom())
        if self.at_kw("TO") or self.at_kw("GIVING"):
            mode = self.next().text
            target = self.parse_target_spec()
            self._optional_end("END-ADD")
            return {"type": "Add", "mode": mode, "operands": atoms,
                    "target": target, "span": {"line": start.line, "col": start.col}}
        t = self.peek()
        raise GrammarError(err(
            ERR_GRAMMAR_UNEXPECTED_TOKEN,
            "ADD requires TO or GIVING.",
            LAYER_GRAMMAR, t.line if t else None, t.col if t else None))

    def parse_subtract(self) -> dict:
        start = self.next()  # SUBTRACT
        atoms = [self.parse_atom()]
        while self._atom_start(self.peek()):
            atoms.append(self.parse_atom())
        self.expect_kw("FROM", "'FROM' in the SUBTRACT statement")
        t = self.peek()
        if len(atoms) == 1 and self._atom_start(t):
            # could be SUBTRACT a FROM b GIVING t
            save = self.i
            try:
                b = self.parse_atom()
                if self.at_kw("GIVING"):
                    self.next()
                    target = self.parse_target_spec()
                    self._optional_end("END-SUBTRACT")
                    return {"type": "Subtract", "form": "giving",
                            "minuend": b, "subtrahends": atoms, "target": target,
                            "span": {"line": start.line, "col": start.col}}
            except GrammarError:
                pass
            self.i = save
        target = self.parse_target_spec()
        self._optional_end("END-SUBTRACT")
        return {"type": "Subtract", "form": "from", "subtrahends": atoms,
                "target": target, "span": {"line": start.line, "col": start.col}}

    def parse_multiply(self) -> dict:
        start = self.next()  # MULTIPLY
        a = self.parse_atom()
        self.expect_kw("BY", "'BY' in the MULTIPLY statement")
        b = self.parse_atom()
        self.expect_kw("GIVING", "'GIVING' in the MULTIPLY statement")
        target = self.parse_target_spec()
        self._optional_end("END-MULTIPLY")
        return {"type": "Multiply", "left": a, "right": b, "target": target,
                "span": {"line": start.line, "col": start.col}}

    def parse_divide(self) -> dict:
        start = self.next()  # DIVIDE
        a = self.parse_atom()
        mode = None
        if self.at_kw("BY") or self.at_kw("INTO"):
            mode = self.next().text
        else:
            t = self.peek()
            raise GrammarError(err(
                ERR_GRAMMAR_UNEXPECTED_TOKEN,
                "DIVIDE requires BY or INTO.",
                LAYER_GRAMMAR, t.line if t else None, t.col if t else None))
        b = self.parse_atom()
        self.expect_kw("GIVING", "'GIVING' in the DIVIDE statement")
        target = self.parse_target_spec()
        self._optional_end("END-DIVIDE")
        return {"type": "Divide", "mode": mode, "first": a, "second": b,
                "target": target, "span": {"line": start.line, "col": start.col}}

    def _optional_end(self, terminator: str) -> None:
        if self.at_kw(terminator):
            self.next()


def parse(tokens: List[Token]) -> tuple[dict, List[Diagnostic]]:
    parser = Parser(tokens)
    try:
        ast = parser.parse_program()
        return ast, []
    except GrammarError as e:
        return None, [e.diag]
