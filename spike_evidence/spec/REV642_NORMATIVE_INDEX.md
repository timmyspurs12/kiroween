# REV642 Normative Index — NecroSpec Corpus (Post-Rev6.4.2)

**Consumption order:** Rev4_extract (by reference) → Rev5 → Rev6 → Rev6.1 → Rev6.2 → Rev6.3 → Rev6.4 → Rev6.4.1 → **Rev6.4.2** (`rev642_errata.md`); later layers control on conflict. This layer is a single-defect correction; the Rev6.4.1 status map (REV641_NORMATIVE_INDEX.md §A–§C) stands except for the one supersession below.

## A. Rev6.4.1 section-by-section status after Rev6.4.2

| Rev6.4.1 section | Status after Rev6.4.2 | Authority |
|---|---|---|
| §1–§6, §8–§15 (incl. R64-01/02/03/05/06/07/08 corrections, §8 wire validation, §9 Boundary64 with 19 OPEN rows, §10 identity procedure, §11 CAT_STOP_RUN contract, §12 supersession table, §13 checklist) | **Normative** (unchanged) | — |
| §7 narrative (self-contained 4H-4 sequence, off/on expectations, CONTROL-UNAVAILABLE classification, seccomp comparison) | **Normative** (unchanged) | — |
| §7 illustrative fragment, the single call line `pkey_mprotect((unsigned long)p, …)` | **Superseded** | Rev6.4.2 §3: `pkey_mprotect(p, 4096, PROT_READ \| PROT_EXEC, pkey)` — no cast; userspace prototype `int pkey_mprotect(void *addr, size_t len, int prot, int pkey)` verified (man-pages 6.19 `pkey_mprotect(2)`; glibc `__pkey_mprotect`) |
| §7 citation of the kernel-doc signature `int pkey_mprotect(unsigned long start, …)` | Retained as a **syscall-layer citation only**; not a userspace call form | Rev6.4.2 §2/§3 |
| §13 AC-04 note | **Superseded** | Rev6.4.2 §4 (CLOSED — DOCUMENTATION for the pointer-type/API form; explicitly NOT empirically verified or experimentally closed; 4H-4 awaits Exp-4) |

## B. Standing dispositions (reaffirmed, unchanged)

- AC-06 remains **PARTIALLY CLOSED** (45 rows specified; 19 OPEN — REQUIRES DESIGN DECISION). The OPEN rows are not reopened or re-argued by Rev6.4.2.
- All empirical statuses remain **Unverified** / HYPOTHESIS — NOT EXECUTED; every gate remains NOT EXECUTED.
- P0 remains **`ABORTED-P0 — SOURCE PROVENANCE INCOMPLETE`** (controlling; not cured by any layer through Rev6.4.2; no waiver authorized).

`NOT EXECUTED — no application code written or modified, no dependencies installed, no compilation performed, no experiments run, and no deployment performed.`
