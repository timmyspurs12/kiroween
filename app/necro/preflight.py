"""Layer 1 — Preflight (byte-level, non-mutating). Rev5 §2.2 Layer 1.

Rules (frozen corpus):
  - 1 <= file <= 32768 bytes; 1 <= lines <= 500
  - reject NUL(0x00) / CR(0x0D) / TAB(0x09) / bytes >= 0x80 at (line, col, ERR_INVALID_CHAR)
  - any pre-newline line length > 72 -> (line, 73, ERR_COL73_OVERFLOW)
  - cols 1-6: spaces/digits only -> ERR_SEQ_AREA at the offending column
  - col 7 in {' ', '*', '/'} -> else ERR_INVALID_INDICATOR at (line, 7)
"""
from typing import List
from .diagnostics import (Diagnostic, err, ERR_INVALID_CHAR, ERR_COL73_OVERFLOW,
                          ERR_SEQ_AREA, ERR_INVALID_INDICATOR,
                          ERR_FILE_TOO_LARGE, ERR_FILE_TOO_LONG, ERR_FILE_EMPTY,
                          LAYER_PREFLIGHT, SEVERITY_ERROR)

MAX_BYTES = 32768
MAX_LINES = 500
MAX_COLUMNS = 72  # content region is cols 1..72


def run_preflight(text: str) -> List[Diagnostic]:
    diags: List[Diagnostic] = []
    raw = text.encode("utf-8", errors="surrogateescape")

    if len(raw) == 0:
        diags.append(err(ERR_FILE_EMPTY, "Source is empty.", LAYER_PREFLIGHT, 1, 1))
        return diags
    if len(raw) > MAX_BYTES:
        diags.append(err(ERR_FILE_TOO_LARGE,
                         f"Source is {len(raw)} bytes; the limit is {MAX_BYTES}.",
                         LAYER_PREFLIGHT, None, None))
        return diags

    lines = text.split("\n")
    if len(lines) > MAX_LINES:
        diags.append(err(ERR_FILE_TOO_LONG,
                         f"Source has {len(lines)} lines; the limit is {MAX_LINES}.",
                         LAYER_PREFLIGHT, MAX_LINES + 1, 1))
        return diags

    # CR / NUL anywhere (byte-level scan; TAB and >=0x80 are found per-line below
    # so the reported column matches the text grid).
    for i, ch in enumerate(raw):
        if ch == 0x0D:
            line_no = raw[:i].count(0x0A) + 1
            col = i - (raw.rfind(0x0A, 0, i) + 1) + 1
            diags.append(err(ERR_INVALID_CHAR, "CR (0x0D) byte is not allowed.",
                             LAYER_PREFLIGHT, line_no, col))
            break

    for line_no, line in enumerate(lines, start=1):
        # character-level checks
        stop = False
        for col_no, ch in enumerate(line, start=1):
            if ch == "\t":
                diags.append(err(ERR_INVALID_CHAR, "TAB character is not allowed.",
                                 LAYER_PREFLIGHT, line_no, col_no, context_line=line))
                stop = True
                break
            if ord(ch) > 0x7E or ch == "\x00":
                diags.append(err(ERR_INVALID_CHAR,
                                 f"Character {ch!r} (byte >= 0x80 or NUL) is not allowed.",
                                 LAYER_PREFLIGHT, line_no, col_no, context_line=line))
                stop = True
                break
        if stop:
            continue

        if len(line) > MAX_COLUMNS:
            # corpus rule: any pre-newline line longer than 72 columns is
            # rejected at (line, 73) — cols 73+ are not part of NVS-0 source
            diags.append(err(ERR_COL73_OVERFLOW,
                             "Line extends past column 72.",
                             LAYER_PREFLIGHT, line_no, 73, context_line=line))
            continue  # one overflow finding per line

        if line:
            seq = line[:6].ljust(6)
            for idx, ch in enumerate(seq, start=1):
                if ch != " " and not ch.isdigit():
                    diags.append(err(ERR_SEQ_AREA,
                                     "Columns 1-6 may contain only spaces or digits.",
                                     LAYER_PREFLIGHT, line_no, idx, context_line=line))
                    break

            if len(line) >= 7:
                indicator = line[6]
                if indicator not in (" ", "*", "/"):
                    diags.append(err(ERR_INVALID_INDICATOR,
                                     f"Invalid indicator {indicator!r} in column 7.",
                                     LAYER_PREFLIGHT, line_no, 7, context_line=line))

    return diags
