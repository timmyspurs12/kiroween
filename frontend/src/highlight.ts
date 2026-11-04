import type { Token } from "./api";

/**
 * Client-side COBOL fixed-format highlighting for the editor. This is a
 * display heuristic only — authoritative tokenization always comes from the
 * backend lexing layer (visible in the Tokens tab).
 */

const KEYWORD_STEMS = [
  "IDENTIFICATION", "DIVISION", "PROGRAM-ID", "IS", "INITIAL",
  "DATA", "WORKING-STORAGE", "LINKAGE", "SECTION",
  "PIC", "PICTURE", "USAGE", "COMP-3", "PACKED-DECIMAL", "DISPLAY",
  "SIGN", "LEADING", "TRAILING", "SEPARATE", "CHARACTER", "VALUE",
  "PROCEDURE", "USING", "MOVE", "TO", "COMPUTE", "ROUNDED", "ON", "NOT",
  "SIZE", "ERROR", "END-COMPUTE", "ADD", "GIVING", "END-ADD", "SUBTRACT",
  "FROM", "END-SUBTRACT", "MULTIPLY", "BY", "END-MULTIPLY", "DIVIDE",
  "INTO", "END-DIVIDE", "IF", "THEN", "ELSE", "END-IF", "GOBACK",
];

const WORD_RE = /[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*/g;
const KEYWORD_SET = new Set(KEYWORD_STEMS);

function classifyWord(w: string): "kw" | "level" | "ident" | "num" {
  const up = w.toUpperCase();
  if (KEYWORD_SET.has(up)) return "kw";
  if (/^(0[1-9]|[1-4][0-9]|77)$/.test(w)) return "level";
  if (/^[0-9]+(\.[0-9]+)?$/.test(w)) return "num";
  return "ident";
}

export interface HlSpan {
  cls: string | null;
  text: string;
}

/** Produce highlighted spans for one fixed-format source string. */
export function highlightSource(source: string): HlSpan[][] {
  const lines = source.split("\n");
  return lines.map((line) => {
    const spans: HlSpan[] = [];
    const n = line.length;
    let i = 0;

    // sequence area cols 1-6 (index 0..5) — muted
    if (n > 0) {
      const seq = line.slice(0, Math.min(6, n));
      spans.push({ cls: "tok-comment", text: seq });
      i = Math.min(6, n);
    }
    // indicator col 7 (index 6)
    if (i < n && i < 7) {
      const ch = line[i]!;
      if (ch === "*" || ch === "/") {
        spans.push({ cls: "tok-comment", text: line.slice(i) });
        return spans;
      }
      spans.push({ cls: null, text: ch });
      i += 1;
    }
    while (i < 8 && i < n) {
      spans.push({ cls: null, text: line[i]! });
      i += 1;
    }

    // content area cols 8-72
    const contentEnd = Math.min(n, 72);
    let buf = "";
    const flush = () => {
      if (buf) {
        spans.push({ cls: null, text: buf });
        buf = "";
      }
    };
    while (i < contentEnd) {
      const ch = line[i]!;
      if (ch === '"') {
        flush();
        let j = i + 1;
        while (j < contentEnd && line[j] !== '"') j += 1;
        j = Math.min(j + 1, contentEnd);
        spans.push({ cls: "tok-str", text: line.slice(i, j) });
        i = j;
        continue;
      }
      if (/[A-Za-z0-9]/.test(ch)) {
        WORD_RE.lastIndex = 0;
        WORD_RE.lastIndex = i;
        const m = WORD_RE.exec(line.slice(0, contentEnd));
        const word = m && m.index === i ? m[0] : ch;
        flush();
        const kind = classifyWord(word);
        spans.push({
          cls: kind === "kw" ? "tok-kw" : kind === "level" ? "tok-level" : kind === "num" ? "tok-num" : "tok-ident",
          text: word,
        });
        i += word.length;
        continue;
      }
      buf += ch;
      i += 1;
    }
    flush();

    // cols 73+ — flagged overflow
    if (n > 72) {
      spans.push({ cls: "tok-over72", text: line.slice(72) });
    }
    return spans;
  });
}

/** Merge backend tokens into per-line span lists (used when analysis exists). */
export function tokensToLines(tokens: Token[], source: string): HlSpan[][] {
  const lines = source.split("\n");
  const out: HlSpan[][] = lines.map(() => []);
  const byLine = new Map<number, Token[]>();
  for (const t of tokens) {
    const arr = byLine.get(t.line) ?? [];
    arr.push(t);
    byLine.set(t.line, arr);
  }
  for (let ln = 1; ln <= lines.length; ln++) {
    const lineText = lines[ln - 1] ?? "";
    const n = lineText.length;
    if (n === 0) {
      out[ln - 1] = [];
      continue;
    }
    // sequence + indicator prefix
    const seqEnd = Math.min(7, n);
    const isComment = lineText[6] === "*" || lineText[6] === "/";
    if (isComment) {
      out[ln - 1]!.push({ cls: "tok-comment", text: lineText });
      continue;
    }
    let idx = 0;
    if (seqEnd > 0) {
      out[ln - 1]!.push({ cls: "tok-comment", text: lineText.slice(0, Math.min(6, seqEnd)) });
      idx = Math.min(6, seqEnd);
      if (idx < 7 && idx < n) {
        out[ln - 1]!.push({ cls: null, text: lineText[idx]! });
        idx += 1;
      }
      while (idx < 8 && idx < n) {
        out[ln - 1]!.push({ cls: null, text: lineText[idx]! });
        idx += 1;
      }
    }
    const toks = (byLine.get(ln) ?? []).slice().sort((a, b) => a.col - b.col);
    for (const t of toks) {
      const start = t.col - 1;
      if (start > idx) {
        out[ln - 1]!.push({ cls: null, text: lineText.slice(idx, start) });
      }
      const cls =
        t.type === "KEYWORD"
          ? "tok-kw"
          : t.type === "LEVEL"
            ? "tok-level"
            : t.type === "NUMBER"
              ? "tok-num"
              : t.type === "PUNCT"
                ? "tok-punct"
                : "tok-ident";
      out[ln - 1]!.push({ cls, text: t.text });
      idx = start + t.text.length;
    }
    if (idx < n) {
      if (idx < 72) {
        out[ln - 1]!.push({ cls: null, text: lineText.slice(idx, 72) });
        idx = 72;
      }
      if (n > 72) {
        out[ln - 1]!.push({ cls: "tok-over72", text: lineText.slice(idx) });
      }
    }
  }
  return out;
}
