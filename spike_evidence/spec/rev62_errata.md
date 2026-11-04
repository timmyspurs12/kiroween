# NecroSpec Rev 6.2 — Final Two-Item Correction (E-12, E-13)

Two errata only. All other Rev 5 / Rev 6 / Rev 6.1 content stands per §0.

---

## Deliverable 1 — E-12: Corrected `read_proc_slice()` and call-site confirmation

**Defect:** v3.1's `read_proc_slice()` initialised `*out_len` and `*rerr` at entry but **not `*oerr`**. On the `open()`-success path `*oerr` was never written, so the caller's aligned local (`oerr`) retained an indeterminate value — or, in Mode `'I'`, a **stale errno from a previous call site** — which was then copied into the wire field `open_err[i]`. All four `read_proc_slice` call sites were affected (three of them via reused locals). `probe_open()` has no equivalent hole (both outputs are written on every path).

> **E-12 (SUPERSEDES the `read_proc_slice` body in Rev 6.1 E-8 §3.3a; nothing else in fixture #20 changes):**
> ```c
> /* All pointer parameters are aligned caller locals, or uint8_t (alignment 1). */
> static void read_proc_slice(const char *path, uint8_t *dst, size_t cap,
>                             uint16_t *out_len, uint8_t *eof, uint8_t *trunc,
>                             uint8_t *openfail, int32_t *oerr, int32_t *rerr,
>                             uint8_t bit) {
>     *out_len = 0; *oerr = 0; *rerr = 0;   /* E-12: full init BEFORE open() */
>     int fd = open(path, O_RDONLY | O_CLOEXEC);
>     if (fd < 0) { *openfail |= (uint8_t)(1U << bit); *oerr = errno; return; }
>     size_t got = 0; int full = 0;
>     for (;;) {
>         if (got == cap) { full = 1; break; }
>         ssize_t r = read(fd, dst + got, cap - got);
>         if (r < 0) { if (errno == EINTR) continue; *rerr = errno; break; }
>         if (r == 0) { *eof |= (uint8_t)(1U << bit); break; }
>         got += (size_t)r;
>     }
>     if (full) {   /* exact-fit disambiguation (unchanged) */
>         char probe; ssize_t r;
>         do { r = read(fd, &probe, 1); } while (r < 0 && errno == EINTR);
>         if (r == 0)     *eof   |= (uint8_t)(1U << bit);
>         else if (r > 0) *trunc |= (uint8_t)(1U << bit);
>         else            *rerr  = errno;
>     }
>     close(fd);
>     *out_len = (uint16_t)got;
> }
> ```

**Confirmation (the question posed):** yes — with `*oerr = 0` executed before `open()` on every entry, the `open()`-success path leaves `*oerr == 0` (nothing else writes it), so every `h->open_err[i] = oerr;` copy stores the documented success value `0` instead of an indeterminate or stale errno. The invariant is now: **open-fail bit clear ⇒ `open_err[i] == 0`**; open-fail bit set ⇒ `open_err[i] == errno`; and `read_err[i] == 0` unless a read error occurred.

**Call-site audit (all four checked; call-site text unchanged — the fix is inside the helper):**

| # | Call site | Mode | Locals passed | Copy-out | Post-E-12 guarantee |
|---|---|---|---|---|---|
| 1 | `/proc/self/status` | 'I' | `&len, &oerr, &rerr` | `h->status_len = len; h->open_err[0] = oerr; h->read_err[0] = rerr;` | success ⇒ `open_err[0]==0 ∧ read_err[0]==0` |
| 2 | `/proc/self/uid_map` | 'I' | same locals (**reused**) | `…[1] = …` | entry-init removes the stale-errno reuse hazard (a prior status open-failure can no longer leak into slot 1) |
| 3 | `/proc/self/gid_map` | 'I' | same locals (**reused**) | `…[2] = …` | same, for slot 2 |
| 4 | `/proc/self/mountinfo` | 'E' | `&mlen, &oerr, &rerr` (fresh) | `h->mountinfo_len = mlen; h->open_err[3] = oerr; h->read_err[3] = rerr;` | success ⇒ `open_err[3]==0 ∧ read_err[3]==0` |

**Normative consumer amendment (§5.1a validation checks, one line added):** reject/flag any diagnostic record where `open_fail_flags` bit *i* is clear but `open_err[i] != 0` (inconsistent record ⇒ finding), in addition to the existing checks.

**Preserved unchanged:** 128-byte packed wire layout, all field offsets, `schema == 3`, `_Static_assert(sizeof == 128)`, the alignment-safe helper interface (all multi-byte values still flow through aligned locals). **No compilation or warning-free status is claimed**; execution remains prohibited, and `-Werror` cleanliness is an execution-time finding under §2.1.5.

---

## Deliverable 2 — E-13: Complete V1–V7 input PICTURE audit table

All PICTUREs are copied from the Rev 4 §3.1 fixture sources (in-corpus per §0). **No fixture definition is unavailable; no entry is marked incomplete; no PICTURE was inferred from bytes.** Implied-decimal note: `SV999` (I=0, F=3) and `SV99` (I=0, F=2) carry the decimal point at the **left edge** (leading implied decimal). Packed sign nibbles: `C`=+, `D`=−, `F`=unsigned (H4 convention). Pad nibbles: a leading `0x0` nibble is required when the digit count is **even**; the only packed even-digit field across V1–V7 is `LK-FACTOR` (`SV99`, 2 digits) — see the error register below.

| V | Field | PICTURE (exact, from fixture) | Input bytes | Decimal | Operation / role | Receiver PICTURE | Expected decimal | Expected output bytes | Sign/pad nibble | Class |
|---|---|---|---|---|---|---|---|---|---|---|
| V1 | LK-AMOUNT | `PIC S9(5)V99 COMP-3` (4 B) | `12 34 56 7C` | +12345.67 | multiplicand | — | — | — | C; 7 digits, no pad | input |
| V1 | LK-RATE | `PIC SV999 COMP-3` (2 B) | `12 5C` | +0.125 | multiplier (implied decimal at left) | — | — | — | C; 3 digits, no pad | input |
| V1 | LK-FEE | `PIC S9(5)V99 COMP-3` (4 B) | — | — | `COMPUTE LK-FEE = LK-AMOUNT * LK-RATE` (no ROUNDED); exact 1543.20875, trunc at store | `PIC S9(5)V99 COMP-3` | +1543.20 | `01 54 32 0C` | C; no pad | [D] |
| V2 | LK-BASE | `PIC S9(3)V99 COMP-3` (3 B) | `12 34 5C` | +123.45 | multiplicand | — | — | — | C; 5 digits, no pad | input |
| V2 | LK-FACTOR | `PIC SV99 COMP-3` (2 B) | `05 5C` | **+0.55** | multiplier (implied decimal at left; **leading pad nibble 0x0**: nibbles `0,5,5,C` → digits "55") | — | — | — | pad `0x0` + C | input |
| V2 | LK-OUT | `PIC S9(4)V9 COMP-3` (3 B) | — | — | `COMPUTE LK-OUT ROUNDED = LK-BASE * LK-FACTOR`; exact 67.8975 (scale 4) | `PIC S9(4)V9 COMP-3` | +67.9 | `00 67 9C` | C; 5 digits, no pad | [D] (default NEAREST-AWAY-FROM-ZERO) |
| V3 | LK-NUM | `PIC S9(3) COMP-3` (2 B) | `00 2C` | +2 | dividend | — | — | — | C; 3 digits, no pad | input |
| V3 | LK-DEN | `PIC S9(3) COMP-3` (2 B) | `00 3C` | +3 | divisor | — | — | — | C; no pad | input |
| V3 | LK-NOTIONAL | `PIC S9(5) COMP-3` (3 B) | `10 00 0C` | +10000 | factor | — | — | — | C; 5 digits, no pad | input |
| V3 | LK-ACCRUAL | `PIC S9(5)V99 COMP-3` (4 B) | — | — | `COMPUTE LK-ACCRUAL = (LK-NUM / LK-DEN) * LK-NOTIONAL` (no ROUNDED); exact 20000/3 = 6666.66̄ | `PIC S9(5)V99 COMP-3` | +6666.66 (alt +6667.00 if the division intermediate rounds) | `06 66 66 6C` (alt `06 67 00 0C`) | C; 7 digits, no pad | [H1] **HYPOTHESIS — NOT EXECUTED** |
| V4 | LK-NUM | `PIC S9(3) COMP-3` (2 B) | `00 2C` | +2 | dividend | — | — | — | C; no pad | input |
| V4 | LK-DEN | `PIC S9(3) COMP-3` (2 B) | `00 3C` | +3 | divisor | — | — | — | C; no pad | input |
| V4 | LK-NOTIONAL | `PIC S9(5)V99 COMP-3` (4 B) | `10 00 00 0C` | +10000.00 | factor | — | — | — | C; 7 digits, no pad | input |
| V4 | LK-ACCRUAL | `PIC S9(5)V99 COMP-3` (4 B) | — | — | same COMPUTE as V3; NOTIONAL scale-invariance probe | `PIC S9(5)V99 COMP-3` | +6666.66 (alt +6667.00) | `06 66 66 6C` (alt `06 67 00 0C`) | C; no pad | [H1] **HYPOTHESIS — NOT EXECUTED** |
| V5 | LK-A | `PIC S9(5)V99 COMP-3` (4 B) | `00 01 00 0C` | +10.00 | minuend (all three COMPUTEs) | — | — | — | C; 7 digits, no pad | input |
| V5 | LK-B | `PIC S9(5)V99 COMP-3` (4 B) | `00 10 00 0C` | +100.00 | subtrahend | — | — | — | C; no pad | input |
| V5 | LK-UNSG-TR | `PIC 9(3)V99 COMP-3` (3 B, unsigned) | `12 34 5F` | +123.45 | sentinel-in; receiver of `COMPUTE LK-UNSG-TR = LK-A − LK-B` (**no** SIZE ERROR clause) | `PIC 9(3)V99 COMP-3` | H3: P1 `+90.00` / P2 unchanged / P3 `−90.00`-mag | P1 `09 00 0F` / P2 `12 34 5F` / P3 `09 00 0D` | unsigned: F (P1) / unchanged `5F` (P2) / raw D (P3); 5 digits, no pad | [H3∧H4] **HYPOTHESIS — NOT EXECUTED** |
| V5 | LK-UNSG-SE | `PIC 9(3)V99 COMP-3` (3 B, unsigned) | `12 34 5F` | +123.45 | sentinel-in; receiver of `COMPUTE LK-UNSG-SE = LK-A − LK-B ON SIZE ERROR MOVE 1 TO LK-ERR-FLAG END-COMPUTE` | `PIC 9(3)V99 COMP-3` | H3: unchanged if SE raised / P1 `+90.00` / P3 mag | P2 `12 34 5F` / P1 `09 00 0F` / P3 `09 00 0D` | as above | [H3∧H4] **HYPOTHESIS — NOT EXECUTED** |
| V5 | LK-SIGN-TR | `PIC S9(3)V99 COMP-3` (3 B) | `12 34 5C` | +123.45 | sentinel-in; receiver of `COMPUTE LK-SIGN-TR = LK-A − LK-B` (no ROUNDED) | `PIC S9(3)V99 COMP-3` | −90.00 | `09 00 0D` | D; 5 digits, no pad | [D] |
| V5 | LK-ERR-FLAG | `PIC 9` (1 B, USAGE DISPLAY, unsigned) | `30` | '0' | set to '1' by the SIZE ERROR branch; pre-set `MOVE 0` guarantees `30` at entry regardless of pre-state | `PIC 9` | '0' or '1' | `30` (no SE) / `31` (SE raised) | ASCII, no nibbles | [H3] **HYPOTHESIS — NOT EXECUTED** |
| V6 | LK-A | `PIC S9(5)V99 COMP-3` (4 B) | `00 01 00 0C` | +10.00 | addend | — | — | — | C; no pad | input |
| V6 | LK-B | `PIC S9(5)V99 COMP-3` (4 B) | `00 02 00 0C` | +20.00 | addend | — | — | — | C; no pad | input |
| V6 | LK-SUM | `PIC S9(5)V99 COMP-3` (4 B) | — | — | `COMPUTE LK-SUM = LK-A + LK-B` (no ROUNDED); **owner: Exp-2 / test 2A** | `PIC S9(5)V99 COMP-3` | +30.00 | `00 03 00 0C` | C; no pad | [D] |
| V7 | LK-IN-LEAD | `PIC S9(4)V99 SIGN IS LEADING SEPARATE` (7 B, DISPLAY) | `2D 30 31 32 33 34 35` | −123.45 (leading ASCII `-` + digits "012345") | condition operand and dividend | — | — | — | separate ASCII sign byte; no nibbles | input |
| V7 | LK-OUT-TRAIL | `PIC S9(3)V99 SIGN IS TRAILING SEPARATE` (6 B, DISPLAY) | — | — | `COMPUTE LK-OUT-TRAIL ROUNDED = LK-IN-LEAD / 2` (IF<0 branch); exact −61.725 (scale 3) | `PIC S9(3)V99 SIGN IS TRAILING SEPARATE` | −61.73 (scale-2 cut: next digit 5 → away-from-zero) | `30 36 31 37 33 2D` ("06173−") | trailing ASCII `-` byte | [D] |
| V7 | LK-OUT-UNSG | `PIC 9(4)V99` (6 B, DISPLAY) | — | — | `COMPUTE LK-OUT-UNSG = 0 - LK-IN-LEAD` | `PIC 9(4)V99` | +123.45 | `30 31 32 33 34 35` ("012345") | unsigned DISPLAY, no sign byte | [D] |

**E-13 error register (audit findings, no expected bytes changed):**
1. **Retracted:** Rev 6.1 E-4's claim "Every COMP-3 field in V1–V6 has odd digit count … no vector uses a pad nibble." `LK-FACTOR` (`SV99`, 2 digits = even) carries a **leading pad nibble `0x0`** in `05 5C`. Re-derivation through the pad rule **confirms** the standing interpretation +0.55 and the expected output `00 67 9C` — the arithmetic and bytes were correct; the nibble-level justification was wrong and is now stated correctly.
2. **Re-verified:** E-10's V5 unsigned sentinels `12 34 5F` against the fixture PICTUREs (`PIC 9(3)V99 COMP-3` — unsigned, F nibble) ✓; `LK-SIGN-TR` (`PIC S9(3)V99`) keeps `12 34 5C` ✓; `LK-ERR-FLAG` (`PIC 9`, DISPLAY) is an ASCII byte, never a nibble ✓.
3. All other input decodes and expected outputs re-derived independently and confirmed unchanged.

---

## Deliverable 3 — Correction Matrix

| # | Issue | Resolution |
|---|---|---|
| 1 | `read_proc_slice()` left `*oerr` unwritten on open-success → indeterminate/stale `open_err[]` (stale case real in Mode 'I' via reused locals) | E-12: `*out_len = 0; *oerr = 0; *rerr = 0;` before `open()`; all four call sites audited and confirmed; §5.1a gains the open-fail-bit⇒`open_err==0` consistency check; wire layout/offsets/schema/alignment interface unchanged; no compilation claim made |
| 2 | Full field-level PICTURE audit table absent (only the ownership map was present) | E-13: complete 24-field table above with exact fixture PICTUREs, pad/sign-nibble analysis, receiver PICTUREs, expected decimals/bytes, and confidence classes; pad-nibble claim retracted and corrected; no vector incomplete |

---

## Deliverable 4 — V6 Ownership Cross-Reference Confirmation

**V6 has exactly one owner: Exp-2 / test 2A** (asserts `00 03 00 0C` [D]). Exp-1's input and expected-results statements (Rev 6 E-9(a)) contain no V6 expectation; §3.5 row #6's Exp-1 column remains empty (E-9(b)); Exp-3's use of V1–V7 remains corpus-input-only with no independent V6 expectation (E-9(c)); E-6 §7.1a/§7.2a unchanged. Nothing in E-12 or E-13 alters any ownership. Result: **one owner per vector, V1–V7; zero residual V6 references under Exp-1.**

---

## Deliverable 5 — Remaining Documentation-Level Blockers

1. All gates remain `NOT EXECUTED`; no artifacts exist.
2. Corpus is transcript-anchored only until P0 executes and produces `SHA256SUMS` (E-11; mandatory, fail-stop, unchanged).
3. EVILMOD v3.1 + E-12, and all bespoke C, are **not compiled** by prohibition; `-Werror` cleanliness is an execution-time finding (§2.1.5).
4. All [D] expectations are derived, not executed; all [Hn] items (H1, H3, H4, H5–H8; T2BADBCD's category; kernel x32 regime; Q1–Q9) remain HYPOTHESIS — NOT EXECUTED, recording-only by design.
5. A1–A3 environment assumptions unverified (no VM provisioned).

---

## Deliverable 6 — Final Specification-Readiness Verdict

Both corrections are closed at specification level: the `open_err[]` initialisation hole is fixed and its four call sites verified with an added consumer consistency check, and the field-level PICTURE audit is complete, fixture-faithful (with the pad-nibble rule now correctly applied to `SV99`), and left every expected byte value standing. No unrelated sections were altered; no execution claims were made.

**`READY FOR LIMITED PHASE-0 EXECUTION`**

This verdict concerns specification completeness only. It is not evidence that any experiment ran or passed; all gates remain `NOT EXECUTED` until artifacts exist and are independently reviewed.

`NOT EXECUTED — zero code written, zero files created, zero containers built, zero experiments run, zero results claimed.`
