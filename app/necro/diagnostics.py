"""NecroSpec NVS-0 analyzer — diagnostics model.

Stable diagnostic codes follow the frozen Rev6.4.2 corpus (Rev5 §2.2/§2.3,
Rev4 §2.2.2). Codes not named in the corpus are marked [EXT] and are
agent-stable extensions, never corpus codes.
"""
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional


# ---- Layer 1: Preflight (Rev5 §2.2 Layer 1) ----
ERR_INVALID_CHAR = "ERR_INVALID_CHAR"        # NUL/CR/TAB/byte >= 0x80
ERR_COL73_OVERFLOW = "ERR_COL73_OVERFLOW"    # content past column 72
ERR_SEQ_AREA = "ERR_SEQ_AREA"                # cols 1-6 not spaces/digits
ERR_INVALID_INDICATOR = "ERR_INVALID_INDICATOR"  # col 7 not in {' ','*','/'}
ERR_FILE_TOO_LARGE = "ERR_FILE_TOO_LARGE"    # [EXT] > 32768 bytes
ERR_FILE_TOO_LONG = "ERR_FILE_TOO_LONG"      # [EXT] > 500 lines
ERR_FILE_EMPTY = "ERR_FILE_EMPTY"            # [EXT] 0 bytes

# ---- Layer 2: Lexical (Rev4 §2.2.2 / Rev5 §2.2 Layer 2) ----
ERR_LEX_INVALID_WORD = "ERR_LEX_INVALID_WORD"

# ---- Layer 3: Grammar (Rev4 §2.2.2 EBNF; layer name per corpus) ----
ERR_GRAMMAR_UNEXPECTED_TOKEN = "ERR_GRAMMAR_UNEXPECTED_TOKEN"      # [EXT]
ERR_GRAMMAR_MISSING_TERMINATOR = "ERR_GRAMMAR_MISSING_TERMINATOR"  # [EXT] END-*
ERR_GRAMMAR_MISSING_PERIOD = "ERR_GRAMMAR_MISSING_PERIOD"          # [EXT]
ERR_GRAMMAR_INCOMPLETE = "ERR_GRAMMAR_INCOMPLETE"                  # [EXT]

# ---- Layer 4: AST semantics (Rev5 §2.2 Layer 4) ----
ERR_DUPLICATE_SYMBOL = "ERR_DUPLICATE_SYMBOL"
ERR_PIC_DIGIT_LIMIT = "ERR_PIC_DIGIT_LIMIT"          # 1 <= I+F <= 18
ERR_OVERPUNCH_UNSUPPORTED = "ERR_OVERPUNCH_UNSUPPORTED"  # signed DISPLAY w/o SIGN SEPARATE
ERR_SIGN_CLAUSE_UNSUPPORTED = "ERR_SIGN_CLAUSE_UNSUPPORTED"  # [EXT] COMP-3 + SIGN SEPARATE
ERR_PIC_REQUIRED = "ERR_PIC_REQUIRED"                # [EXT] leaf item without PICTURE
ERR_UNDECLARED_IDENT = "ERR_UNDECLARED_IDENT"
ERR_NON_ELEMENTARY_TARGET = "ERR_NON_ELEMENTARY_TARGET"
ERR_LEVEL_STRUCTURE = "ERR_LEVEL_STRUCTURE"          # [EXT] impossible level nesting

# ---- Layer 5: Semantic analysis (Milestone 2; agent layer [EXT]) --------
SEM_DIVISOR_ZERO = "SEM_DIVISOR_ZERO"                # [EXT] literal 0 divisor
SEM_MOVE_SPACES_TO_NUMERIC = "SEM_MOVE_SPACES_TO_NUMERIC"  # [EXT] SPACES -> numeric
SEM_TRUNCATION_HIGH = "SEM_TRUNCATION_HIGH"          # [EXT] high-order digits lost
SEM_PRECISION_LOSS = "SEM_PRECISION_LOSS"            # [EXT] low-order digits lost
SEM_SIGN_DISCARD = "SEM_SIGN_DISCARD"                # [EXT] unsigned receiver, signed result
SEM_SIZE_ERROR_GUARD = "SEM_SIZE_ERROR_GUARD"        # [EXT] overflow guarded (info)

LAYER_SEMANTIC = "Semantic"

# Finding classification (platform model): every diagnostic states what kind
# of knowledge it carries, so consumers can separate proven violations from
# possibilities, notes and unsupported constructs.
CLASS_VIOLATION = "violation"    # proven: definite against declared rules/evidence
CLASS_RISK = "risk"              # possibility: needs human investigation
CLASS_NOTE = "note"              # informational, no action required
CLASS_UNSUPPORTED = "unsupported"  # construct/frame outside the supported subset

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

# severity -> classification for finding kinds whose meaning follows their
# severity (semantic layer, project findings)
_SEVERITY_CLASSIFICATION = {
    SEVERITY_ERROR: CLASS_VIOLATION,
    SEVERITY_WARNING: CLASS_RISK,
    SEVERITY_INFO: CLASS_NOTE,
}

LAYER_PREFLIGHT = "Preflight"
LAYER_LEXICAL = "Lexical"
LAYER_GRAMMAR = "Grammar"
LAYER_AST = "AST"

_LAYER_CLASSIFICATION = {
    LAYER_PREFLIGHT: CLASS_UNSUPPORTED,
    LAYER_LEXICAL: CLASS_UNSUPPORTED,
    LAYER_GRAMMAR: CLASS_UNSUPPORTED,
    LAYER_AST: CLASS_VIOLATION,
    LAYER_SEMANTIC: CLASS_RISK,  # overridden per-finding by the semantic layer
}

# Suggested-correction text per stable code (shown in the diagnostics UI).
HINTS = {
    ERR_INVALID_CHAR: "Remove the character. NVS-0 source must be 7-bit ASCII with no NUL, CR or TAB bytes.",
    ERR_COL73_OVERFLOW: "Keep statement content inside columns 8-72; columns 73-80 are reserved for sequence numbers.",
    ERR_SEQ_AREA: "Columns 1-6 may contain only spaces or a sequence number.",
    ERR_INVALID_INDICATOR: "Column 7 must be a space, '*' (comment) or '/' (page comment).",
    ERR_LEX_INVALID_WORD: "User-defined words start with a letter, use letters/digits/interior hyphens, max 30 chars, no trailing hyphen, and cannot be reserved.",
    ERR_GRAMMAR_UNEXPECTED_TOKEN: None,  # message carries the specifics
    ERR_GRAMMAR_MISSING_TERMINATOR: None,
    ERR_GRAMMAR_MISSING_PERIOD: "Each sentence ends with a period.",
    ERR_GRAMMAR_INCOMPLETE: None,
    ERR_DUPLICATE_SYMBOL: "Data-item names must be unique (case-insensitive) across the Data Division.",
    ERR_PIC_DIGIT_LIMIT: "Elementary items require 1 <= integer + fraction digits <= 18.",
    ERR_OVERPUNCH_UNSUPPORTED: "Signed DISPLAY items require SIGN IS LEADING/TRAILING SEPARATE.",
    ERR_SIGN_CLAUSE_UNSUPPORTED: "Remove the SIGN SEPARATE clause from COMP-3 items.",
    ERR_PIC_REQUIRED: "Elementary items (level 77 or leaves) require a PIC clause.",
    ERR_UNDECLARED_IDENT: "Reference a name declared in WORKING-STORAGE or LINKAGE.",
    ERR_NON_ELEMENTARY_TARGET: "Statements operate on elementary items, not group items.",
    SEM_DIVISOR_ZERO: "Guard the divisor (IF second = 0 …) or restructure the statement; division by zero aborts the program at run time.",
    SEM_MOVE_SPACES_TO_NUMERIC: "Move numeric data (for example ZERO) or review the receiver's category; later arithmetic on this field would read invalid data.",
    SEM_TRUNCATION_HIGH: "Compare the sender's capacity with the receiver's PICTURE; enlarge the receiver or confirm the loss of high-order digits is intended.",
    SEM_PRECISION_LOSS: "Align the fractional PICTURE digits, or add ROUNDED if truncation is not intended.",
    SEM_SIGN_DISCARD: "Give the receiver an S PICTURE (with an allowed sign clause) or confirm the program never produces a negative result here.",
    SEM_SIZE_ERROR_GUARD: "No action required for capacity here; note that the guard changes control flow on overflow, which matters for migration testing.",
    ERR_LEVEL_STRUCTURE: "Check the level-number nesting of the Data Division.",
}


@dataclass
class Diagnostic:
    severity: str
    code: str
    message: str
    line: Optional[int] = None
    col: Optional[int] = None
    layer: str = LAYER_PREFLIGHT
    hint: Optional[str] = None
    context_line: Optional[str] = None
    evidence: Optional[str] = None
    classification: Optional[str] = None
    detail: Optional[dict] = None
    finding_id: Optional[str] = None

    def __post_init__(self):
        if self.hint is None:
            self.hint = HINTS.get(self.code)
        if self.classification is None:
            self.classification = _LAYER_CLASSIFICATION.get(
                self.layer, CLASS_VIOLATION)
        # deterministic, stable finding identity for traceability across
        # runs and (later) multi-file reports
        if self.finding_id is None:
            basis = f"{self.code}|{self.line}|{self.col}|{self.message}"
            self.finding_id = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]

    def to_json(self) -> dict:
        return asdict(self)


def err(code: str, message: str, layer: str, line=None, col=None,
        context_line: Optional[str] = None) -> Diagnostic:
    return Diagnostic(SEVERITY_ERROR, code, message, line, col, layer,
                      context_line=context_line)
