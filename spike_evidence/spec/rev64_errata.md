# NecroSpec Rev 6.4 — Consolidated Specification Correction and Closure Audit (F-01 … F-13)

## 1. Purpose and authority of Rev6.4

Rev6.4 is a **new superseding normative layer** over the published NecroSpec corpus (`rev4_extract.md` → `rev5.md` → `rev6_errata.md` → `rev61_errata.md` → `rev62_errata.md` → `rev63_errata.md`). It resolves independent-review findings **F-01 through F-13**, reconciles cross-references, and tightens honesty constraints on security and evidence claims. Rules:

1. Rev6.4 supersedes only the statements explicitly listed in §4 (supersession table). Everything else in the corpus remains normative in the consumption order above, with Rev6.4 controlling on conflict.
2. Rev6.4 is **documentation-only**. It creates no executable code, fixtures, harnesses, containers, or results. Any code-like fragment herein is an **illustrative specification fragment** defining an exact requirement — to be materialized (if at all) during a future authorized implementation phase, never by this pass.
3. Where Rev6.4 makes a design choice, it is labeled **"[Rev6.4 design decision — new, not historical]"** and is presented as a normative choice of this layer, never as a pre-existing fact.
4. Where correctness depends on unexecuted experiments, statements are labeled **Unverified** / **HYPOTHESIS — NOT EXECUTED**. No test result, timing, gate pass, or compiler behavior is claimed.
5. The P0 disposition is **not** affected by Rev6.4 (see §12).

## 2. Historical-document preservation statement

The twelve historical publication artifacts (`spike_evidence/README.md`, `PUBLICATION_SHA256SUMS`, `spec/rev4_extract.md`, `spec/rev5.md`, `spec/rev6_errata.md`, `spec/rev61_errata.md`, `spec/rev62_errata.md`, `spec/rev63_errata.md`, `spec/SHA256SUMS`, `spec/preexec_checks.md`, `env0/spec_manifest.json`, `env0/p0_disposition_amendment.json`) were verified **before** this work (`sha256sum -c` over both manifests: 11/11 and 6/6 OK at commit `d41b66caa99e034dfdf6e00159e018ec8dca5a71`) and re-verified **after** this work (results recorded in the Rev6.4 report and reproducible from `PUBLICATION_SHA256SUMS` at any time). No historical file was edited, re-encoded, re-flowed, or re-hashed; their `TRANSCRIPT-DERIVED COPY` classification is retained; their manifests are unchanged. Historical text that Rev6.4 corrects remains physically present and is **superseded for normative use only** (see F-07 §3).

## 3. Findings F-01 through F-13 — exact normative corrections

### F-01 — Stage-2 executable shared-memory mapping (`shmat`/`SHM_EXEC`)

**Supersedes:** the implicit Stage-2 completeness claim in Rev 5 §6 / Rev 6 E-2 (a Stage-2 policy without a SysV-shared-memory rule must not be described as comprehensive against executable-memory creation).

**Verified platform facts (source-verified 2026-11-04, torvalds/linux master):**
- UAPI header `include/uapi/linux/shm.h`: `#define SHM_EXEC 0100000 /* execution access */` → **SHM_EXEC = 0o100000 = 32768 = 0x8000**. (Same header: `SHM_RDONLY`=0o10000, `SHM_RND`=0o20000, `SHM_REMAP`=0o40000.)
- x86_64 syscall table (`arch/x86/entry/syscalls/syscall_64.tbl`): `30 common shmat sys_shmat` (29 = `shmget`, 31 = `shmctl`, 67 = `shmdt`). Exact syscall name: **`shmat`**.
- Kernel entry (`ipc/shm.c`): `SYSCALL_DEFINE3(shmat, int, shmid, char __user *, shmaddr, int, shmflg)` — current x86_64 layout is 3-argument with the attach address returned in the syscall return value. Historic x86_64 kernels used a 4-argument layout `(shmid, shmaddr, shmflg, raddr_out)`. **Under both layouts `shmflg` is argument index 2 (0-based)**; the masked rule below is therefore invariant to which layout the running kernel implements. The rule is additionally **empirically self-falsifiable**: if `shmflg` were not arg 2 on the running kernel, test 4H-5 (on-mode) would return a header instead of killing, which is a defined FAIL (§6).

**[Rev6.4 design decision — new, not historical]** Stage-2 **denies `shmat()` calls whose `shmflg` includes `SHM_EXEC`, and permits ordinary attachments**:

```
seccomp_rule_add_array(ctx2, SCMP_ACT_KILL_PROCESS, syscall(__NR_shmat), 1,
    SCMP_CMP(2 /* arg index of shmflg */, SCMP_CMP_MASKED_EQ,
             0x8000ULL /* mask = SHM_EXEC */, 0x8000ULL /* value */));
```

1. Exact syscall name: `shmat`; argument layout as verified above; `shmflg` = argument index **2**.
2. Comparison: `SCMP_CMP_MASKED_EQ`, `arg=2`, `datum_a = 0x8000 (SHM_EXEC)`, `datum_b = 0x8000` — matches any attachment whose flags carry the execute bit regardless of other bits.
3. Configured action for a denied call: `SCMP_ACT_KILL_PROCESS` (consistent with all other Stage-2 deny rules) → kernel SIGSYS-kill → headerless worker death → outer `bwrap` exit `159`.
4. Ordinary (non-`SHM_EXEC`) `shmat()` is **allowed** by Stage-2 (falls through to the allow default), covered by control 4H-6.
5. If the syscall name cannot be resolved (`seccomp_syscall_resolve_name("shmat") < 0`) or the rule cannot be added/represented on the target architecture (non-zero `seccomp_rule_add_array`), the existing fail-closed policy applies unchanged: `INIT_ACK(init_status=-4)`, `_exit(16)`, run class `FAILED_SANDBOX_INIT`. The rule is never silently skipped.
6. **Completeness restatement:** with `shmat`/`SHM_EXEC` added, the Stage-2 executable-memory coverage set is: `memfd_create` (all), `mmap`/`mprotect`/`pkey_mprotect` (executable bit, masked), `shmat` (`SHM_EXEC`, masked). Mechanisms explicitly outside this set and their status: `mremap` cannot create executability not already present (recorded rationale, observational); `open(O) + mmap(PROT_EXEC)` of a staged file is blocked by the masked `mmap` rule; `uselib` is denied in **Stage 1**. The word "comprehensive" may only be used after Exp-4A census confirms no additional exec-creation mechanism in the observed steady state (open item Q8, unchanged).
7. Stage-1 remains unchanged: `shmat` is **not** restricted in Stage-1 (loaders do not use SysV shm; restriction would serve no constructor-window purpose).

**Required future tests (specified now, implemented only in an authorized execution phase):** see §6 rows 4H-5 and 4H-6, including the off-mode control, the non-executable control, and the INCONCLUSIVE classification when a host/kernel restriction prevents the off-control from demonstrating attachment (e.g., SysV shm unavailable) — such an outcome is **never** evidence of enforcement.

### F-02 — `CMD_CALL.reset_flag` fully defined

**Supersedes:** any undefined reading of `reset_flag` in Rev 5 §2.3.2. The field is **retained** (not removed) — Exp-3 3C's `cob_cancel` sequencing requires a worker-side reset mechanism. All statements below are **[Rev6.4 design decision — new, not historical]**.

| Property | Normative definition |
|---|---|
| Wire representation | `u8 reset_flag`, first byte of the `CMD_CALL` payload (existing offset); little-endian trivially (single byte). |
| Valid values | `0` = preserve state (perform the call as-is). `1` = reset the called program's state before the call. |
| Zero meaning | `0` ⇒ **preserve**: no cancel, no re-resolve; exactly the Rev 5 behavior. |
| Does reset invoke `cob_cancel()`? | Yes: worker calls `cob_cancel(prog_name)` for the named program only. With `physical_cancel no` (Rev 5 §4.2 config), the program is logically canceled and re-initialized on next activation; the exact libcob behavior is **Unverified** until Exp-3 records it. |
| Cancel vs argument validation | Reset occurs **after** full frame validation (§7 validation order) and **before** entry re-resolution and the call. |
| Cancel vs program call | Reset is strictly **before** the call. |
| Scope | The **single named program** of this `CMD_CALL`. Not worker-global; there is no all-programs reset. |
| Interaction with `IS INITIAL` | For an `IS INITIAL` program (T3INIT), `reset_flag=1` is semantically a no-op (per-activation re-init already guaranteed); it remains valid and MUST NOT fail. |
| Interaction with sticky linkage | `cob_cancel` does not touch caller-owned LINKAGE buffers; bytes passed in by the supervisor are unaffected. Whether libcob clears internal entry/linkage bookkeeping is **Unverified** (Exp-3 records it). |
| Interaction with EXTERNAL state | None possible: the NVS-0 grammar rejects `EXTERNAL` (Rev 4 §2.2.2 reserved list). EXTERNAL state is **out of scope by construction**. |
| Invalid values | Any value ≥ 2 is a worker-side semantic protocol fault: no `CALL_ACK`, `close(4)`, `_exit(11)` (new worker exit code; see §7). Supervisor classifies the run `FAILED_PROTOCOL`. |
| Reset failure | If `cob_cancel(prog_name) != 0`: worker emits `CALL_ACK{cob_call_ret=-2, outcome_cat=CAT_FATAL_ERROR(3), tainted=1, err="RESET_FAILED"}`, flushes, `close(4)`, `_exit(10)`; supervisor replaces the worker. Evidence must label this **worker-operational** (F-10 Class B-adjacent), not module-originated. Whether libcob can fail cancel in this flow is **Unverified**. |
| Taint / replacement | Reset failure taints the worker ⇒ process replacement required (exit-10 path). A successful reset does **not** taint. |

**Reset is a request, never proof:** no pass criterion may treat `reset_flag=1` as evidence that state was actually reset. Exp-3 MUST compare observable program state before and after (bytes of `LK-OUT-VAL`/`LK-OUT-UNIN`), per the sequences defined in F-11.

**Required state-transition observations (Exp-3, all recorded not asserted):** (a) T3STATE `step=1` repeated ×10 with `reset_flag=0` ⇒ sticky accumulation pattern recorded; (b) fresh worker, T3STATE call with `reset_flag=1` ⇒ first-call value recorded; (c) T3STATE ×3 (`reset_flag=0`), then `reset_flag=1` with `step=1` ⇒ post-reset value recorded and compared against the pre-reset series (returned-to-base or not — H5/cancel-semantics disposition); (d) T3INIT ×3 with `reset_flag=1` ⇒ constant per-activation values recorded.

### F-03 — Exp-2 outcome categories: honest coverage and gate revision

**Supersedes:** Rev 5 §7.2 "Expected" (all five categories required) and the corresponding Rev 5 §9 Exp-2 pass criterion. The GnuCOBOL return mapping is restated unchanged (documented API): `0` normal, `1` STOP RUN, `-1` error exit, `-2` hard error exit, `-3` signal-handler exit.

| Category | Ret | Fixture / test | Determinism | Worker exit behavior | Protocol response | Taint | Gate-mandatory? |
|---|---|---|---|---|---|---|---|
| CAT_OK | 0 | **2A** T2MULTI (V6) | Deterministic by design | continues; `_exit(0)` on QUIT | `CALL_ACK{0,cat=0,tainted=0}` bytes = V6 | no | **YES** — deterministic fixture; exact observation: `cob_call_ret=0`, `outcome_cat=0`, `tainted=0`, output bytes `00 03 00 0C`. |
| CAT_STOP_RUN | 1 | **2D** T2STOP | Deterministic by design (STOP RUN unambiguous); exit code **42** is expected-**Unverified** | flush `CALL_ACK`, `close(4)`, `_exit(10)` | `CALL_ACK{ret=1,cat=1,exit_code=42,tainted=1}` | yes | **YES** — deterministic fixture; the value 42 is recorded-not-asserted. |
| CAT_RUNTIME_ERROR | -1 | **2E** T2BADBCD | **HYPOTHESIS — NOT EXECUTED** (−1 vs −2 vs silent repair/zero-read) | if categorized error: flush + `_exit(10)`; recorded verbatim otherwise | recorded `CALL_ACK` or process death, verbatim | yes if error path | **NO** — 2E is mandatory as a *recorded-outcome* test with hypothesis disposition; category coverage is **not** a gate criterion. |
| CAT_FATAL_ERROR | -2 | none controlled | — | — | — | — | **NO — unverified/optional.** No controlled fixture exists; not required for gate PASS. |
| CAT_SIGNAL_CAUGHT | -3 | none controlled | — | — | — | — | **NO — unverified/optional.** Not required for gate PASS. |
| PROCESS_DEATH (not a CAT_*) | n/a | **2F-L1** T2CRASH, **2F-L2** EVILMOD 'K' | **H6 HYPOTHESIS — NOT EXECUTED** (libcob-trapped −2/−3 vs SIGSEGV death 139) | death or exit-10 path | none, or category per H6 | yes | **YES as a recorded-outcome probe** (outcome with H6 disposition), explicitly **not** as category coverage. T2CRASH is kept distinct from the GnuCOBOL return categories: it tests process-level termination *or* an exceptional libcob conversion — whichever occurs is recorded. |

**Revised Exp-2 gate criterion (normative):** PASS requires (a) full protocol-fault battery rejection, (b) `CAT_OK` and `CAT_STOP_RUN` deterministically observed with the exact observations above, (c) canonical binding enforcement, (d) 4B = `-2`/exit 12, (e) 2F outcomes recorded with H6 disposition, (f) 2E outcome recorded with hypothesis disposition. Categories −1/−2/−3 are recorded-if-observed and are labeled **UNVERIFIED-CLASS observations** in evidence; absence is not a failure and presence is not asserted by this specification. No result is fabricated by this text.

### F-04 — Grammar-to-semantics table (no accepted production without defined semantics)

**Supersedes:** the implicit claim that parser acceptance implies defined reference-model semantics. **No subset expansion.** All productions below are already accepted by the Rev 4 grammar; each now has normative reference-model semantics. Conventions: exact rational intermediates (`fractions.Fraction`); single rounding point at receiver store; truncation toward zero unless `ROUNDED` (half-away-from-zero); receiver capacity = (I,F) of its expanded PICTURE; size error ⇔ the rounded-or-truncated integer part does not fit in I digits. GnuCOBOL-specific points are H-tagged (recording-only).

| Production | Operand evaluation order | Intermediate / precision | Operation semantics | Receiver conversion & storage | Rounding point | Size-error condition | Receiver on size error | Reference-model (Python) | Compiler-oracle comparison duty |
|---|---|---|---|---|---|---|---|---|---|
| `MOVE atom TO id+` | Source evaluated once; receivers stored in listed order | exact rational of source | source value replicated to each receiver | per-receiver rescale to (I,F); sign conversion per receiver codec | truncation (grammar has no `ROUNDED` on MOVE) | per-receiver, evaluated per store | with clause: that receiver unchanged, body runs; else H3 | `store(store_src, recv)` per receiver in order | per-receiver byte compare (3E) |
| `COMPUTE t ROUNDED? = expr` (plain/se) | expr evaluated by precedence (parens > unary ± > * / > + −) | exact rational at every step; division exact (**H1** governs whether GnuCOBOL truncates division intermediates — recorded via V3/V4) | arithmetic expression | single store to t | at store only (if `ROUNDED`) | after exact value computed | ON: t unchanged + ON-body; NOT-ON body iff no SE; no clause: **H3** | direct AST evaluation with `Fraction` | V1–V5, V7 + 3E corpus |
| `ADD a+ TO t` | all addends evaluated, then receiver's **pre-store** value | exact rational sum | t_new = t_old + Σa_i (in-place) | single store to t | at store | on t_new overflow | as COMPUTE | sum then store | 3E |
| `ADD a+ GIVING t` | addends only (t is not an operand) | exact rational sum | t = Σa_i | single store | at store | on t_new overflow | as COMPUTE | sum then store | 3E |
| `SUBTRACT a+ FROM t` | addends, then receiver pre-store | exact rational | t_new = t_old − Σa_i (in-place) | single store | at store | as above | as COMPUTE | difference then store | 3E |
| `SUBTRACT a FROM b GIVING t` | a then b (b is minuend) | exact rational | t = b − a (exactly two operands per grammar) | single store | at store | as above | as COMPUTE | subtract then store | 3E |
| `MULTIPLY a BY b GIVING t` | a then b | exact rational product | t = a × b (GIVING form only; in-place MULTIPLY is **not** in the grammar and is therefore unsupported by construction) | single store | at store | as above | as COMPUTE | product then store | 3E |
| `DIVIDE x INTO y GIVING t` | x then y | exact rational quotient (division by zero ⇒ runtime error; category mapping is **H9 HYPOTHESIS — NOT EXECUTED**, recorded) | t = y ÷ x | single store | at store | as above | as COMPUTE | divide then store | 3E; zero-divide case recorded |
| `DIVIDE x BY y GIVING t` | x then y | as above | t = x ÷ y | single store | at store | as above | as COMPUTE | divide then store | 3E |
| `ROUNDED` (in `target_spec`) | — | — | applies to the single receiver of its statement | half-away-from-zero at receiver scale | the single rounding point | evaluated on the rounded value | — | `round_half_away(frac, F)` | boundary vectors (F-11) target the half-case |
| `ON SIZE ERROR stmt+` / `NOT ON SIZE ERROR stmt+` | clause bodies are ordinary statement lists | — | ON-body executes iff its statement incurred SE; NOT-ON-body iff not; scope is exactly the one preceding arithmetic statement | — | — | — | — | conditional execution flags | mutants M1/M2 + 3E |
| multiple operands (`ADD a1 a2 …`) | listed order (irrelevant under exact arithmetic; recorded for tracing) | exact | n-ary sum/difference | — | — | — | — | `sum(...)` | 3E |
| multiple receivers | only `MOVE … TO id+` has them | — | sequential independent stores | each receiver independent (own rescale, own SE) | per receiver | per receiver | per receiver | loop of stores | 3E multi-receiver vectors |
| in-place vs separate receivers | in-place (`ADD…TO`, `SUBTRACT…FROM`) read the pre-store receiver; separate forms never read the receiver | — | as above | — | — | — | — | explicit `old = recv` read | 3E |
| signed / unsigned receivers | — | — | sign conversion at store | signed: C/D nibble per §2.4 rule 2; unsigned: **H4** nibble (F expected); negative-into-unsigned = **H3 ∧ H4** policy set P1/P2/P3 (Rev 6.1 E-13 §2.5.1, unchanged) | — | unsigned negative may or may not be SE per H3 | per policy set | codec with policy | V5 + 3E |
| unary signs / parentheses (`factor`) | recursive | exact | standard precedence; unary minus applies to its factor only | — | — | — | — | recursive-descent over AST | 3E |
| group-item storage | — | — | **rejected at Layer 4** (`ERR_NON_ELEMENTARY_TARGET`): groups never appear as receivers or arithmetic operands, so no group storage semantics exist **by construction** | — | — | — | — | unreachable | rejection unit test |
| inherited `USAGE` | — | — | group USAGE propagates to elementary children (Rev 5 Layer 4) | elementary codec = propagated usage (COMP-3 per §2.4 rule 2; DISPLAY per rule 3) | — | — | — | codec selection from propagated usage | 3E |
| `IF cond … END-IF` | cond operands evaluated | exact rational | six comparison operators; branch statement lists executed in order | — | — | — | — | boolean select | V7 + 3E |
| `GOBACK` | — | — | program ends; normal-return path (category per F-03 table) | — | — | — | — | halt | 2A/2D |

**Explicit rejections (already enforced, restated so acceptance ≠ support):** group receivers, in-place MULTIPLY/DIVIDE, REMAINDER division, overpunch DISPLAY, multi-result division, `ON SIZE ERROR` without terminal `END-*`. The reference model supports **only** the productions above.

### F-05 — Canonical staging sequence

**Supersedes:** the Rev 5 §4.3 ordering sentence ("staging → chmod → sentinel creation → worker launch"), which contradicted the `/stage/root_only_secret.txt` row (create before chmod). The canonical sequence is confirmed and fixed (**[Rev6.4 design decision]** — the directive-proposed order is adopted after evaluation: files cannot be created after a read-only lock, and hashes must cover final content):

1. *(host, root)* Create the staging directory `/var/lib/necro-stage/$UUID`.
2. *(host, root)* Stage the module (`<MOD>.so`, mode `0444`).
3. *(host, root)* Create the required sentinel files: `/stage/root_only_secret.txt` (mode `0600`, root:root, 64 random bytes) **inside the stage dir**; and the host `/tmp/host_gateway_secret.txt` isolation sentinel (mode `0600`, root:root) **outside** the stage dir (host `/tmp`; its position here is for manifest completeness — it is never in the staged directory).
4. *(host, root)* Verify the complete staged-file inventory and expected permissions (`stat` each entry).
5. *(host, root)* Compute and record the staging manifest + SHA-256 hashes (`staging_manifest.json`).
6. *(host, root)* Apply final read-only permissions to the staging directory and its contents (dir `0555`, files `0444`, secret `0600`).
7. *(host, root)* Verify final permissions and read-only behavior (`stat` re-check; creation-attempt denial).
8. *(host, root)* Launch the worker (`bwrap` profile §4.4 + E-1).
9. *(worker, uid 10001, inside sandbox)* Perform the in-worker verification required by the loader design: L1 = read `canon_path`, verify SHA-256, `cob_resolve`; L2 = open, `memfd` copy/hash/seal, `dlopen`/`dlsym`; plus `INIT_ACK` workdir proof (§4.1).

**Immutability honesty:** step 6 enforces **DAC only**. Mount-level immutability comes solely from the `--ro-bind` + `--remount-ro /` bwrap profile (and L2's kernel `F_ADD_SEALS` seal after copy); chmod alone does **not** make any mount immutable. No later corpus section may reverse this order; the E-11/P0 records and staging-manifest evidence must reference this sequence.

### F-06 — Rev4 fixture dependency inventory reconciled to #1–#20

**Supersedes:** the "#1–#19" inventory ranges in Rev 6 E-0 §0.1 ("fixture sources #1–#19") and Rev 6.1 E-11 step 2 (verified at `rev61_errata.md` line 247; E-0 occurrence at `rev6_errata.md` §0.1). Historical documents are unchanged; those references are **superseded for normative use**. Correct dependency inventory: **Rev 4 §2.2.2 and §3.1–§3.3 = fixtures #1–#20**.

| # | Name | Source type | Owner experiment(s) | Purpose | Class | Source present in corpus? |
|---|---|---|---|---|---|---|
| 1 | EX1FEE | COBOL | Exp-1 (V1); Exp-3 3E | multiplication/truncation | positive | ✓ `rev4_extract.md` §3.1 |
| 2 | EX2RND | COBOL | Exp-1 (V2); 3E | ROUNDED half-case | positive | ✓ |
| 3 | EX3DIVA | COBOL | Exp-1 (V3); 3E | division-intermediate (H1) | positive | ✓ |
| 4 | EX3DIVB | COBOL | Exp-1 (V4); 3E | H1 scale-invariance | positive | ✓ |
| 5 | EX4UNSG | COBOL | Exp-1 (V5); 3E | unsigned/size-error policies (H3/H4) | positive | ✓ |
| 6 | T2MULTI | COBOL | **Exp-2 2A (V6 owner)**; 3E corpus | basic call parity | positive | ✓ |
| 7 | CALC-FEE | COBOL | Exp-3 3E; lexer/AST positive | hyphenated identifiers | positive | ✓ |
| 8 | T2BADBCD | COBOL | Exp-2 2E | invalid-packed path (hypothesis) | positive (valid source exercising error path) | ✓ |
| 9 | T3STATE | COBOL | Exp-3 3B/3C/3D | sticky WS state | positive | ✓ |
| 10 | T3INIT | COBOL | Exp-3 3C | `IS INITIAL` re-init | positive | ✓ |
| 11 | T3STICKY | COBOL | Exp-3 3D (H7) | omitted-USING probe | positive | ✓ |
| 12 | T3DISP | COBOL | Exp-1 (V7); 3E | sign-separate DISPLAY codecs | positive | ✓ |
| 13 | T2STOP | COBOL | Exp-2 2D; Exp-3 rejection tuple | reserved-word/STOP RUN rejection; STOP RUN category | negative (valid GnuCOBOL, invalid NVS-0) | ✓ `rev4_extract.md` §3.2 |
| 14 | T2CRASH | COBOL | Exp-2 2F-L1; Exp-3 rejection tuple | `CALL` rejection; H6 probe | negative (as above) | ✓ |
| 15 | NEG_COL73 | COBOL | Exp-3 tuple | col-73 preflight rejection | negative | ✓ |
| 16 | NEG_BADIND | COBOL | Exp-3 tuple | col-7 indicator rejection | negative | ✓ |
| 17 | NEG_PIC19 | COBOL | Exp-3 tuple | 19-digit AST rejection | negative | ✓ |
| 18 | NEG_UNTERM_SE | COBOL | Exp-3 tuple | missing END-COMPUTE rejection | negative | ✓ |
| 19 | crash_helper.c | C | Exp-2 2F-L1 (linked into #14 via `-K crash_now`) | native crash helper | helper | ✓ `rev4_extract.md` §3.3 |
| 20 | EVILMOD.c | C | Exp-2 2F-L2; Exp-4 4B–4H | sandbox/diagnostic probe module | helper/probe | ✓ **two versions**: v1 in `rev4_extract.md` (historical); **controlling = v3.1 + E-12** in `rev61_errata.md`/`rev62_errata.md`; the F-01/F-09/F-10 Mode `'M'`/`'P'` extensions are **specified here, not yet materialized** — no claim that the extended source exists |

Count: 20/20 sources present in the published corpus (with #20's version multiplicity stated). No source file is claimed present merely because its name appears in an inventory.

### F-07 — Rev6.3 E-15 cross-references and correction language

**Supersedes (in Rev6.3 E-15 only):** (a) its citation "Rev 6.1 E-4 §2.5v2 table" — E-4 belongs to **Rev 6** (`rev6_errata.md`); (b) its citation "Rev 6.1 E-13 / Rev 6.2 Deliverable 2 tables" — E-13 belongs to **Rev 6.2** (`rev62_errata.md`); (c) its phrase "all five document occurrences corrected" as physical edits — no historical file was edited. Corrected reference map: old alternate bytes live at **`rev6_errata.md` lines 293, 294, 379, 380 (4×)** and **`rev62_errata.md` lines 73, 77 (2×)**; `rev61_errata.md` contains **0** occurrences; `rev63_errata.md` contains **6** occurrences, all inside E-15's own correction/citation table (legitimate historical citation). **Historical preservation ≠ normative correction:** the old literals remain physically present (preserved, as-emitted) and are **superseded for normative use**; they must never control interpretation. Canonical, restated: V3/V4 primary output = **+6666.66 → `06 66 66 6C`**; alternate (division-intermediate rounds up) = **+6667.00 → `06 66 70 0C`** (nibbles `0 6 6 6 7 0 0 C`). Both remain **HYPOTHESIS — NOT EXECUTED**: the arithmetic result and the actual compiler behavior are empirically unverified until Exp-1 records them.

### F-08 — One canonical module-name grammar for L1 and L2

**Supersedes:** Rev 5 §2.3.3's L1 regex (`^[A-Z0-9][A-Z0-9-]{0,30}$`, per its prose) and L2 regex (`^[A-Za-z0-9][A-Za-z0-9_]{0,30}$`) as a mismatched pair. **[Rev6.4 design decision]** — one grammar, both loaders:

1. Canonical grammar: `^[A-Z0-9][A-Z0-9-]{0,30}$` **with no trailing hyphen** (effective max length 31).
2. First character: uppercase ASCII letter or digit. Subsequent: uppercase ASCII letters, digits, interior hyphens.
3. Case handling: **case-sensitive; no normalization** — lowercase input is rejected, never folded.
4. Underscores: **rejected**. Hyphens: **allowed, interior only** (no leading/trailing).
5. Rejected by construction (charset + anchoring): path separators `/`, `\`; dots; whitespace; all Unicode ≥ 0x80; all control characters; empty string.
6. Validation order: the supplied `name` is validated **before** canonicalization; canonicalization is then the pure function `canon_path = "/stage/" + name + ".so"`; the supplied `path` is compared to `canon_path` by exact byte equality; mismatch ⇒ `INIT_ACK(-1)`, `_exit(14)` before any open/hash/resolve (unchanged).
7. Path mapping: only the function above; no search path beyond `COB_LIBRARY_PATH=/stage` (unchanged context).
8. L1↔L2 proof of sameness: both loaders embed the **identical grammar literal** (single normative regex + trailing-hyphen rule, this section), and Exp-2's canonical-binding battery is extended: every negative example below is sent to **both** loaders and both MUST reject identically (`INIT_ACK(-1)`, exit 14, no file opened). Any divergence is a gate FAIL.
9. Positive examples: `T2MULTI`, `CALC-FEE`, `EVILMOD`. Negative examples: `t2multi` (lowercase), `T2_MULTI` (underscore), `-T2` (leading hyphen), `T2-` (trailing hyphen), `A.B` (dot), `A/B` (separator), `A B` (space), `ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456` (32 chars).
10. Note: the L2 exported **symbol** `necro_plugin_entry` is a symbol name, not a module name; it is unaffected.

### F-09 — Stage-2-specific syscall test matrix

**Supersedes:** any reading of Rev 5 §5.3 as covering Stage-2-specific restrictions. All rows below are **Stage-2-specific** (Stage-1 deliberately permits these mechanisms per Rev 5 §6; therefore an on-mode denial is attributable to Stage-2 by policy construction, and the rows also satisfy the Stage-1/Stage-2 distinction requirement). Probes **4H-1…4H-6** (EVILMOD Mode `'M'`, sub 1…6 — future hook; illustrative fragment only):

```c
/* Spec fragment — NOT created as implementation by Rev6.4. Mode 'M' probes. */
case 1: fd = syscall(SYS_memfd_create, "p", 0); if (fd>=0) close(fd); break;              /* 4H-1 */
case 2: p = mmap(NULL, 4096, PROT_READ|PROT_WRITE|PROT_EXEC,
                 MAP_PRIVATE|MAP_ANONYMOUS, -1, 0); if (p!=MAP_FAILED) munmap(p,4096); break; /* 4H-2 */
case 3: p = mmap(NULL, 4096, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
        if (p!=MAP_FAILED) { r = mprotect(p, 4096, PROT_READ|PROT_EXEC); rec(r); munmap(p,4096);} break; /* 4H-3 */
case 4: r = pkey_mprotect(p, 4096, PROT_READ|PROT_EXEC, -1); break;                        /* 4H-4 */
case 5: id = shmget(IPC_PRIVATE, 4096, 0600); a = shmat(id, NULL, SHM_EXEC); rec(a); …; break; /* 4H-5 */
case 6: id = shmget(IPC_PRIVATE, 4096, 0600); a = shmat(id, NULL, 0); …; break;            /* 4H-6 */
```

| Probe | Exact syscall | Arg index / mask / comparison | Host capability / kernel support | Preconditions | seccomp=**off** expected (control) | seccomp=**on** expected | Unsupported / host-restricted classification | Outcome type |
|---|---|---|---|---|---|---|---|---|
| 4H-1 | `memfd_create` | n/a (deny-all rule, no comparison) | kernel ≥ 3.17 | worker in READY (Stage-2 loaded) | header `rc[0]=0` (fd created, closed) — operation **available** | headerless death, bwrap **159** | off-mode ENOSYS ⇒ `CONTROL-UNAVAILABLE` ⇒ on-run **INCONCLUSIVE**, never enforcement evidence | SIGSYS |
| 4H-2 | `mmap` | arg 2, `MASKED_EQ`, mask `PROT_EXEC=0x4`, value `0x4` | standard | 4H-1 style READY state | `rc[0]=0` (executable mapping created where host policy permits) | headerless death, **159** | off-mode EPERM/ENOSYS (e.g. `vm.mmap_rwx_bits` host policy) ⇒ control grade recorded; on-kill still counts as filter action (entry gate) but a *mechanism-prevention* claim requires CONTROL-STRONG | SIGSYS |
| 4H-3 | `mprotect` | arg 2, `MASKED_EQ`, `0x4`, `0x4` | standard | mmap(RW) of 4H-3 must succeed first (`rc[1]=0`) | `rc[1]=0` (RW map), `rc[0]=0` (RX conversion where permitted) | death at the `mprotect` call, **159** | as 4H-2 | SIGSYS |
| 4H-4 | `pkey_mprotect` | arg 2, `MASKED_EQ`, `0x4`, `0x4` | syscall ≥ kernel 4.9; full function needs PKU CPU feature | 4H-3's RW map reused | `rc[0]=0` where PKU present; **otherwise** recorded errno (`ENOSYS`/`EINVAL`/`EPERM`) — grade `CONTROL-ENTRY` (call entered and returned) at best | death at entry, **159** (entry gate fires before hardware support matters) | no PKU ⇒ off-mode is `CONTROL-ENTRY` only; a mechanism-prevention claim for pkey is **not** made | SIGSYS |
| 4H-5 | `shmat` | arg 2, `MASKED_EQ`, mask `SHM_EXEC=0x8000`, value `0x8000` | SysV shm available (`shmget` succeeds); F-01 facts | `shmget(IPC_PRIVATE,4096,0600)` succeeded (`rc[1]=0`) | executable attach succeeds where host/kernel permit (`rc[0]=0`, address recorded; attach/detach recorded; the observed shmat argument layout is recorded as observation **O-F01-1**) | death at `shmat` entry, **159** — a header with `rc[0]=0` is an x-attach bypass ⇒ **Exp-4 FAIL** | off-mode `shmget`/`shmat` failure from host/kernel restriction ⇒ **INCONCLUSIVE control** ⇒ that run is classified inconclusive, never enforcement evidence | SIGSYS |
| 4H-6 | `shmat` (non-exec control) | (allowed by the masked rule — falls through) | as 4H-5 | as 4H-5 | `rc[0]=0` (ordinary attach works) | **worker survives**, `rc[0]=0` — proves the Stage-2 `shmat` rule is flag-specific, not deny-all | if this fails on-mode while 4H-5 kills, the mask/value is wrong ⇒ **Exp-4 FAIL** (rule error, not feature) | — |

Rules: off-mode `EPERM` from host policy is **never** proof the Stage-2 filter works; each row tests exactly one syscall (no cross-coverage); every claim "blocked by Stage-2" requires its own row's off-control at grade `CONTROL-ENTRY` or better, and mechanism-prevention claims require `CONTROL-STRONG`; run order is off-control before on-mode per row; Stage-1 coverage remains the Rev 5 §5.3 4F rows + 4C + E-2 4F-9.

### F-10 — Trust boundary and evidence classification (module adversarial)

**Amends:** Rev 5 §2.6 and Rev 6 §2.6.1 (consistent; this finding operationalizes them).

1. **Classification: the loaded native/COBOL module is ADVERSARIAL** for this spike — trusted for nothing; no documented trust boundary proves otherwise. The worker hosting it is payload infrastructure (unchanged).
2. **Class A — Module-reported observations (untrusted by definition):** values returned by the COBOL program; `cob_call_ret`/`outcome_cat`/`cobol_exit_code` as delivered in `CALL_ACK`; the entire EVILMOD diagnostic structure (UID/GID/caps/mountinfo/seccomp text, probe `rc/err`, buffer lengths); any module-written log bytes. Every such datum in evidence MUST be labelled `CLASS-A: MODULE-ORIGINATED, UNTRUSTED`. A Class-A datum may illustrate; it may never attest.
3. **Class B — Supervisor-observed evidence (independent of the module), with collection method:** worker PID/process identity (supervisor-spawned child; `waitpid`); UID/GID (`/proc/<host-pid>/status`, root-readable from outside the PID namespace); uid_map/gid_map (`/proc/<pid>/uid_map`, `gid_map`); capability sets (`CapInh/CapPrm/CapEff/CapBnd/CapAmb` in `/proc/<pid>/status`); mount topology and read-only flags (`/proc/<pid>/mountinfo`); seccomp **mode** and filter **count** (`/proc/<pid>/status` fields `Seccomp`, `Seccomp_filters`); exit status/signal (`waitpid`, bwrap `128+sig` decode); cgroup membership and resource events (`cgroup.procs`, `memory.events`, `pids.current` of `necro.slice/spike.scope`); cleanup/reaping (`cgroup.procs` empty + reaped wait status); host-side staged-artifact hashes (supervisor-computed at staging, F-05 step 5); host-side protocol framing and byte counts (supervisor's own state machine). **Cannot be collected under this architecture:** seccomp filter *content* proof (mode/count only; exported-BPF artifacts are worker-written ⇒ Class A); integrity-protected result content; log authenticity. Filter-content verification therefore rests on behavior (4C/4F/4H on-mode kills) plus fail-closed loading — stated, not hidden.
4. **Adversarial protocol-interference tests (Exp-2 sub-tests 2H-1…2H-5; run with `--worker-seccomp=off` so interference is not masked by filters; EVILMOD Mode `'P'` — future hook):** (2H-1) module reads FD 3; (2H-2) module writes a forged frame to FD 4; (2H-3) module closes FD 3 or FD 4; (2H-4) module consumes/corrupts expected request traffic; (2H-5) module forges a well-formed success `CALL_ACK`. Expected supervisor responses: desync/unexpected-frame/EOF ⇒ kill worker, run = `FAILED_PROTOCOL`, taint recorded, worker never reused, no result accepted; a forged frame that is well-formed but **unexpected in the state machine** is rejected as an unexpected frame (2H-5). **Stated directly:** the architecture **cannot prevent** a module from emitting protocol-perfect forgeries timed to look worker-originated in an expected slot; it detects state-machine anomalies (unexpected frames, out-of-order responses, double responses, EOF) and bounds damage by killing and replacing. No authenticated-execution-receipt, integrity-protected-result, or module-independent security-attestation claim is made anywhere in this specification.
5. **Differential parity (3E) scope:** reports an observed byte comparison between worker output and oracle output on non-tainted runs; it does not attest the trustworthiness of the execution path and must be cited as an observational result only.
6. **Stronger-integrity architecture (described, NOT implemented):** move protocol-FD ownership out of the module's process — e.g., worker-broker process holds FD 3/4 and invokes the module in a forked child whose only inherited FDs are the log pipe — so module code never touches the authoritative supervisor channel. This is a Phase-1 design option; adopting it is a future decision and changes none of this spike's gates.

### F-11 — Differential-corpus and state-test reproducibility

**Supersedes:** the under-specified corpus/replay text of Rev 5 §7.3. All of the following are specification (nothing here has run).

**64 boundary vectors — deterministic generation table.** For each receiver-PICTURE class C ∈ {`S9(5)V99`, `S9(4)V9`, `S9(3)V99`, `9(3)V99`, `SV999`, `SV99`, `S9(5)`, `S9(3)`} (8 classes — the COMP-3 receiver set of the positive fixtures), exactly 8 boundary cases: B1 zero; B2 +max; B3 −max (unsigned classes: +max repeated with input sign flipped, recorded as invalid-input decode case); B4 minimum fraction magnitude (+10^−F); B5 max − ulp (10^−F); B6 overflow = +10^I (size-error by construction); B7 exact half-case at target scale (…5 exactly, ROUNDED target); B8 scale-edge (value with F+1 fraction digits exercising store truncation). Total 8×8 = **64**. Each vector record: `{vector_id, fixture (the positive fixture owning that PICTURE receiver), target_pic, signedness, scale, boundary_type, operand_bytes_hex (inputs constructed to force the receiver boundary)}`. Expected outputs are **not** precomputed in the spec: they are derived at run time by the §2.4 oracle ([D] rules) and recorded; V3/V4-class division cases are excluded from the 64 (they live in the hypothesis-tagged V-table). Serialization: canonical JSONL, one record per line, sorted by `vector_id` ASCII; corpus hash = SHA-256 over the file bytes; stored as `exp3/corpus/boundary64.jsonl` + `boundary64.sha256`.

**Hypothesis-generated cases.** Hypothesis pinned at **6.170.14** through the §10 lock process. One strategy per positive fixture: `st.integers(min_value=-10**(I+F), max_value=10**(I+F)-1)` mapped through the fixture's receiver set (multi-field fixtures: tuples via `@st.composite`, receiver capacities fixed to the fixture's PICTUREs; T3DISP uses sign-separate text strategies). Generation settings: `max_examples=1000`, `deadline=None`, `database=None`, **`derandomize=True`**, `print_blob=True`. Replay mechanism: `derandomize=True` makes the corpus a deterministic function of (strategy, settings, Hypothesis version) — **explicitly: a fixed seed alone does not guarantee identical results across Hypothesis versions, and no cross-version identity is claimed**; corpus identity is pinned by the version lock plus the exported corpus hash. Failing examples: retained via `print_blob` output as minimal reproductions in `exp3/failures/<fixture>/<hash>.txt` and replayed with `@example` decorators in the regression run. Exports: per-fixture `exp3/corpus/generated_<fixture>.jsonl` (inputs + oracle outputs + worker outputs + verdict) plus `generated_corpus.sha256`. Clean-environment reproduction: same locked wheels (§10) + same files ⇒ byte-identical `derandomize` corpus within the pinned version; a version bump requires re-baselining the corpus hash (recorded as a finding, not silence).

**Five planted mutations (unchanged definitions, Rev 5 §7.3):** M1 round-half-down; M2 truncate-instead-of-round; M3 sign-nibble C↔D swap on decode; M4 V-scale off-by-one; M5 separate-sign position swap. Each mutant: expected failure = ≥1 corpus vector byte mismatch in its targeted construct class; demonstration = run mutant oracle over boundary64 + one generated corpus, record `mutants.json {mutation_id, first_failing_vector, wall_time}`; mutation definitions, mutant code, and the corpus are retained as evidence artifacts. Undetected mutant ⇒ 3E FAIL.

**T3STATE / T3INIT exact sequences (recorded, not asserted).** Initial state: fresh worker per sequence; WS-ACC-VAL = VALUE +10; WS-ACC-UNIN uninitialized (**H5**). S1 (sticky): T3STATE, `reset_flag=0`, `step=1`, ×10 calls — record OUT-VAL series (expected: VALUE+1, +2, … if sticky persists; exact pattern recorded) and OUT-UNIN series (H5). S2 (IS INITIAL): T3INIT, `step=1`, ×10 — record constant-series expectation. S3 (cancel/reset): T3STATE ×3 (`step=5`), then `reset_flag=1, step=1` — record post-reset OUT-VAL vs S1 baseline (returned-to-base per cancel semantics, or not — recorded); repeat with a second reset. S4 (worker replacement): after any tainted outcome the worker is replaced and the sequence restarted on a fresh PID (recorded). Mutation between calls: only `step` values as listed; no other state is touched. Observables per step: `LK-OUT-VAL`/`LK-OUT-UNIN` COMP-3 bytes from `CALL_ACK`.

**Performance threshold scope.** The `≤ 1.5 s / 1000 calls` figure attaches to the **complete comparison path on a warm worker**: worker `CMD_CALL` round-trip + supervisor framing + oracle encode/compare, excluding cold start (first call after `INIT_ACK`), excluding compiler-oracle compilation, excluding corpus generation. It is a **target**, not an established result; the hardware/software environment (CPU model, cores, RAM, kernel, Python version, locked wheel versions) is recorded in `exp3/environment.json` at run time and the measured figure reported against it. No timing claim is made by this specification.

### F-12 — Dependency classes and coherent hash locking

**Supersedes:** the mixed presentation of Rev 5 §2.1.3 (seven captured hashes + one "regenerated at Env-0" row, read against a universal "must match captured digest" rule).

- **Class 1 — predeclared reference version + hash (7):** `lark==1.3.1`, `sortedcontainers==2.4.0`, `pytest==9.2.0`, `iniconfig==2.3.1`, `packaging==26.3`, `pluggy==1.7.0`, `pygments==2.21.0` with the 2026-11-04 reference digests already recorded in Rev 5 §2.1.3. At Env-0 these are re-acquired (`pip download --only-binary=:all:`) and their digests re-verified by `pip hash` against the recorded values; mismatch ⇒ supply-chain finding, abort.
- **Class 2 — capture-at-Env-0 baseline (1):** `hypothesis==6.170.14` — version predeclared; **wheel hash is NOT pre-captured anywhere in this corpus and none is invented**. Capture procedure at Env-0: acquire via `pip download --dest /wheels --only-binary=:all: hypothesis==6.170.14` (wheel filename resolved by the target interpreter: either the `cp312-cp312-manylinux…` or `cp311-abi3-manylinux…` x86_64 wheel); compute SHA-256 via `pip hash /wheels/hypothesis-6.170.14-<tag>.whl`; retain the wheel in `/wheels` and a copy under `spike_evidence/env0/wheels/`; insert the digest as the `--hash=sha256:…` entry in `requirements-spike.lock`; every subsequent `pip install --require-hashes` verifies it. This is a **capture-at-Env-0 baseline**, explicitly not a pre-captured upstream reference hash.
- **Lock completeness:** the lock contains **all 8 distributions with hashes** (3 direct + 1 hypothesis-transitive `sortedcontainers` + 4 pytest transitives — closure unchanged); `--require-hashes` requires a hash for every package actually installed, and this lock satisfies that: **no package is installed from an unhashed entry**. The Rev 5 §2.1.3 sentence imposing reference-digest equality applies to Class 1 only; Class 2 is governed by this capture rule. No wheel hash or dependency version is invented here.

## 4. Superseded statements and replacement wording

| # | Location (historical, unchanged) | Superseded wording | Replacement (Rev6.4 §) |
|---|---|---|---|
| 1 | Rev 5 §6 / E-2 implicit completeness of Stage-2 exec-memory policy | Stage-2 covers memfd/mmap/mprotect/pkey_mprotect | + `shmat`/`SHM_EXEC` masked rule, §3 F-01 |
| 2 | Rev 5 §2.3.2 `CMD_CALL` | `reset_flag` undefined | full definition + `_exit(11)` fault, §3 F-02, §7 |
| 3 | Rev 5 §7.2 Expected; §9 Exp-2 criterion | "all five categories observed" | revised honest criterion, §3 F-03 |
| 4 | Rev 5 §2.2/§2.4 acceptance-implies-support implication | parser acceptance read as defined semantics | F-04 table; unsupported constructs rejected |
| 5 | Rev 5 §4.3 ordering sentence | chmod before sentinel creation | canonical 9-step sequence, §3 F-05 |
| 6 | Rev 6 E-0 §0.1; Rev 6.1 E-11 step 2 | "fixtures #1–#19" | "#1–#20", §3 F-06 |
| 7 | Rev 6.3 E-15 citation text | "Rev 6.1 E-4", "Rev 6.1 E-13", "occurrences corrected" | Rev 6 E-4 / Rev 6.2 E-13; "superseded for normative use", §3 F-07 |
| 8 | Rev 5 §2.3.3 L2 name regex | `[A-Za-z0-9][A-Za-z0-9_]{0,30}` | canonical grammar both loaders, §3 F-08 |
| 9 | Rev 5 §5.3 scope | no Stage-2-specific tests | 4H-1…4H-6 matrix, §3 F-09, §6 |
| 10 | Rev 5 §2.6 evidence framing | implicit trust in returned diagnostics | Class A/B labeling, §3 F-10, §11 |
| 11 | Rev 5 §7.3 corpus/replay text | under-specified | §3 F-11 |
| 12 | Rev 5 §2.1.3 lock presentation | mixed hash classes; 7-vs-8 tension | Class 1/Class 2, §3 F-12 |
| 13 | Rev 5 §2.3.2 framing/padding gaps | implicit | full wire contract, §7 |
| 14 | Rev 5 §11 audit line "exit codes 10/12/13/14/15/16" | enumeration without 11 | adds `_exit(11)` worker protocol fault |
| 15 | Rev 5 §2.5 hypothesis register | H1–H7 (+H8 E-2) | adds **H9** (zero-divide category mapping, recording-only) |

## 5. (Superseded-statements register — see §4; no historical file is edited.)

## 6. Security-policy matrix (consolidated; Stage-1 vs Stage-2)

| Layer | Mechanism / syscall | Rule | Action | Claim arbiter (test) | Status |
|---|---|---|---|---|---|
| Stage-1 | fork, vfork, clone, clone3, execve, execveat | deny | KILL_PROCESS | 4F-1…6 | Unverified (specified) |
| Stage-1 | socket family (16 exact names, Rev 5 §6) | deny | KILL_PROCESS | 4C | Unverified |
| Stage-1 | ptrace, process_vm_*; unshare, setns; mount/umount2/pivot_root/chroot; bpf, perf_event_open, userfaultfd, io_uring_*, keyring, modules, kexec, reboot, swap, uselib, open_by_handle_at, name_to_handle_at, **modify_ldt** | deny | KILL_PROCESS | 4F-7, 4F-8 (sandbox-assisted), 4F-9 (x32 gate) | Unverified |
| Stage-1 | x32 ABI numbers (`nr ≥ 0x40000000`) | badarch gate | KILL_PROCESS | 4F-9 | Unverified |
| Stage-1 | loaders' needs: openat/mmap/mprotect(exec)/memfd_create/close/read/write/munmap | **allowed** (constructor window) | — | 4A census | Unverified (R-1 accepted) |
| **Stage-2** | `memfd_create` | deny all | KILL_PROCESS | **4H-1** | Unverified |
| **Stage-2** | `mmap` (exec bit) | arg2 MASKED_EQ 0x4/0x4 | KILL_PROCESS | **4H-2** | Unverified |
| **Stage-2** | `mprotect` (exec bit) | arg2 MASKED_EQ 0x4/0x4 | KILL_PROCESS | **4H-3** | Unverified |
| **Stage-2** | `pkey_mprotect` (exec bit) | arg2 MASKED_EQ 0x4/0x4 | KILL_PROCESS | **4H-4** | Unverified |
| **Stage-2** | `shmat` (`SHM_EXEC` 0x8000) | arg2 MASKED_EQ 0x8000/0x8000 | KILL_PROCESS | **4H-5** (+4H-6 non-exec control) | Unverified |
| Stage-2 | everything else | allow (default) | — | 4A census may propose tightening (Q8) | Open (post-census decision) |

## 7. Protocol contract (complete wire-level specification)

**Encoding.** Protocol version `1`; header = 8 bytes, little-endian: `[u8 magic=0x4E][u8 version=1][u8 opcode][u8 flags][u32 payload_len]`. **All multi-byte integers in every payload are little-endian.** Strings: module `name`/`path` are ASCII (constrained by the F-08 grammar and canonical-path comparison); error text is UTF-8. Lengths count **bytes**, not characters. No NUL terminators anywhere. Maxima (unchanged, Rev 5 §2.3.2): frame ≤ 33880; `CMD_CALL` payload ≤ 32836; `CALL_ACK` payload ≤ 33872; per-arg ≤ 16384; aggregate ≤ 32768; `err_len` ≤ 1024; name ≤ 31; path ≤ 128; argc ≤ 16.

**Flags and padding.** Envelope `flags`: only `0x00` is valid; every other value is a protocol fault. Padding bytes (`CMD_CALL.pad`, `CALL_ACK.pad`): must be `0`; nonzero ⇒ fault. Unused argument-length slots (`CALL_ACK.len_i` for `i ≥ argc`; `CMD_CALL.len_i` for `i ≥ argc`): must be `0`; nonzero ⇒ fault (supervisor side: `FAILED_PROTOCOL`, kill). Reserved fields: `INIT_ACK` has none beyond documented; all `reserved*` bytes anywhere must be zero.

**Validation order (receiver of `CMD_CALL`, after EINTR-safe `read_exact`):** (1) magic; (2) version == 1; (3) opcode known; (4) flags == 0; (5) `payload_len` ≤ state-specific max (checked in `uint64_t` before allocation; static buffers); (6) embedded `argc ≤ 16`; (7) each `len_i ≤ 16384`; (8) `Σ len_i ≤ 32768`, summed in non-wrapping width; (9) lengths consume payload **exactly**; (10) pad == 0; (11) `reset_flag ∈ {0,1}`. Any failure ⇒ fault. Symmetric rules apply to `CALL_ACK` on the supervisor side (untrusted input per §11).

**Partial I/O.** `read_exact`/`write_all` per Rev 5 §2.3.2 (EINTR-safe; `EOF_CLEAN` at frame boundary; `ERR_PREMATURE_EOF` mid-frame; `ERR_EPIPE` with `SIGPIPE` ignored). New worker-side rule: premature EOF or any of the faults above **inside** an established session ⇒ no response, `close(4)`, **`_exit(11)`** (idle clean EOF remains `_exit(14)`). Supervisor treats all faults as `FAILED_PROTOCOL`: kill, taint record, PID recycle, no retry on the same worker.

**Worker state machine.** States: `STARTUP` (fd audit, `$TMPDIR` init) → `AWAIT_INIT` → `INIT_VALIDATING` (canonical binding; hash; [on] Stage-1 → load → Stage-2 → Seccomp verify) → `READY` ⇄ (`CMD_CALL` → `CALL_IN_PROGRESS` → result response) → `READY`; `READY` → `TAINTED_EXIT` (tainted `CALL_ACK` flushed ⇒ `_exit(10)`); `READY` → `QUIT_ACK` → `_exit(0)`; any fault state → `_exit(11)` (or specific init codes: −1→14, −2→12, −3→15, −4→16).

| Event in state S | Response |
|---|---|
| `CMD_INIT` in `AWAIT_INIT`, valid | validate → `INIT_ACK` → `READY` (or init-failure exit path) |
| second `CMD_INIT` (in `READY`) | fault: `_exit(11)` |
| `CMD_CALL` in `AWAIT_INIT` | fault: `_exit(11)` |
| `CMD_CALL` in `READY`, valid | validate (order above) → [reset] → call → `CALL_ACK` → `READY` or `TAINTED_EXIT` |
| `CMD_CALL` during `CALL_IN_PROGRESS` | impossible (single-threaded sequential read); if engineered via FD forgery it surfaces as an unexpected/overlapping frame on the supervisor side ⇒ `FAILED_PROTOCOL` |
| `CMD_QUIT` in `READY` | `QUIT_ACK`, `close(3/4)`, `_exit(0)` |
| `CMD_QUIT` outside `READY` | fault: `_exit(11)` |
| invalid version | fault: `_exit(11)` |
| truncated frame (premature EOF mid-frame) | `_exit(11)`; idle clean EOF ⇒ `_exit(14)` |
| oversized frame | fault: `_exit(11)` |
| unknown command | fault: `_exit(11)` |
| invalid flag / bad padding / bad reset_flag | fault: `_exit(11)` |
| unexpected descriptor closure (EOF on FD 3) | idle: `_exit(14)`; mid-frame: `_exit(11)` |

**Status-consistency rules.** Valid tuples `(cob_call_ret, outcome_cat, tainted)`: (0,0,0); (1,1,1); (−1,2,1); (−2,3,1); (−3,4,1). `cobol_exit_code` is advisory except `outcome_cat=1`, where it must equal the STOP RUN code (2D expectation: 42, Unverified). Worker-exit implications: a tainted `CALL_ACK` ⇒ worker must `_exit(10)` after flushing; exit 10 without a preceding tainted ACK is a contradiction; `_exit(0)` only via `QUIT_ACK` (or idle-EOF 14); init exits 12/14/15/16 pair with `INIT_ACK −2/−1/−3/−4`. **Impossible-by-rule combos include:** `(ret=0, tainted=1)`, `(ret=0, cat≠0)`, `(ret≠0, tainted=0)`, `(cat=0, ret≠0)`, any `(ret,cat)` off the valid list, `QUIT_ACK` after a tainted ACK. **A contradiction between any of these fields IS a protocol-integrity failure**: supervisor kills the worker, records `FAILED_PROTOCOL` + finding, replaces the worker, and accepts no result from that exchange. Reset semantics are those of F-02 (integrated by reference; no separate inconsistent definition exists).

## 8. COBOL grammar-to-semantics table

Provided in full as §3 F-04 (single normative table; no production accepted without semantics; no subset expansion).

## 9. Fixture and experiment ownership matrix

Provided in full as §3 F-06 (20-entry inventory with owners, purposes, class, and source presence). Vector ownership is unchanged and restated: V1–V5, V7 owned by Exp-1; **V6 owned exclusively by Exp-2 test 2A** (`00 03 00 0C` [D]); V1–V7 additionally feed the 3E differential corpus without independent expectations there. Canonical vector bytes: V1 `01 54 32 0C`; V2 `00 67 9C`; V3/V4 `06 66 66 6C` (alternate `06 66 70 0C`); V5 per the H3/H4 policy set with `12 34 5F` unsigned sentinels; V6 `00 03 00 0C`; V7 `30 36 31 37 33 2D` / `30 31 32 33 34 35`. All empirically unverified.

## 10. Reproducibility and dependency-capture rules

Provided in full as §3 F-11 (boundary table, Hypothesis pinning/derandomize/replay/export, mutations, state sequences, threshold scoping) and §3 F-12 (Class 1 / Class 2 lock rules; 8/8 hashed at install time).

## 11. Trust-boundary and evidence-classification rules

Provided in full as §3 F-10: module adversarial; Class A (module-originated, untrusted) vs Class B (supervisor-observed) with collection methods and the explicit list of what this architecture cannot prove; 2H-1…2H-5 adversarial interference tests; the direct statement that perfect forgeries in expected slots cannot be prevented; differential parity's observational scope; the described (not implemented) broker architecture for stronger integrity. Standing constraints reaffirmed: R-1 (constructor window under Stage-1) and the L1 trusted-host staging assumption (A2) remain explicitly identified; the L2 sealed-memfd claim remains exactly "post-copy tamper is kernel-blocked in-process" — nothing more.

## 12. P0 provenance status (unchanged, controlling)

**`ABORTED-P0 — SOURCE PROVENANCE INCOMPLETE`**

Rev6.4 does **not** cure and does not alter this disposition. The six specification documents remain `TRANSCRIPT-DERIVED COPY`; GitHub publication is not provenance evidence; this new errata file is itself transcript/session-derived and cures nothing. No original-source hashes are invented; `P0 PASS` is not claimed; Env-0 and all technical gates remain blocked under E-11 step 6. Channel A (lossless platform-origin transcript export + byte-level verification) and Channel B (user-attested copies — qualified baseline only, and insufficient for the original E-11 requirement absent an explicit user waiver) remain distinct; **no waiver is authorized by Rev6.4**. The `p0_disposition_amendment.json` remains historically controlling.

## 13. Acceptance checklist

| ID | Condition | Mark | Note |
|---|---|---|---|
| AC-01 | Stage-2 `shmat`/`SHM_EXEC` explicitly specified | **CLOSED — DOCUMENTATION** | §3 F-01 (source-verified facts; rule; controls) |
| AC-02 | Stage-2-specific tests with independent off/on controls | **CLOSED — DOCUMENTATION** | §3 F-09 (4H-1…4H-6), §6 |
| AC-03 | `reset_flag` fully specified or removed | **CLOSED — DOCUMENTATION** | §3 F-02 (retained + fully defined) |
| AC-04 | every accepted production has semantics or rejection | **CLOSED — DOCUMENTATION** | §3 F-04 table |
| AC-05 | deterministic fixture or revised honest criteria per mandatory category | **CLOSED — DOCUMENTATION** | §3 F-03 (gate revised) |
| AC-06 | one consistent staging sequence | **CLOSED — DOCUMENTATION** | §3 F-05 |
| AC-07 | Rev4 inventory reconciled to #1–#20 | **CLOSED — DOCUMENTATION** | §3 F-06 |
| AC-08 | E-15 references and correction wording accurate | **CLOSED — DOCUMENTATION** | §3 F-07 (verified line numbers) |
| AC-09 | identical L1/L2 name validation | **CLOSED — DOCUMENTATION** | §3 F-08 |
| AC-10 | module vs supervisor evidence distinguished | **CLOSED — DOCUMENTATION** | §3 F-10, §11 |
| AC-11 | corpus generation/storage/replay/state reproducible | **CLOSED — DOCUMENTATION** | §3 F-11 |
| AC-12 | Hypothesis capture + full transitive hashing coherent | **CLOSED — DOCUMENTATION** | §3 F-12 |
| AC-13 | wire format/validation/state machine/status consistency complete | **CLOSED — DOCUMENTATION** | §7 |
| AC-14 | cross-document references & inventories reconcile | **CLOSED — DOCUMENTATION** | audit evidence in the Rev6.4 report (greps on published files) |
| AC-15 | historical files & integrity records unchanged | **CLOSED — DOCUMENTATION** | verified pre- and post-work against both manifests |
| AC-16 | P0 remains `ABORTED-P0 — SOURCE PROVENANCE INCOMPLETE` | **CLOSED — DOCUMENTATION** | §12 |
| AC-17 | no code/compilation/installation/container/experiment/deployment | **CLOSED — DOCUMENTATION** | self-evident from the record; §15 report |

"CLOSED — DOCUMENTATION" means the documentation requirement is fully specified; it implies **no** empirical outcome (all implementation-dependent rows remain Unverified).

## 14. Remaining unresolved decisions

1. **Q8 (pre-existing):** Exp-4A steady-state census may justify Stage-2 tightening; any benign-path SIGSYS under Stage-2 is a finding until then.
2. **F-10 architecture option:** broker-process separation for authenticated results is described, not chosen; adoption is a future design decision outside this spike.
3. **P0 closure channel (A vs B) — user-owned:** Rev6.4 cannot produce byte-accessible originals and does not waive E-11.
4. **Implementation-fidelity checkpoint:** EVILMOD Mode `'M'`/`'P'` fragments, the `_exit(11)` paths, and the F-08 shared grammar must be materialized exactly as specified during any future authorized implementation; deltas become new findings.
5. All H1–H9 hypotheses, O-F01-1, and every "Unverified" label above remain open **by design** until recorded by executed experiments.

## 15. Change log (Rev 6.3 → Rev 6.4)

1. F-01: `shmat`/`SHM_EXEC` Stage-2 policy + 4H-5/4H-6 (kernel facts source-verified; SHM_EXEC=0x8000; x86_64 `shmat`=30; shmflg=arg2 under both layouts).
2. F-02: `reset_flag` fully defined; `_exit(11)` introduced; Exp-3 reset observations specified.
3. F-03: category-to-fixture table; gate criteria revised to deterministic CAT_OK/CAT_STOP_RUN + recorded-outcome dispositions; T2CRASH kept distinct from CAT_*.
4. F-04: complete grammar-to-semantics table; acceptance-≠-support restated; H9 added.
5. F-05: canonical 9-step staging sequence; host/worker attribution; chmod ≠ mount immutability.
6. F-06: fixture inventory reconciled to #1–#20 with source-presence evidence; E-0/E-11 ranges superseded.
7. F-07: E-15 reference corrections; historical vs normative correction distinguished; exact old-byte locations enumerated.
8. F-08: single canonical module-name grammar for L1/L2 + conformance battery.
9. F-09: Stage-2-specific test matrix 4H-1…4H-6 with control grades and Stage-1/Stage-2 attribution.
10. F-10: adversarial classification; Class A/B evidence; 2H-1…2H-5; unpreventable-forgery statement; broker option described.
11. F-11: boundary64 table; Hypothesis 6.170.14 + derandomize/replay/export rules; M1–M5 evidence; state sequences; threshold scoping.
12. F-12: Class 1/Class 2 lock rules; 8/8 hashed; no invented digests.
13. F-13: complete wire contract, validation order, state machine, status-consistency rules.
14. Exit-code space extended with `_exit(11)`; hypothesis register extended with H9; probe space extended with 4H-* and 2H-*.
15. P0 disposition and all historical artifacts untouched (§2, §12).

`NOT EXECUTED — zero code written or modified, no packages installed, no containers built, no compilation performed, no experiments run, no results claimed.`
