# NecroSpec Rev 6.4.2 — Single-Defect Correction (R64-04 pointer type)

## 1. Purpose and scope

Rev6.4.2 makes exactly **one** correction: the `pkey_mprotect()` example in Rev6.4.1 §7 casts its first argument to `unsigned long`; the userspace prototype takes a `void *`. No other statement of Rev6.4.1 or any earlier layer is amended. The 64 Boundary64 rows are untouched; the 19 OPEN Boundary64 design decisions remain open and untouched; no new requirements, fixtures, experiments, or corrections are introduced. This layer is documentation-only. Rev6.4.1 is preserved byte-for-byte as historical record; the correction supersedes only the identified line.

## 2. Verification basis (independent sources vs Arena-sandbox observations)

**Independently verified (authoritative external sources, fetched 2026-11-04):**

- man-pages **6.19** `pkey_mprotect(2)` (man7.org), SYNOPSIS: `int pkey_mprotect(size_t size; void addr[size], size_t size, int prot, int pkey);` — the first parameter `addr` is a **`void *`** (`void addr[size]` array-parameter notation). Same page, ERRORS: `EINVAL (pkey_mprotect()) pkey has not been allocated with pkey_alloc(2)` — consistent with the valid-key requirement already specified.
- glibc source `sysdeps/unix/sysv/linux/pkey_mprotect.c` (bminor mirror of the GNU C Library): `int __pkey_mprotect (void *addr, size_t len, int prot, int pkey)` with `weak_alias (__pkey_mprotect, pkey_mprotect)` — the userspace wrapper's first parameter is **`void *addr`**.
- Kernel documentation *Memory Protection Keys* (core-api/protection-keys.html) gives `int pkey_mprotect(unsigned long start, size_t len, unsigned long prot, int pkey)` — this is the **raw syscall-layer** signature (kernel entry convention), correct at its own layer. Rev6.4.1 §7 cited it accurately but then used its parameter types in **userspace call syntax** — a layer-mixing defect. The userspace call must use the libc wrapper prototype.

**Arena-sandbox observations (environment-reported, reproducible from the published manifests by any reviewer):**

- Local glibc headers in the Arena sandbox expose no `pkey_mprotect` prototype (grep empty); the verification therefore rests on the two external sources above.
- All integrity results in §5 (branch/commit identity, `sha256sum -c` outputs, git status) are tool outputs of the Arena sandbox environment.

## 3. The defect and the correction

**Superseded (Rev6.4.1 §7 illustrative fragment, one line):**

```c
    int r = pkey_mprotect((unsigned long)p, 4096,
                          PROT_READ|PROT_EXEC /* PROT_EXEC = 0x4 */, pkey);
```

**Replacement (full fragment; only the call line differs from Rev6.4.1 §7 — every other line is carried verbatim):**

```c
/* 4H-4 — spec fragment only; not built by this pass. */
int  pkey = pkey_alloc(0, 0);                                /* step 1: valid protection key */
void *p    = mmap(NULL, 4096, PROT_READ|PROT_WRITE,
                  MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);         /* step 2: this probe's own mapping */
if (p != MAP_FAILED && pkey >= 0) {
    int r = pkey_mprotect(p, 4096,
                          PROT_READ|PROT_EXEC /* PROT_EXEC = 0x4 */, pkey);
    rec(r, errno);            /* off-mode CONTROL-STRONG iff r == 0 */
    munmap(p, 4096); pkey_free(pkey);
} else {
    rec_setup(p, errno, pkey, pkey < 0 ? errno : 0);         /* setup outcome recorded, see below */
    /* on-mode only: pkey_mprotect is still invoked with whatever setup was obtained —
       the Stage-2 filter matches at syscall ENTRY on the prot argument (arg 2,
       MASKED_EQ 0x4/0x4) before any kernel argument validation. */
}
```

Normative points: (a) the first argument is the probe's existing `void *p` (established two lines earlier by `void *p = mmap(NULL, 4096, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);`), passed **directly, without a cast** — a type-correct call against the verified wrapper prototype `int pkey_mprotect(void *addr, size_t len, int prot, int pkey)`; (b) the probe's semantics — setup checks, off-mode CONTROL-STRONG condition, PKU-absent ⇒ CONTROL-UNAVAILABLE/INCONCLUSIVE, on-mode entry-gate kill (bwrap `159`), arg-2 `MASKED_EQ 0x4/0x4` seccomp comparison — are unchanged from Rev6.4.1 §7; (c) Rev6.4.1 §7's citation of the kernel-doc syscall-layer signature remains a correct citation **at that layer** and is retained as history; it is superseded only as the userspace call form. **No compilation is claimed; the fragment remains an illustrative specification fragment.**

Mechanical check performed in-repo: a line-diff of the Rev6.4.1 §7 fragment against this replacement yields exactly one changed line (the call), and the replacement passes the existing `void *p` variable directly (verified textually before publication; see the Rev6.4.2 report).

## 4. AC-04 closure disposition (updated, accurate)

| AC | Condition | Disposition | Note |
|---|---|---|---|
| AC-04 | 4H-4 uses an independently established mapping and valid protection key | **CLOSED — DOCUMENTATION** (pointer-type/API-form correction only) | The specification fragment is now type-correct against the verified userspace prototype. Per the standing Rev6.4 §13 definition, CLOSED — DOCUMENTATION implies **no empirical outcome**: the 4H-4 mechanism test is **NOT experimentally executed, NOT empirically verified, and NOT closed by this correction**. Off/on expectations remain Unverified until Exp-4 records them; a CONTROL-STRONG off-mode control remains a precondition for any mechanism-prevention claim (Rev6.4.1 §7 rules unchanged). |

No other AC disposition from Rev6.4.1 §13 is altered (AC-06 remains PARTIALLY CLOSED with 19 OPEN rows).

## 5. Preservation

Verified **before** writing (HEAD `eb7e3379e19a150f446d27b3429828051c90cae3`, parent `3d0d6a47803fb334aef488e91171df4920a9fe59`, branch `arena/c6d3bcf5-kiroween` = remote tip, clean tree): `PUBLICATION_SHA256SUMS` 11/11 OK; `spec/SHA256SUMS` 6/6 OK; `REV64_SHA256SUMS` 2/2 OK; `REV641_SHA256SUMS` 2/2 OK; P0 amendment digest `a14cdca5835fb40a2ae0e960a90fd34473c6d5a5ff761fd826b8286d9dccc824`. Re-verified **after** writing with identical results (reported in §9 of the Rev6.4.2 report). `spike_evidence/spec/rev641_errata.md` and `spike_evidence/spec/REV641_NORMATIVE_INDEX.md` are byte-identical pre/post; the git diff of this pass contains only the three new Rev6.4.2 files.

## 6. P0 provenance — unchanged

`ABORTED-P0 — SOURCE PROVENANCE INCOMPLETE`

Rev6.4.2 does not cure, amend, or reinterpret the P0 disposition. The original-source provenance question (Channel A / Channel B, no waiver authorized) remains a separate, user-owned decision. Env-0 and all technical gates remain blocked/not executed.

## 7. Change log (Rev 6.4.1 → Rev 6.4.2)

1. R64-04 (pointer type): Rev6.4.1 §7 `pkey_mprotect((unsigned long)p, …)` superseded by `pkey_mprotect(p, …)` — userspace prototype verified (man-pages 6.19; glibc `__pkey_mprotect`); kernel-doc signature reclassified as syscall-layer citation.
2. AC-04 note updated to state explicitly that the correction is documentation-only and carries no empirical verification.
3. No other change: Boundary64 rows untouched; OPEN decisions untouched; historical files untouched; P0 untouched.

`NOT EXECUTED — no application code written or modified, no dependencies installed, no compilation performed, no experiments run, and no deployment performed.`
