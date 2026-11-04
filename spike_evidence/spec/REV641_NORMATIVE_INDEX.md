# REV641 Normative Index — NecroSpec Corpus (Post-Rev6.4.1)

**Consumption order:** Rev4_extract (§2.2.2, §3.1–3.3 by reference) → Rev5 → Rev6 → Rev6.1 → Rev6.2 → Rev6.3 → Rev6.4 → **Rev6.4.1** (`rev641_errata.md`); later layers control on conflict. Statuses: **Normative** (controlling), **Superseded** (replaced by the cited Rev6.4.1 section; historical text preserved, never edited), **Unverified** (specified, empirically unproven until recorded by an authorized experiment), **Open** (deliberately unresolved).

## A. Rev6.4 section-by-section status after Rev6.4.1

| Rev6.4 section | Status | Rev6.4.1 authority |
|---|---|---|
| §1 Purpose/authority | Normative (layering extended by Rev6.4.1 §1) | — |
| §2 Preservation statement | Normative (re-verified pre/post by Rev6.4.1 §2) | — |
| §3 F-01 (shmat/SHM_EXEC rule semantics, layout invariance, self-falsifiability) | Normative | — |
| §3 F-01 illustrative libseccomp fragment + failure mapping | **Superseded** | §4 (typed `seccomp_rule_add_exact_array` + `seccomp_syscall_resolve_name`; five-case fail-closed table) |
| §3 F-02 (reset_flag definition, `_exit(11)` for invalid values, Exp-3 observations) | Normative | — |
| §3 F-02 "Reset failure" row (cancel return-value test, `RESET_FAILED`, exit-10) | **Superseded** | §6 (void `cob_cancel`; process-level handling; no invented status) |
| §3 F-03 (category table, honest gate structure, T2CRASH distinction) | Normative | — |
| §3 F-03 CAT_STOP_RUN row + gate clause (b) | **Superseded** | §11 (single 2D contract; 42 = normative, Unverified until recorded) |
| §3 F-04, F-05, F-06, F-07, F-08, F-12 | Normative | — |
| §3 F-09 rows 4H-1, 4H-2, 4H-3 (memfd, mmap, mprotect) | Normative | — |
| §3 F-09 row 4H-4 (pkey) | **Superseded** | §7 (self-contained alloc→mmap→pkey_mprotect; CONTROL-UNAVAILABLE classification) |
| §3 F-09 rows 4H-5/4H-6 (shmat controls) | **Superseded** | §5 (mode 0700 + ownership/IPC_STAT; CONTROL-INVALID/UNAVAILABLE/STRONG; fresh-worker independence; kill/namespace semantics) |
| §3 F-10 (adversarial model, Class A/B, 2H-1…2H-5, broker option) | Normative | — |
| §3 F-10 Class-B bullet 1 ("identity via waitpid") | **Superseded** | §10 (identity-tuple discovery: NSpid, cgroup, exe, pidfd/starttime; permissions declared) |
| §3 F-11 (Hypothesis pinning, derandomize/replay/export, M1–M5, state sequences, threshold scoping) | Normative | — |
| §3 F-11 boundary64 paragraphs (class recipe) | **Superseded** | §9 (corrected 8-instance enumeration + complete 64-row table; 19 rows OPEN) |
| §4 supersession register | Normative (extended by Rev6.4.1 §12) | — |
| §6 security-policy matrix | Normative except rows 4H-4/5/6 probe details **Superseded** by §5/§7 (actions/comparisons unchanged) | §5, §7 |
| §7 protocol contract (encoding, maxima, order, state machine, `_exit(11)`) | Normative | — |
| §7 "Flags and padding" unused-slot rule + status-consistency cat=1 clause | **Superseded** | §8 (split CMD_CALL/CALL_ACK validation; recomputed formulas 32836/33872/33880) and §11 clause 3 |
| §8–§11 (pointers to F-04/F-06/F-11/F-10) | Normative as amended by the cited Rev6.4.1 sections | — |
| §12 P0 status | Normative; unchanged and controlling | — |
| §13 AC-01…AC-17 | Normative; AC-06 further qualified by Rev6.4.1 §13 | §13 |
| §14 open decisions, §15 change log | Normative (extended by Rev6.4.1 §14/§15) | — |

## B. Topic index (controlling text after Rev6.4.1)

| Topic | Controlling text | Empirical status |
|---|---|---|
| Stage-2 `shmat`/`SHM_EXEC` policy (rule semantics) | Rev6.4 F-01 + Rev6.4.1 §4 (construction/failure handling) | Unverified (4H-5/4H-6 per Rev6.4.1 §5) |
| Shared-memory test permissions/controls | Rev6.4.1 §5 | Unverified |
| `reset_flag` semantics | Rev6.4 F-02 as corrected by Rev6.4.1 §6 | Unverified (Exp-3 S1–S4) |
| 4H-4 pkey probe | Rev6.4.1 §7 | Unverified |
| Wire validation (request/response) | Rev6.4 §7 as corrected by Rev6.4.1 §8 | Unverified |
| Boundary64 corpus | Rev6.4.1 §9 (sole authority) | Unverified; 19 rows **Open** |
| Worker identity discovery | Rev6.4.1 §10 | Unverified (procedure specified) |
| CAT_STOP_RUN contract | Rev6.4.1 §11 | Unverified (2D) |
| All other topics (grammar/semantics, staging, sandbox, EVILMOD, Exp-1…Exp-4, lock classes, trust model, vectors V1–V7) | Rev6.4 index (REV64_NORMATIVE_INDEX.md §B) stands, with the Rev6.4.1 amendments above | Unverified throughout |

## C. Explicitly superseded statements (never normative, never edit history)

1. Rev6.4 §3 F-01 fragment `syscall(__NR_shmat)` / untyped `SCMP_CMP` → Rev6.4.1 §4.
2. Rev6.4 §3 F-02 cancel-return/`RESET_FAILED` path → Rev6.4.1 §6.
3. Rev6.4 §3 F-03 CAT_STOP_RUN "recorded-not-asserted" dual language → Rev6.4.1 §11.
4. Rev6.4 §3 F-09 4H-4 map-reuse; 4H-5/4H-6 `0600` segment mode and single grading → Rev6.4.1 §5/§7.
5. Rev6.4 §3 F-10 "identity via waitpid" → Rev6.4.1 §10.
6. Rev6.4 §3 F-11 boundary64 recipe (incl. `SV999`/`SV99` as receiver classes) → Rev6.4.1 §9.
7. Rev6.4 §7 unused-slot rule for `CMD_CALL`; cat=1 consistency wording → Rev6.4.1 §8/§11.

**Disposition:** `REV6.4.1 PARTIALLY COMPLETE — SPECIFICATION BLOCKERS REMAIN` (19 OPEN boundary vectors; P0 independently blocking all technical execution).

`NOT EXECUTED — no code written or modified, no dependencies installed, no containers built, no compilation performed, no arithmetic, FFI, parser, IPC, state or sandbox experiments run, and no deployment performed.`
