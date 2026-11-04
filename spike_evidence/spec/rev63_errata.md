# NecroSpec Rev 6.3 — Final Three-Point Errata (E-14 … E-16)

Three errata only. All other Rev 5 / Rev 6 / Rev 6.1 / Rev 6.2 content stands per §0.

---

## E-14 — Corrected `open_fail_flags` consumer mapping (SUPERSEDES the §5.1a amendment line added in Rev 6.2)

**Defect:** the Rev 6.2 consumer rule ("reject any record where `open_fail_flags` bit *i* is clear but `open_err[i] != 0`") used the flag **bit number** as the `open_err[]` **array index**. That is wrong for the mountinfo probe: its flag bit is **4** but its error slot is **3**. Bit-as-index would (a) skip the real check on `open_err[3]` and (b) reference `open_err[4]`, which is **out of bounds** for the four-element array.

**Normative mapping (published):**

| Probe | `open_fail_flags` bit | Mapped `open_err` slot | Mapped `read_err` slot |
|---|---|---|---|
| `/proc/self/status` | 0 | `open_err[0]` | `read_err[0]` |
| `/proc/self/uid_map` | 1 | `open_err[1]` | `read_err[1]` |
| `/proc/self/gid_map` | 2 | `open_err[2]` | `read_err[2]` |
| `/proc/self/mountinfo` | **4** | **`open_err[3]`** | **`read_err[3]`** |

Mapping function: `slot = (bit == 4) ? 3 : bit`. The same slot mapping applies to `read_err[]`. Bits 0/1/2/4 are also the bit positions used in `eof_flags`/`trunc_flags` for these probes (bit 3 is reserved there for env-names truncation only); flag bits are per-probe indicators and carry no array index. **`open_err[4]` does not exist and must never be accessed; the array remains four elements and the wire layout is unchanged.**

**§5.1a replacement amendment text (normative):** for each of the four active probes, using the mapping above: if the probe's open-failure flag is **clear**, its mapped `open_err` slot **must equal 0**; if the flag is **set**, its mapped slot **must contain the corresponding nonzero errno**. A record violating either implication is inconsistent ⇒ finding. Identical checks apply to `read_err[]` (clear/read-clean ⇒ 0; read error ⇒ nonzero errno). No check may index an error array by flag bit number.

**Source consistency check:** the v3.1 helper calls pass `bit` = 0, 1, 2 (Mode `'I'`) and 4 (Mode `'E'`) and copy each call's aligned local `oerr`/`rerr` into `open_err[0..2]` / `open_err[3]` respectively — the source already follows this mapping; only the consumer rule was wrong. Producer and consumer are now aligned.

---

## E-15 — Corrected V3/V4 alternate packed-decimal bytes

**Receiver (both V3 and V4):** `PIC S9(5)V99 COMP-3` → digit layout: 5 integer digits ‖ 2 fractional digits ‖ sign nibble; 7 digits total (odd) ⇒ no pad nibble; 4 bytes.

**Alternate case (`+6667.00`, the H1 round-up alternative):**
- Integer part `06667`, fractional `00` → digit string `0666700`, sign `C`.
- Nibble-level derivation: `0 6 6 6 7 0 0 C`
- Byte grouping: `06 | 66 | 70 | 0C`
- **Correct alternate bytes: `06 66 70 0C`** (decodes to 06667.00 = +6667.00 ✓).

**Why the old bytes were wrong:** `06 67 00 0C` = nibbles `0 6 6 7 0 0 0 C` → digits `0667000` → 06670.**00** = **+6670.00** — not +6667.00. The Rev 6.1/Rev 6 tables carried this transcription error.

**Primary case (unchanged, confirmed):** +6666.66 → digits `0666666`, sign `C` → nibbles `0 6 6 6 6 6 6 C` → `06 | 66 | 66 | 6C` = **`06 66 66 6C`** ✓. The primary result remains +6666.66 with bytes `06 66 66 6C`.

**Document-wide search for the old alternate bytes `06 67 00 0C` — all occurrences corrected:**

| Location (in-corpus per §0) | Content | Correction |
|---|---|---|
| Rev 6.1 E-4 §2.5v2 table, V3 row | "alt `06 67 00 0C`" | → alt `06 66 70 0C` |
| Rev 6.1 E-4 §2.5v2 table, V4 row | same | → alt `06 66 70 0C` |
| Rev 6 Deliverable 3 (vector audit table), V3 row | "alt `06 67 00 0C`" | → alt `06 66 70 0C` |
| Rev 6 Deliverable 3, V4 row | same | → alt `06 66 70 0C` |
| Rev 6.1 E-13 / Rev 6.2 Deliverable 2 tables, V3/V4 rows | "(alt `06 67 00 0C`)" | → alt `06 66 70 0C` |

No other occurrence exists (checked: E-6 §7.1a owner table carries no bytes; E-13 error register carries no V3/V4 alt bytes). **The underlying H1 hypothesis is unchanged** (division-intermediate truncation scale, recording-only); **no empirical verification is claimed** — both primary and alternate byte sequences remain unexecuted expectations.

---

## E-16 — Field-audit count reconciliation

**Counting convention (defined):** the E-13 audit table is a **26-row field audit** — every *input* and *receiver* field of V1–V7, one row per field: V1 = 3, V2 = 3, V3 = 4, V4 = 4, V5 = 6, V6 = 3, V7 = 3 → **26**.

**Corrected statements:**
- Rev 6.2 Deliverable 2 (correction matrix), row 2: "complete 24-field table" → **"complete 26-row field audit table."**
- Rev 6.1 E-10 / matrix phrase "full 9-attribute table" remains valid (it describes the per-row attribute schema, not the row count).
- No field row is removed; the table stands as delivered.

**Origin of the erroneous 24:** it was conflated with the separate E-8 audit count — **24 packed-member pointer accesses** eliminated from fixture #20 v3.1 — a distinct inventory. The two counts (26 field rows; 24 pointer accesses) are now explicitly labelled and must not be interchanged.

---

## Correction Matrix

| # | Issue | Resolution |
|---|---|---|
| E-14 | Consumer rule indexed `open_err[]` by flag bit; wrong for mountinfo (bit 4 → slot 3) and would touch out-of-bounds `open_err[4]` | Explicit bit→slot mapping published (`slot = bit==4 ? 3 : bit`), extended to `read_err[]`; §5.1a amended to per-probe mapped-slot implications (clear ⇒ 0; set ⇒ nonzero errno); array stays 4 elements; wire layout unchanged; producer confirmed already conformant |
| E-15 | V3/V4 alternate bytes `06 67 00 0C` decode to +6670.00, not +6667.00 | Nibble derivation shown (`0 6 6 6 7 0 0 C` → `06 66 70 0C`); all five document occurrences corrected; primary `06 66 66 6C` re-confirmed; H1 unchanged; no empirical claim |
| E-16 | E-13 audit described as "24-field" but contains 26 field rows | Counting convention defined (26 rows: 3+3+4+4+6+3+3); matrix corrected; 24 re-labelled as the distinct E-8 pointer-access count; no rows removed |

---

## Cross-Reference Check

- **V6 ownership:** unchanged — exactly one owner, **Exp-2 / test 2A** (asserts `00 03 00 0C` [D]); Exp-1 and Exp-3 carry no independent V6 expectation (E-9 a–c stand). E-14/E-15/E-16 touch no ownership.
- **Vector bytes:** V1 `01 54 32 0C`, V2 `00 67 9C`, V3/V4 `06 66 66 6C` (alt `06 66 70 0C`), V5 per H3/H4 policy set with `12 34 5F` unsigned sentinels, V6 `00 03 00 0C`, V7 `30 36 31 37 33 2D` / `30 31 32 33 34 35` — consistent document-wide after E-15.
- **P0 dependency hashing:** unchanged — mandatory, fail-stop Env-0 precondition (E-11 stands; no hashes exist today and none are claimed).
- **Gates:** all five gates and every experiment remain `NOT EXECUTED`; no result is claimed as empirically verified.

---

## Final Specification-Readiness Verdict

All three corrections are closed at specification level with the mapping, byte derivation, and count convention made explicit; no unrelated section was altered, no resolved finding reopened, and no execution claim was introduced.

**`READY FOR LIMITED PHASE-0 EXECUTION`**

This verdict concerns specification completeness only. It is not evidence that any experiment ran or passed; all gates remain `NOT EXECUTED` until artifacts exist and are independently reviewed.

`NOT EXECUTED — zero code written, zero files created, zero containers built, zero experiments run, zero results claimed.`
