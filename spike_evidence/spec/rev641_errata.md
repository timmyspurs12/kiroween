# NecroSpec Rev 6.4.1 — Final Targeted Errata and Independent Closure Audit (R64-01 … R64-08)

## 1. Purpose, revision scope and authority

Rev6.4.1 is a **surgical, documentation-only superseding layer** over the published NecroSpec corpus (Rev4_extract → Rev5 → Rev6 → Rev6.1 → Rev6.2 → Rev6.3 → **Rev6.4**). It resolves the eight findings **R64-01 … R64-08** raised by independent review of Rev6.4, and nothing else. Rules:

1. Rev6.4.1 supersedes **only** the statements explicitly listed in §12 (supersession table). Every other Rev6.4 statement, and the entire Rev4–Rev6.3 chain, remains in force in the consumption order above, Rev6.4.1 controlling on conflict.
2. No historical file (Rev4–Rev6.4, manifests, env0 records, README) is edited in any way. Rev6.4 is preserved byte-for-byte; its integrity was verified before and after this pass (§2).
3. Rev6.4.1 is documentation-only: no code, fixtures, harnesses, containers, compilation, installation, or experiments. Code-like text herein is an **illustrative specification fragment** fixing an exact API/wire requirement, to be materialized only in a future explicitly authorized implementation phase. **No fragment in this document is claimed to compile or run.**
4. Labels: **[D]** = derived from documented COBOL/API semantics (still unverified until recorded by an executed experiment); **[Hn]** = HYPOTHESIS — NOT EXECUTED; **Unverified** = specified but empirically unproven; **OPEN — REQUIRES DESIGN DECISION** = cannot be fully established from published material + authoritative sources without an architectural decision. No invented bytes, hashes, behaviors, or outcomes.
5. Verification basis for this pass (all performed 2026-11-04, read-only): kernel UAPI `include/uapi/linux/shm.h` and `ipc/shm.c` (torvalds/linux master); `arch/x86/entry/syscalls/syscall_64.tbl`; libseccomp **v2.6.0** `include/seccomp.h.in` (tag matching the Rev5 pin `libseccomp2/-dev=2.6.0-2`, Debian trixie); kernel documentation *Memory Protection Keys* (kernel.org, `core-api/protection-keys.html`); proc(5) (NSpid, ptrace access checks); GnuCOBOL `cob_cancel` declaration/definition (libcob `common.h` / `call.c`, doxygen of the 3.x sources); and the published corpus files themselves.

## 2. Preservation of historical documents

Verified **before** writing (at HEAD `3d0d6a47803fb334aef488e91171df4920a9fe59`, branch `arena/c6d3bcf5-kiroween`, parent `d41b66caa99e034dfdf6e00159e018ec8dca5a71` = published Rev6.4 layer, clean tree):

- `spike_evidence/PUBLICATION_SHA256SUMS`: **11/11 OK**.
- `spike_evidence/spec/SHA256SUMS`: **6/6 OK**.
- `spike_evidence/REV64_SHA256SUMS`: **2/2 OK** (`rev64_errata.md`, `REV64_NORMATIVE_INDEX.md`).
- `env0/p0_disposition_amendment.json` digest `a14cdca5835fb40a2ae0e960a90fd34473c6d5a5ff761fd826b8286d9dccc824`, disposition string `ABORTED-P0 — SOURCE PROVENANCE INCOMPLETE` present.

Re-verified **after** writing with identical results (recorded in the Rev6.4.1 report). The three new Rev6.4.1 files are the only additions; no existing byte changed. `TRANSCRIPT-DERIVED COPY` classifications retained; GitHub publication ≠ provenance; this layer cures no provenance defect.

## 3. Findings R64-01 … R64-08 — summary of exact corrections

| ID | Rev6.4 defect (exact location) | Correction (Rev6.4.1 section) | Status |
|---|---|---|---|
| R64-01 | §3 F-01 fragment: `syscall(__NR_shmat)` (would invoke the syscall) and `SCMP_CMP(...)` passed where `seccomp_rule_add_array` expects a pointer | Corrected fragment: `seccomp_syscall_resolve_name("shmat")` + `seccomp_rule_add_exact_array()` with a real `struct scmp_arg_cmp` array; five-case fail-closed table — **§4** | CLOSED — DOCUMENTATION |
| R64-02 | §3 F-09 rows 4H-5/4H-6: `shmget(IPC_PRIVATE, 4096, 0600)` — no execute bit ⇒ off-mode `EACCES` before demonstrating executable attachment (kernel `ipc/shm.c do_shmat`: `SHM_EXEC` ⇒ `acc_mode \|= S_IXUGO`) | Mode `IPC_CREAT\|0700`, creator==attacher euid, `IPC_STAT` verification (worker + supervisor-side where feasible), CONTROL-INVALID / CONTROL-UNAVAILABLE / CONTROL-STRONG classification, fresh-worker on/off controls, cleanup and kill semantics — **§5** | CLOSED — DOCUMENTATION |
| R64-03 | §3 F-02: `if (cob_cancel(prog_name) != 0)` — GnuCOBOL 3.2 declares `void cob_cancel(const char *name)`; no return value exists | All return-value comparisons deleted; reset = request only; observables = post-call state comparison; process-level death handling; no fabricated `RESET_FAILED`/`CAT_FATAL_ERROR` — **§6** | CLOSED — DOCUMENTATION |
| R64-04 | §3 F-09 row 4H-4: `pkey_mprotect(p, …)` with `p` never established by the probe's own path ("4H-3's RW map reused") | Self-contained sequence `pkey_alloc(0,0)` → own `mmap` → checked → `pkey_mprotect`; off/on expectations; PKU-absent ⇒ CONTROL-UNAVAILABLE/INCONCLUSIVE (entry-gate evidence only) — **§7** | CLOSED — DOCUMENTATION |
| R64-05 | §7 "Flags and padding": zero-value rule applied to nonexistent `CMD_CALL.len_i (i ≥ argc)` slots | Split validation: CMD_CALL validates **exactly argc** length fields (no unused slots exist); CALL_ACK validates the **fixed 16-slot array** with mandatory zeros for `i ≥ argc`; payload formulas recomputed and maxima re-verified — **§8** | CLOSED — DOCUMENTATION |
| R64-06 | §3 F-11: boundary64 was a recipe (8 vague classes × 8 named cases), not a reconstructible corpus; Rev6.4's class list also misidentified `SV999`/`SV99` (operand PICTUREs, not receivers) | Complete 64-row specification table (IDs `BV-C1-B1`…`BV-C8-B8`) with exact values, bytes, ownership, and validity; class enumeration corrected to the actual fixture receivers; structurally unrepresentable rows marked **OPEN — REQUIRES DESIGN DECISION** with smallest-resolution proposals — **§9** | PARTIALLY CLOSED (45 rows fully specified; 19 rows OPEN) |
| R64-07 | §3 F-10 Class B: "worker PID/process identity (supervisor-spawned child; `waitpid`)" — `waitpid` returns the bwrap launcher's PID, not the worker's host PID | Supervisor-side discovery procedure: launcher PID via fork; worker host PID via `/proc` ppid-scan + `NSpid` (≥2 fields) + cgroup + `exe` correlation; pidfd/start-time anti-reuse; multi-candidate and pre-exit handling; ptrace-access permission declaration — **§10** | CLOSED — DOCUMENTATION |
| R64-08 | §3 F-03 CAT_STOP_RUN row + §7: `cobol_exit_code=42` both "exact response" and "recorded-not-asserted" | Single unambiguous contract: `cob_call_ret=1`/`outcome_cat=1`/`tainted=1` mandatory; `cobol_exit_code=42` normative fixture-derived expectation, Unverified until Exp-2; mismatch = recorded finding; `_exit(10)` distinguished; gate and status-consistency rules restated identically — **§11** | CLOSED — DOCUMENTATION |

## 4. Corrected F-01 seccomp fragment (R64-01)

**Verified API facts (libseccomp v2.6.0, `include/seccomp.h.in`; pinned by Rev5 §2.1 as Debian `libseccomp-dev 2.6.0-2`):**

```c
int seccomp_rule_add(scmp_filter_ctx ctx, uint32_t action, int syscall,
                     unsigned int arg_cnt, ...);                      /* h.in:688 — variadic structs   */
int seccomp_rule_add_array(scmp_filter_ctx ctx, uint32_t action, int syscall,
                           unsigned int arg_cnt,
                           const struct scmp_arg_cmp *arg_array);     /* h.in:708 — pointer to array   */
int seccomp_rule_add_exact(scmp_filter_ctx ctx, uint32_t action, int syscall,
                           unsigned int arg_cnt, ...);                /* h.in:727                      */
int seccomp_rule_add_exact_array(scmp_filter_ctx ctx, uint32_t action, int syscall,
                                 unsigned int arg_cnt,
                                 const struct scmp_arg_cmp *arg_array); /* h.in:745                    */
struct scmp_arg_cmp {                                                 /* h.in:108                      */
    unsigned int arg;            /* argument number, starting at 0 */
    enum scmp_compare op;        /* e.g. SCMP_CMP_MASKED_EQ (= 7, h.in:96) */
    scmp_datum_t datum_a;
    scmp_datum_t datum_b;
};
#define SCMP_CMP64(...)  ((struct scmp_arg_cmp){__VA_ARGS__})         /* h.in:271 */
#define SCMP_CMP        SCMP_CMP64                                    /* h.in:272 — yields a struct VALUE */
#define SCMP_SYS(x)      (__SNR_##x)                                  /* h.in:248 */
int seccomp_syscall_resolve_name(const char *name);                   /* h.in:655 */
#define SCMP_ACT_KILL_PROCESS 0x80000000U                             /* h.in:357 */
```

The two independent defects are therefore confirmed: `syscall(__NR_shmat)` performs the actual kernel call (a filter-construction side effect that must never occur), and `SCMP_CMP(...)` — a compound-literal **struct value** in v2.6.0 — is not the `const struct scmp_arg_cmp *` that `seccomp_rule_add_array()` requires.

**Corrected rule construction (chosen form — spec fragment only; compilation remains unexecuted):**

```c
/* Stage-2: deny executable SysV shm attachment. Rule semantics unchanged from Rev6.4 F-01:
   syscall "shmat", arg index 2 (shmflg), SCMP_CMP_MASKED_EQ, mask SHM_EXEC=0x8000,
   compare value SHM_EXEC=0x8000, action SCMP_ACT_KILL_PROCESS. */
int nr_shmat = seccomp_syscall_resolve_name("shmat");   /* runtime name resolution */
if (nr_shmat < 0) {                                     /* unresolved name: negative return */
    necro_fail_sandbox_init(-4);   /* INIT_ACK(init_status=-4); _exit(16); run FAILED_SANDBOX_INIT */
}
struct scmp_arg_cmp shmat_cmp[1] = {
    SCMP_CMP(2, SCMP_CMP_MASKED_EQ,
             (scmp_datum_t)SHM_EXEC /* mask  = 0x8000 */,
             (scmp_datum_t)SHM_EXEC /* value = 0x8000 */)
};  /* type-correct: compound literal initializes struct scmp_arg_cmp[1]; the array
      decays to const struct scmp_arg_cmp * for seccomp_rule_add_exact_array(). */
if (seccomp_rule_add_exact_array(ctx2, SCMP_ACT_KILL_PROCESS, nr_shmat, 1, shmat_cmp) != 0) {
    necro_fail_sandbox_init(-4);
}
/* after seccomp_load(ctx2) returns 0: verify /proc/self/status reports "Seccomp: 2",
   else necro_fail_sandbox_init(-4) (Rev5 §6 / Rev6 E-2, unchanged). */
```

Design notes (normative): (a) the **`_exact_array`** variant is chosen because it fails hard when the syscall cannot be resolved on the native architecture (no pseudo/surrogate fallback) — the fail-closed flavor Rev5 §6 already mandates; the equally type-correct alternative `seccomp_rule_add_exact(ctx2, SCMP_ACT_KILL_PROCESS, nr_shmat, 1, SCMP_CMP(2, SCMP_CMP_MASKED_EQ, …))` (variadic struct value) is permitted. (b) `syscall(__NR_shmat)` must **never** appear in filter-construction code; header-macro resolution (`SCMP_SYS(shmat)`) is allowable only as a compile-time cross-check of `nr_shmat`, never as a substitute for the runtime negative check. (c) The rule semantics (arg 2, mask/value 0x8000, KILL_PROCESS), the layout-invariance argument, and the 4H-5/4H-6 falsifiability requirement carry over from Rev6.4 F-01 unchanged.

**Fail-closed handling (no missing rule may be silently ignored; every Stage-2 rule is individually checked):**

| Failure | Detected by | Response |
|---|---|---|
| Unresolved syscall name | `seccomp_syscall_resolve_name("shmat") < 0` (negative, e.g. `-ENOSYS`) | `INIT_ACK(-4)`, `_exit(16)`, run class `FAILED_SANDBOX_INIT` |
| Unsupported architecture | `seccomp_init()` returning `NULL`; `seccomp_arch_add() != 0`; or rule-add returning `-EACCES`/`-EDOM` (native-arch unavailability; exact variants reject surrogate numbers) | same |
| Invalid comparison | rule-add returns `-EINVAL` (bad arg index — kernel exposes at most 6 — or malformed op/datum) | same |
| Rule-add failure | any non-zero return of `seccomp_rule_add_exact_array()` | same — the policy is never loaded with the rule silently missing |
| Filter-load failure | `seccomp_load() != 0`; or post-load `/proc/self/status` `Seccomp:` ≠ `2` | same |

## 5. Corrected 4H-5/4H-6 shared-memory test contract (R64-02)

**Verified kernel fact** (`ipc/shm.c`, `do_shmat`, torvalds/linux master): `if (shmflg & SHM_EXEC) { prot |= PROT_EXEC; acc_mode |= S_IXUGO; }` followed by `err = -EACCES; if (ipcperms(ns, &shp->shm_perm, acc_mode)) goto out_unlock;`. Rev6.4's `shmget(IPC_PRIVATE, 4096, 0600)` created a segment with **no execute bit**, so the off-mode executable attach could fail with `EACCES` for fixture reasons alone — the defect.

**Segment creation and ownership (worker, inside the sandbox):**

1. `shmid = shmget(IPC_PRIVATE, 4096, IPC_CREAT | 0700)` — creator is the worker itself (euid 10001) inside the sandbox's **private IPC namespace** (`bwrap --unshare-all`); creator and attacher are therefore the same identity by construction.
2. Immediately verify: `shmctl(shmid, IPC_STAT, &ds)` with `ds.shm_perm.cuid == ds.shm_perm.uid == geteuid()` **and** `(ds.shm_perm.mode & 0777) == 0700`. The execute bit in the segment mode is what makes an `SHM_EXEC` attach permission-feasible; the ownership check proves the attacher owns the segment it is about to attach.
3. Both operations occur in the intended (sandbox-private) IPC namespace; no host-visible IPC object is created at any point (`IPC_PRIVATE`, private namespace).

**Supervisor-observable `IPC_STAT` corroboration (declared feasibility):** a host-side `shmctl(IPC_STAT)` **cannot** see the segment (different IPC namespace). Where feasible, the supervisor instead reads `/proc/<worker-host-pid>/root/proc/sysvipc/shm` (the procfs instance inside the worker's namespaces; entry: key `0x00000000`, size 4096, mode 700, cpid = worker). This read is subject to the kernel's ptrace access check on `/proc/<pid>/root` (§10 permissions paragraph). If the supervisor cannot satisfy that check, record `IPC-STAT-SUPERVISOR: UNAVAILABLE`; the probe's own `IPC_STAT` output remains **Class A** (module-reported, illustrative) and is **never** presented as independent confirmation.

**4H-5 — executable attachment (Mode 'M' sub 5; future hook):**

- **Off-mode control (seccomp off, fresh worker):** shmget(`IPC_CREAT|0700`) → `IPC_STAT` verify → `shmat(shmid, NULL, SHM_EXEC)` → expect a valid address (not `(void *)-1`); store and read back one word through the attachment → `shmdt() == 0` → `shmctl(shmid, IPC_RMID) == 0`. All steps succeeding ⇒ control grade **CONTROL-STRONG** (executable shared-memory attachment demonstrably available to the worker identity).
- **Classification of off-mode failures:** owner/mode/`IPC_STAT` mismatch, or wrong mode bits ⇒ **CONTROL-INVALID** (test-fixture misconfiguration — must be fixed; the paired on-mode kill from such a run is **not** enforcement evidence). Genuine host/kernel restriction after owner and mode are verified correct — e.g. `EACCES` from an LSM, `ENOSYS` from `!CONFIG_SYSVIPC` — ⇒ **CONTROL-UNAVAILABLE** ⇒ that experiment run is **INCONCLUSIVE**, never enforcement evidence. Full success ⇒ **CONTROL-STRONG**.
- **On-mode (Stage-2, fresh worker):** expected outcome is death at the `shmat` syscall **entry** — headerless worker death, bwrap exit `159` (SIGSYS). Any header/`CALL_ACK` with `rc[0]==0` is an attach bypass ⇒ **Exp-4 FAIL**. The on-mode kill counts as **mechanism-prevention** evidence only when the paired off-mode control reached **CONTROL-STRONG** in the same environment; otherwise it evidences the entry gate at most.
- **IPC object fate on Stage-2 kill:** the worker dies at `shmat` entry with the segment still existing (0 attaches, `IPC_PRIVATE`); when the sandbox's last process dies, the bwrap reaper exits and the private **IPC namespace is destroyed, and the kernel frees all remaining SysV segments with it** (namespace-lifetime guarantee). Host-side post-mortem confirmation is generally impossible (the namespace is gone); where the §10 procedure still permits a pre-death read of `/proc/<pid>/root/proc/sysvipc/shm`, the snapshot is recorded. No host-side IPC object ever exists.

**4H-6 — non-executable attachment control (Mode 'M' sub 6; separate fresh worker, Stage-2 on):** identical sequence with `shmat(shmid, NULL, 0)`: **must succeed** (`rc[0]==0`), then `shmdt() == 0`, `shmctl(IPC_RMID) == 0`, worker survives and continues. This proves the Stage-2 `shmat` rule is flag-specific rather than deny-all. If 4H-6 dies on-mode while 4H-5 kills, the mask/value pair is wrong ⇒ **Exp-4 FAIL** (rule error, not a security feature).

Both probes remain EVILMOD Mode-'M' hooks **specified, not yet materialized** (Rev6.4 §3 F-06 row #20 note unchanged); each run uses a **fresh worker** per subtest so no state or segment is shared between 4H-5 and 4H-6.

## 6. Corrected reset semantics (R64-03)

**Verified API fact:** GnuCOBOL 3.2 declares and defines **`void cob_cancel(const char *name)`** (libcob `common.h`; defined at `call.c:1013`). It returns **no value**. The API provides **no synchronous failure indicator** — this specification states that directly.

**Corrections (superseding Rev6.4 §3 F-02 rows "Reset failure" and any return-value reading):**

1. **Every proposed comparison, assignment, or status interpretation of `cob_cancel()`'s return value is deleted.** There is no integer to test; no success/failure value is invented.
2. `reset_flag = 1` is a **request** to invoke `cob_cancel(prog_name)` after full frame validation (Rev6.4.1 §8 order) and **before** entry re-resolution and the call. `reset_flag = 0` preserves state (unchanged Rev5 behavior). `reset_flag ≥ 2` remains a frame-semantics fault ⇒ `_exit(11)` (unchanged — that rule is about frame validity, not cancellation).
3. **What the worker can observe on normal return:** only that the function returned (control flow continued). A normal return does **not** independently prove that the program's state was reset.
4. **Process-level failure modes are the only failure modes.** Verified from the GnuCOBOL sources: a `NULL` name triggers `cob_runtime_error` + `cob_stop_run(1)` (`call.c:1023–1026`), and an uninitialized runtime triggers `cob_fatal_error(COB_FERROR_INITIALIZED)`. The worker never passes `NULL` (frame validation guarantees `name_len ≥ 1`, §8). If the GnuCOBOL runtime nevertheless terminates during cancellation, the worker dies **before** replying: the supervisor records the actual outcome — raw wait status, exit code, and terminating signal (bwrap `128+sig` decode, §10 identity tuple) — classified as a **process-death outcome** per F-03. It is **never** translated into a fabricated `CAT_FATAL_ERROR`, `outcome_cat`, or `RESET_FAILED` response.
5. The Rev6.4 constructs `err="RESET_FAILED"`, the cancel-failure `CALL_ACK{…}`, and the reset-failure `_exit(10)` path are **removed**. `_exit(10)` retains exactly its Rev5 meaning (flush of a tainted `CALL_ACK`); no reset-related exit code exists.
6. **Reset request ≠ proof of reset.** The disposition of a reset is established exclusively by the **observable state comparison performed by Exp-3 after the subsequent program invocation**: the LK-OUT-VAL / LK-OUT-UNIN COMP-3 bytes recorded by sequences S1–S4 of Rev6.4 §3 F-11 (sticky accumulation pattern ×10; post-reset value vs pre-reset baseline; T3INIT constants), recorded verbatim and compared — never asserted from the call pattern.
7. A **cancellation request** (worker performed `cob_cancel(prog_name)`) and **verified state-reset behavior** (post-call bytes returned to base) remain two distinct recorded facts and are labeled as such in all evidence.

## 7. Corrected 4H-4 pkey test contract (R64-04)

Rev6.4's row reused "4H-3's RW map", which does not exist inside 4H-4's own execution path. **4H-4 (Mode 'M' sub 4; future hook) is self-contained**, following the documented kernel sequence ("Before a pkey can be used, it must first be allocated with `pkey_alloc()`" — kernel *Memory Protection Keys* documentation; syscalls `int pkey_alloc(unsigned long flags, unsigned long init_access_rights)`, `int pkey_mprotect(unsigned long start, size_t len, unsigned long prot, int pkey)`):

```c
/* 4H-4 — spec fragment only; not built by this pass. */
int  pkey = pkey_alloc(0, 0);                                /* step 1: valid protection key */
void *p    = mmap(NULL, 4096, PROT_READ|PROT_WRITE,
                  MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);         /* step 2: this probe's own mapping */
if (p != MAP_FAILED && pkey >= 0) {
    int r = pkey_mprotect((unsigned long)p, 4096,
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

Normative rules:

1. Every setup step is checked before `pkey_mprotect()` is invoked; the mapping and key used off-mode are **always valid** and are allocated **inside this probe** — never inherited from another subcase, test, or process.
2. **Off-mode expected result:** `pkey_mprotect(...) == 0` where PKU (or arm64 POE) and kernel support are present ⇒ **CONTROL-STRONG** (executable conversion of a valid mapping under a valid key demonstrably succeeds).
3. **PKU/kernel unavailable:** `pkey_alloc()` failing (`ENOSYS` = kernel facility absent; `EINVAL`/`EAGAIN` = no keys / CPU feature absent) ⇒ the off-mode control is **CONTROL-UNAVAILABLE** for the mechanism ⇒ the mechanism test is **INCONCLUSIVE**, never "passed". The on-mode kill remains attributable as **entry-gate** evidence (the filter fires at syscall entry before hardware support matters), but **no mechanism-prevention claim** may be recorded without a CONTROL-STRONG off-mode control. Unsupported-hardware classification and successful-filter-enforcement classification are therefore **always separate** entries in the Exp-4 record.
4. **On-mode (Stage-2, fresh worker):** death at `pkey_mprotect` entry (bwrap `159`). Expected regardless of setup success; if setup failed, the run is still classified entry-gate-only per rule 3.
5. Seccomp comparison unchanged from Rev6.4 §6: arg index 2, `SCMP_CMP_MASKED_EQ`, mask `0x4` (`PROT_EXEC`), value `0x4`, `SCMP_ACT_KILL_PROCESS`.

## 8. Corrected CMD_CALL/CALL_ACK wire validation (R64-05)

Rev5 §2.3.2 layouts are **retained unchanged** (no design reason to alter the frame):

```
CMD_CALL  (0x02): [u8 reset_flag][u8 pad=0][u16 argc][u32 len_0..argc-1][bufs]
CALL_ACK  (0x82): [i32 cob_call_ret][i32 cobol_exit_code][u8 outcome_cat][u8 tainted]
                  [u16 err_len][u16 argc][u16 pad=0][u32 len_0..15][err][bufs]
```

**CMD_CALL (validated by the worker on untrusted input):**

- `argc ∈ [0, 16]` (`u16`, little-endian). There are **exactly `argc` length fields**; unused request slots **do not exist** and are neither inspected nor validated.
- Each present `len_i ≤ 16384`; `Σ len_i ≤ 32768`, accumulated with an overflow-safe widening step (`if (sum + len_i > 32768) reject` in `uint64_t`).
- **`payload_len = 4 + (4 × argc) + Σ len_i`** — lengths and buffers must consume the declared payload **exactly** (trailing bytes or shortfall ⇒ fault).
- `pad == 0`; `reset_flag ∈ {0,1}` (values ≥ 2 ⇒ semantic frame fault, `_exit(11)`).
- Maximum re-check against the layout: `4 + 4×16 + 32768 = 32836` — matches the Rev5 `CMD_CALL` payload max **32836** ✓ (frame bound 33880 governed by `CALL_ACK`, below).

**CALL_ACK (validated by the supervisor on untrusted input — Class A data, §10/Rev6.4 §3 F-10):**

- The **fixed 16-entry length array `u32 len_0..15` is always present** in full. **Unused response slots DO exist** and every slot with `i ≥ argc` **must be `0`**; any non-zero unused slot ⇒ protocol fault.
- Active slots (`i < argc`): each `len_i ≤ 16384`; `Σ_{i<argc} len_i ≤ 32768` (overflow-safe accumulation as above).
- `argc ≤ 16`; `err_len ≤ 1024`; `pad == 0`.
- **`payload_len = 16 + 64 + err_len + Σ_{i<argc} len_i`** (16-byte fixed part `[i32 ret][i32 exit_code][u8 cat][u8 tainted][u16 err_len][u16 argc][u16 pad=0]`, 64-byte length array, error text, then buffers) — exact consumption required.
- Maximum re-check: `16 + 64 + 1024 + 32768 = 33872` — matches the Rev5 `CALL_ACK` payload max **33872** ✓, and `33872 + 8 = 33880 = MAX_WIRE_FRAME_BYTES` ✓.

**Superseded wording:** Rev6.4 §7 "Flags and padding" sentence applying the unused-slot zero rule to "`CALL_ACK.len_i` for `i ≥ argc`; `CMD_CALL.len_i` for `i ≥ argc`" is superseded by the split rules above; validation-order steps (7)/(8) of Rev6.4 §7 apply **per frame** as restated here. All other §7 provisions (validation order, partial-I/O rules, state machine, `_exit(11)`, status-consistency) remain in force, with the `outcome_cat=1` clause restated by §11 of this layer.

## 9. Complete Boundary64 specification (R64-06)

**Corrections to Rev6.4 §3 F-11's class enumeration (fact-based):** the Rev6.4 receiver-class list named `SV999`/`SV99`, which **no positive fixture uses as a receiver** — they are **operand** PICTUREs (EX1FEE `LK-RATE`, EX2RND `LK-FACTOR`; verified in `rev4_extract.md` §3.1 and rev62 E-13). The corrected eight boundary classes are the eight **(fixture, target-receiver)** instances actually exercised by the Exp-3 differential corpus. The count is preserved: 8 classes × 8 boundaries = **64 uniquely identified vectors**. T3DISP (DISPLAY codecs) remains outside boundary64 — its codec behavior is owned by V7, and DISPLAY boundary parity remains inside the ≥1000-vectors/fixture Hypothesis corpus.

**Global conventions (normative for all rows):**

- Encoding per Rev5 §2.4 + rev62 E-13: COMP-3 digits = I+F, two per byte high-nibble-first; **leading pad nibble `0x0` iff the digit count is even**; sign nibble `C`=+, `D`=-, `F`=unsigned (**H4** — unsigned nibble expectation is itself H4-tagged); invalid digit/sign nibbles rejected at decode (`ERR_INVALID_PACKED`).
- Store rule: single rounding point at receiver store; truncate toward zero unless the target is `ROUNDED` (EX2RND: nearest-away-from-zero) [D-manual, unverified until recorded].
- **Fresh worker per vector** (after `INIT_ACK`, before `QUIT`), so sticky state starts at its `VALUE`; EX4UNSG receivers pre-seeded with the V5 sentinels (`12 34 5F` / `12 34 5F` / `12 34 5C`, `ERR-FLAG='30'` — the program's `MOVE 0` re-zeros the flag at entry regardless); other receivers' pre-state is declared per class and matters only where a size error holds the receiver unchanged.
- **Owner of every boundary vector: Exp-3 test 3E** (differential corpus: oracle-derived expected bytes vs recorded worker bytes, exact byte equality). V1–V7 ownership is untouched; the BV-* rows are new, distinct vectors. Future `exp3/corpus/boundary64.jsonl` files are execution artifacts, specified here normatively.
- Division-class rows (C3/C4) use **exactly terminating quotients** by construction; their [D] derivations assume the division intermediate retains at least the quotient's exact scale — any GnuCOBOL intermediate truncation is an **H1 finding** to be recorded, never pre-excused (H1 ownership remains with V3/V4).
- Validity classes: `valid` (in-range input), `overflow` (receiver capacity exceeded by design), `invalid-packed` (deliberately malformed packed-decimal input — decode-rejection probe, distinct from any negative-arithmetic condition).

**Class preambles** (fields constant within a class; repeated per row below in compressed form):

| Class | Fixture | Target field (target PICTURE, size) | Signed | I | F | Operation | Operand fields (exact PICTURE, size) | Pre-state / notes |
|---|---|---|---|---|---|---|---|---|
| C1 | #1 EX1FEE | `LK-FEE` — `PIC S9(5)V99 COMP-3`, 4 B | S | 5 | 2 | `COMPUTE LK-FEE = LK-AMOUNT * LK-RATE` (no ROUNDED, no SE clause) | `LK-AMOUNT` `PIC S9(5)V99 COMP-3` 4 B; `LK-RATE` `PIC SV999 COMP-3` 2 B | LK-IO 10 B = 4+2+4; argc=1 |
| C2 | #2 EX2RND | `LK-OUT` — `PIC S9(4)V9 COMP-3`, 3 B, **ROUNDED** | S | 4 | 1 | `COMPUTE LK-OUT ROUNDED = LK-BASE * LK-FACTOR` | `LK-BASE` `PIC S9(3)V99 COMP-3` 3 B; `LK-FACTOR` `PIC SV99 COMP-3` 2 B | LK-IO 8 B = 3+2+3 |
| C3 | #3 EX3DIVA | `LK-ACCRUAL` — `PIC S9(5)V99 COMP-3`, 4 B | S | 5 | 2 | `COMPUTE LK-ACCRUAL = (LK-NUM / LK-DEN) * LK-NOTIONAL` | `LK-NUM` `PIC S9(3) COMP-3` 2 B; `LK-DEN` `PIC S9(3) COMP-3` 2 B; `LK-NOTIONAL` `PIC S9(5) COMP-3` 3 B | LK-IO 11 B = 2+2+3+4; pre `00 00 00 0C` |
| C4 | #4 EX3DIVB | `LK-ACCRUAL` — `PIC S9(5)V99 COMP-3`, 4 B | S | 5 | 2 | same as C3 | `LK-NUM`/`LK-DEN` `PIC S9(3)` 2 B; `LK-NOTIONAL` `PIC S9(5)V99 COMP-3` 4 B | LK-IO 12 B = 2+2+4+4; pre `00 00 00 0C` |
| C5 | #5 EX4UNSG | designated target `LK-UNSG-SE` — `PIC 9(3)V99 COMP-3`, 3 B, **unsigned**, `ON SIZE ERROR` clause present | U | 3 | 2 | `COMPUTE LK-UNSG-SE = LK-A - LK-B` (with SE clause) | `LK-A`, `LK-B` `PIC S9(5)V99 COMP-3` 4 B each | LK-IO 18 B = 4+4+3+3+3+1; per call all three receivers + `LK-ERR-FLAG` (`PIC 9`, DISPLAY) are written — each row's expectation lists all outputs |
| C6 | #6 T2MULTI | `LK-SUM` — `PIC S9(5)V99 COMP-3`, 4 B | S | 5 | 2 | `COMPUTE LK-SUM = LK-A + LK-B` (no clause) | `LK-A`, `LK-B` `PIC S9(5)V99 COMP-3` 4 B each | 3× 01 params (argc=3, lens 4/4/4); V6 owner (Exp-2/2A) unaffected — BV-C6-* are 3E-only |
| C7 | #9 T3STATE | `LK-OUT-VAL` — `PIC S9(5) COMP-3`, 3 B | S | 5 | 0 | `ADD LK-STEP TO WS-ACC-VAL` then `MOVE WS-ACC-VAL TO LK-OUT-VAL`; sticky; `WS-ACC-VAL VALUE +10`; fresh worker ⇒ ACC = +10 at entry | `LK-STEP` `PIC S9(5) COMP-3` 3 B | LK-IO 9 B = 3+3+3; `LK-OUT-UNIN` output every row = **[H5]** |
| C8 | #10 T3INIT | `LK-OUT-VAL` — `PIC S9(5) COMP-3`, 3 B | S | 5 | 0 | same as C7; `IS INITIAL` ⇒ WS re-initialized **per activation** ⇒ ACC = +10 at **every** call entry (deterministic even on a reused worker — the C7/C8 observable difference) | `LK-STEP` `PIC S9(5) COMP-3` 3 B | as C7; `LK-OUT-UNIN` = **[H5]** per call |

**Boundary definitions (corrected, normative):** B1 exact zero; B2 positive maximum representable magnitude `10^I - 10^-F`; B3 negative maximum `-(10^I - 10^-F)` for signed targets; for the unsigned class C5, B3 is instead the **invalid-sign-encoding probe** (a malformed packed sign nibble — a decode-rejection condition, *not* a negative arithmetic value; negative-into-unsigned arithmetic remains owned by V5 with the H3∧H4 policy set P1/P2/P3); B4 minimum representable nonzero unit `10^-F` (**for F=0 this is `1` — an integer unit, not a fractional magnitude**); B5 positive maximum minus one least-significant unit; B6 first positive overflow value `10^I` (no I=0 class exists in the corrected set, so the `10^0` edge is documented as n/a); B7 exact half-unit case at the target scale (`0.5 × 10^-F`; for F=0: `0.5`), requiring the input operands to represent the additional fractional digit exactly; B8 deterministic scale-edge value with an additional **nonzero** fractional digit beyond the target scale.

**The 64 rows.** Operand cell grammar: `FIELD=<exact decimal> `<bytes>``. Result cell: expected receiver bytes + tag, or the OPEN reason. All encodings below were machine-re-verified from the E-13 codec rules (digit counts, pad-nibble rule, sign nibbles).

**C1 — EX1FEE → LK-FEE (S9(5)V99, I=5, F=2, signed; truncating store):**

| Vector ID | B | Operand values → bytes | Signed | I,F | Reference-model operation | Target-store behavior | Expected result / status | Validity |
|---|---|---|---|---|---|---|---|---|
| BV-C1-B1 | B1 | `LK-AMOUNT=+123.45` `00 12 34 5C`; `LK-RATE=+0.000` `00 0C` | S | 5,2 | 123.45 × 0 = 0 (exact) | trunc to (5,2) | `00 00 00 0C` [D] | valid |
| BV-C1-B2 | B2 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |
| BV-C1-B3 | B3 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |
| BV-C1-B4 | B4 | `LK-AMOUNT=+0.08` `00 00 00 8C`; `LK-RATE=+0.125` `12 5C` | S | 5,2 | 0.08 × 0.125 = 0.01 = 10⁻² (exact) | trunc | `00 00 00 1C` [D] | valid |
| BV-C1-B5 | B5 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |
| BV-C1-B6 | B6 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |
| BV-C1-B7 | B7 | `LK-AMOUNT=+0.01` `00 00 00 1C`; `LK-RATE=+0.500` `50 0C` | S | 5,2 | 0.01 × 0.500 = 0.005 = exact half-unit (operand has the extra digit) | trunc (no ROUNDED): tie truncates toward zero | `00 00 00 0C` [D] | valid |
| BV-C1-B8 | B8 | `LK-AMOUNT=+123.45` `00 12 34 5C`; `LK-RATE=+0.001` `00 1C` | S | 5,2 | 123.45 × 0.001 = 0.12345 (extra nonzero frac digit 3) | trunc | `00 00 01 2C` [D] | valid |

C1 OPEN reasons (B2/B3/B5/B6): `|LK-RATE| ≤ 0.999` ⇒ `|product| ≤ 99999.99 × 0.999 = 99899.99001 < 99999.99` — EX1FEE **cannot reach** ±max, max-ulp, or overflow. Smallest compatible resolution (proposal, non-normative): substitute sentinel rows `LK-AMOUNT=±99999.99`, `LK-RATE=±0.999` → ±99899.99 → `98 99 99 9C`/`98 99 99 9D` [D], explicitly labeled *nearest-reachable sentinels, not B2/B3/B5/B6*; PICTURE-level max/overflow coverage for S9(5)V99 is carried by C4 and C6 (same receiver PICTURE). No fixture change proposed.

**C2 — EX2RND → LK-OUT (S9(4)V9, I=4, F=1, signed; ROUNDED nearest-away):**

| Vector ID | B | Operand values → bytes | Signed | I,F | Reference-model operation | Target-store behavior | Expected result / status | Validity |
|---|---|---|---|---|---|---|---|---|
| BV-C2-B1 | B1 | `LK-BASE=+12.34` `01 23 4C`; `LK-FACTOR=+0.00` `00 0C` | S | 4,1 | 12.34 × 0 = 0 | ROUNDED (no-op at 0) | `00 00 0C` [D] | valid |
| BV-C2-B2 | B2 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |
| BV-C2-B3 | B3 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |
| BV-C2-B4 | B4 | `LK-BASE=+1.00` `00 10 0C`; `LK-FACTOR=+0.10` `01 0C` | S | 4,1 | 1.00 × 0.10 = 0.1 = 10⁻¹ (exact) | ROUNDED (no-op) | `00 00 1C` [D] | valid |
| BV-C2-B5 | B5 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |
| BV-C2-B6 | B6 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |
| BV-C2-B7 | B7 | `LK-BASE=+0.25` `00 02 5C`; `LK-FACTOR=+0.20` `02 0C` | S | 4,1 | 0.25 × 0.20 = 0.05 = exact half-unit | ROUNDED nearest-away: 0.05 → **0.1** | `00 00 1C` [D] | valid |
| BV-C2-B8 | B8 | `LK-BASE=+1.23` `00 12 3C`; `LK-FACTOR=+0.40` `04 0C` | S | 4,1 | 1.23 × 0.40 = 0.492 (extra frac digits 9,2) | ROUNDED: 0.492 → **0.5** | `00 00 5C` [D] | valid |

C2 OPEN reasons (B2/B3/B5/B6): `|product| ≤ 999.99 × 0.99 = 989.9901 ≪ 9999.8` — EX2RND cannot reach ±max, max-ulp, or `10^4`. Resolution proposal: nearest-reachable sentinel row (`LK-BASE=+999.99`, `LK-FACTOR=+0.99` → 989.9901 → ROUNDED 990.0 → `09 90 00 0C` [D]-derived, labeled not-B2); S9(4)V9 max/overflow coverage has no other owning fixture — documented corpus limitation.

**C3 — EX3DIVA → LK-ACCRUAL (S9(5)V99, I=5, F=2; NOTIONAL integer):**

| Vector ID | B | Operand values → bytes | Signed | I,F | Reference-model operation | Target-store behavior | Expected result / status | Validity |
|---|---|---|---|---|---|---|---|---|
| BV-C3-B1 | B1 | `LK-NUM=+0` `00 0C`; `LK-DEN=+3` `00 3C`; `LK-NOTIONAL=+10000` `10 00 0C` | S | 5,2 | (0/3) × 10000 = 0 | trunc | `00 00 00 0C` [D] | valid |
| BV-C3-B2 | B2 | `LK-NUM=+239` `23 9C`; `LK-DEN=+100` `10 0C`; `LK-NOTIONAL=+41841` `41 84 1C` | S | 5,2 | (239/100) × 41841 = 2.39 × 41841 = 99999.99 exactly (terminating quotient; H1-insensitive by construction, recorded) | trunc (no-op) | `99 99 99 9C` [D] | valid |
| BV-C3-B3 | B3 | `LK-NUM=-239` `23 9D`; `LK-DEN=+100` `10 0C`; `LK-NOTIONAL=+41841` `41 84 1C` | S | 5,2 | = -99999.99 exactly | trunc (no-op) | `99 99 99 9D` [D] | valid |
| BV-C3-B4 | B4 | `LK-NUM=+1` `00 1C`; `LK-DEN=+100` `10 0C`; `LK-NOTIONAL=+1` `00 00 1C` | S | 5,2 | (1/100) × 1 = 0.01 = 10⁻² | trunc (no-op) | `00 00 00 1C` [D] | valid |
| BV-C3-B5 | B5 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |
| BV-C3-B6 | B6 | `LK-NUM=+999` `99 9C`; `LK-DEN=+1` `00 1C`; `LK-NOTIONAL=+99999` `99 99 9C` | S | 5,2 | 999 × 99999 = 99,899,001 ≫ 10⁵ | size error; **no clause** ⇒ store policy = **H3** (reference model: receiver unchanged) | result bytes [H3] | overflow |
| BV-C3-B7 | B7 | `LK-NUM=+1` `00 1C`; `LK-DEN=+200` `20 0C`; `LK-NOTIONAL=+1` `00 00 1C` | S | 5,2 | (1/200) × 1 = 0.005 = exact half-unit | trunc | `00 00 00 0C` [D] | valid |
| BV-C3-B8 | B8 | `LK-NUM=+1` `00 1C`; `LK-DEN=+200` `20 0C`; `LK-NOTIONAL=+3` `00 00 3C` | S | 5,2 | (1/200) × 3 = 0.015 (extra digit 5) | trunc | `00 00 00 1C` [D] | valid |

C3-B5 OPEN reason: 99999.98 = 4999999/50 with **4999999 prime** (verified by factorization this pass); (n/d)×N = 99999.98 with n,d ≤ 999, N ≤ 99999 (integer) requires n×N = 4999999 × 50k — impossible. No resolution without changing fixture operands (out of scope); S9(5)V99 B5 coverage is carried by C4-B5 and C6-B5 at the same receiver PICTURE.

**C4 — EX3DIVB → LK-ACCRUAL (S9(5)V99; NOTIONAL has V99):**

| Vector ID | B | Operand values → bytes | Signed | I,F | Reference-model operation | Target-store behavior | Expected result / status | Validity |
|---|---|---|---|---|---|---|---|---|
| BV-C4-B1 | B1 | `LK-NUM=+0` `00 0C`; `LK-DEN=+3` `00 3C`; `LK-NOTIONAL=+10000.00` `10 00 00 0C` | S | 5,2 | 0 | trunc | `00 00 00 0C` [D] | valid |
| BV-C4-B2 | B2 | `LK-NUM=+1` `00 1C`; `LK-DEN=+1` `00 1C`; `LK-NOTIONAL=+99999.99` `99 99 99 9C` | S | 5,2 | (1/1) × 99999.99 = +max exactly | trunc (no-op) | `99 99 99 9C` [D] | valid |
| BV-C4-B3 | B3 | `LK-NUM=+1` `00 1C`; `LK-DEN=+1` `00 1C`; `LK-NOTIONAL=-99999.99` `99 99 99 9D` | S | 5,2 | = -max exactly | trunc (no-op) | `99 99 99 9D` [D] | valid |
| BV-C4-B4 | B4 | `LK-NUM=+1` `00 1C`; `LK-DEN=+1` `00 1C`; `LK-NOTIONAL=+0.01` `00 00 00 1C` | S | 5,2 | 0.01 = 10⁻² | trunc (no-op) | `00 00 00 1C` [D] | valid |
| BV-C4-B5 | B5 | `LK-NUM=+1` `00 1C`; `LK-DEN=+1` `00 1C`; `LK-NOTIONAL=+99999.98` `99 99 99 8C` | S | 5,2 | = max - ulp exactly | trunc (no-op) | `99 99 99 8C` [D] | valid |
| BV-C4-B6 | B6 | `LK-NUM=+500` `50 0C`; `LK-DEN=+1` `00 1C`; `LK-NOTIONAL=+200.00` `00 20 00 0C` | S | 5,2 | 500 × 200.00 = 100000 = 10⁵ exactly | size error; no clause ⇒ **H3** | result bytes [H3] | overflow |
| BV-C4-B7 | B7 | `LK-NUM=+1` `00 1C`; `LK-DEN=+200` `20 0C`; `LK-NOTIONAL=+1.00` `00 00 10 0C` | S | 5,2 | (1/200) × 1.00 = 0.005 = exact half-unit | trunc | `00 00 00 0C` [D] | valid |
| BV-C4-B8 | B8 | `LK-NUM=+1` `00 1C`; `LK-DEN=+200` `20 0C`; `LK-NOTIONAL=+3.00` `00 00 30 0C` | S | 5,2 | 0.015 (extra digit 5) | trunc | `00 00 00 1C` [D] | valid |

**C5 — EX4UNSG → `LK-UNSG-SE` (9(3)V99, unsigned, I=3, F=2, SE clause present).** Each row's expected outputs cover all four written fields: `UNSG-SE` (designated target), `UNSG-TR` (unsigned, **no** clause), `SIGN-TR` (S9(3)V99, no clause), `ERR-FLAG` (ASCII `30`/`31`). Unsigned receiver bytes carry the **H4** nibble expectation (`F`).

| Vector ID | B | Operand values → bytes | Signed | I,F | Reference-model operation | Target-store behavior | Expected result / status | Validity |
|---|---|---|---|---|---|---|---|---|
| BV-C5-B1 | B1 | `LK-A=+123.45` `00 12 34 5C`; `LK-B=+123.45` `00 12 34 5C` | U | 3,2 | 0.00 | stores (no SE) | SE `00 00 0F`; TR `00 00 0F` [H4-nib]; SIGN-TR `00 00 0C` [D]; FLAG `30` [D] | valid |
| BV-C5-B2 | B2 | `LK-A=+1100.00` `01 10 00 0C`; `LK-B=+100.01` `00 10 00 1C` | U | 3,2 | +999.99 = +max (unsigned 9(3)V99) | stores | SE `99 99 9F`; TR `99 99 9F` [H4-nib]; SIGN-TR `99 99 9C`; FLAG `30` | valid |
| BV-C5-B3 | B3 | `LK-A=+10.00` `00 01 00 0B` (encoding of +10.00 with the sign nibble C replaced by the **invalid `0xB`**; valid nibbles are C/D/F only); `LK-B=+0.00` `00 00 00 0C` | U | 3,2 | source decode rejection (`ERR_INVALID_PACKED`) — **a decode condition, not a negative value** | recorded-not-asserted | outcome category per the 2E hypothesis disposition [H]; all bytes recorded verbatim | **invalid-packed** |
| BV-C5-B4 | B4 | `LK-A=+10.01` `00 01 00 1C`; `LK-B=+10.00` `00 01 00 0C` | U | 3,2 | +0.01 = 10⁻² | stores | SE `00 00 1F`; TR `00 00 1F` [H4-nib]; SIGN-TR `00 00 1C`; FLAG `30` | valid |
| BV-C5-B5 | B5 | `LK-A=+1100.00` `01 10 00 0C`; `LK-B=+100.02` `00 10 00 2C` | U | 3,2 | +999.98 = max - ulp | stores | SE `99 99 8F`; TR `99 99 8F` [H4-nib]; SIGN-TR `99 99 8C`; FLAG `30` | valid |
| BV-C5-B6 | B6 | `LK-A=+1100.00` `01 10 00 0C`; `LK-B=+100.00` `00 10 00 0C` | U | 3,2 | +1000.00 = 10³ → size error on SE and TR and SIGN-TR statements | SE clause: receiver **unchanged** (`12 34 5F`) + `MOVE 1` ⇒ FLAG `31` [D]; TR and SIGN-TR have **no** clause ⇒ **H3** | SE unchanged `12 34 5F` + FLAG `31` [D]; TR [H3]; SIGN-TR [H3] | overflow |
| BV-C5-B7 | B7 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |
| BV-C5-B8 | B8 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |

C5-B7/B8 OPEN reason (structural): `LK-A - LK-B` with both operands at quantum 10⁻² can only produce multiples of 10⁻² — `0.005` (half-unit, 3 fractional digits) and any third-fraction-digit value are **unrepresentable by the actual source operands**. Resolution proposal: none without changing operand PICTUREs (out of scope); scale-edge and half-unit coverage for boundary classes is carried by C1–C4 rows; the 9(3)V99 receiver class therefore has documented B7/B8 coverage gaps.

**C6 — T2MULTI → LK-SUM (S9(5)V99, I=5, F=2; no clause):**

| Vector ID | B | Operand values → bytes | Signed | I,F | Reference-model operation | Target-store behavior | Expected result / status | Validity |
|---|---|---|---|---|---|---|---|---|
| BV-C6-B1 | B1 | `LK-A=+123.45` `00 12 34 5C`; `LK-B=-123.45` `00 12 34 5D` | S | 5,2 | 0 exactly | trunc | `00 00 00 0C` [D] | valid |
| BV-C6-B2 | B2 | `LK-A=+99999.98` `99 99 99 8C`; `LK-B=+0.01` `00 00 00 1C` | S | 5,2 | +99999.99 = +max | trunc (no-op) | `99 99 99 9C` [D] | valid |
| BV-C6-B3 | B3 | `LK-A=-99999.98` `99 99 99 8D`; `LK-B=-0.01` `00 00 00 1D` | S | 5,2 | -99999.99 = -max | trunc (no-op) | `99 99 99 9D` [D] | valid |
| BV-C6-B4 | B4 | `LK-A=+0.01` `00 00 00 1C`; `LK-B=+0.00` `00 00 00 0C` | S | 5,2 | +0.01 = 10⁻² | trunc (no-op) | `00 00 00 1C` [D] | valid |
| BV-C6-B5 | B5 | `LK-A=+99999.99` `99 99 99 9C`; `LK-B=-0.01` `00 00 00 1D` | S | 5,2 | +99999.98 = max - ulp | trunc (no-op) | `99 99 99 8C` [D] | valid |
| BV-C6-B6 | B6 | `LK-A=+99999.99` `99 99 99 9C`; `LK-B=+0.01` `00 00 00 1C` | S | 5,2 | +100000.00 = 10⁵ → size error | no clause ⇒ **H3** | result bytes [H3] | overflow |
| BV-C6-B7 | B7 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |
| BV-C6-B8 | B8 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |

C6-B7/B8 OPEN reason: a sum of quantum-10⁻² operands is a multiple of 10⁻²; `0.005` and any extra fractional digit are structurally unrepresentable. Same resolution posture as C5.

**C7 — T3STATE → LK-OUT-VAL (S9(5), I=5, F=0, signed; sticky, fresh worker ⇒ ACC = +10 at entry):**

| Vector ID | B | Operand values → bytes | Signed | I,F | Reference-model operation | Target-store behavior | Expected result / status | Validity |
|---|---|---|---|---|---|---|---|---|
| BV-C7-B1 | B1 | `LK-STEP=-10` `00 01 0D` | S | 5,0 | 10 + (-10) = 0 | integer store | VAL `00 00 0C` [D]; UNIN [H5] | valid |
| BV-C7-B2 | B2 | `LK-STEP=+99989` `99 98 9C` | S | 5,0 | 10 + 99989 = 99999 = +max | integer store | `99 99 9C` [D]; UNIN [H5] | valid |
| BV-C7-B3 | B3 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |
| BV-C7-B4 | B4 | `LK-STEP=-9` `00 00 9D` | S | 5,0 | 10 - 9 = 1 = 10⁰ (integer unit — F=0 rule) | integer store | `00 00 1C` [D]; UNIN [H5] | valid |
| BV-C7-B5 | B5 | `LK-STEP=+99988` `99 98 8C` | S | 5,0 | 10 + 99988 = 99998 = max - 1 | integer store | `99 99 8C` [D]; UNIN [H5] | valid |
| BV-C7-B6 | B6 | `LK-STEP=+99990` `99 99 0C` | S | 5,0 | 10 + 99990 = 100000 = 10⁵ → size error | `ADD … TO` with no clause ⇒ **H3** | result bytes [H3]; UNIN [H5] | overflow |
| BV-C7-B7 | B7 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |
| BV-C7-B8 | B8 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |

C7-B3 OPEN reason: ACC_after = 10 + STEP with `STEP ∈ [-99999, +99999]` ⇒ min reachable = **-99989 > -99999**: the -max boundary is unreachable in a single call because of the +10 base. Smallest compatible resolution (proposal): a documented **two-call sticky sequence** (call 1 `LK-STEP=-50004` `50 00 4D` → ACC -49994; call 2 `LK-STEP=-50005` `50 00 5D` → ACC -99999 → `99 99 9D` [D]); adopting a sequence-shaped boundary vector is a design decision ⇒ row remains OPEN. C7-B7/B8 OPEN reason: integer operands ⇒ integer results only; `0.5` and sub-unit fractional digits are unrepresentable. `LK-OUT-UNIN` is [H5] on every row (un-VALUED accumulator).

**C8 — T3INIT → LK-OUT-VAL (S9(5); `IS INITIAL` ⇒ re-initialized to `VALUE +10` per activation):**

| Vector ID | B | Operand values → bytes | Signed | I,F | Reference-model operation | Target-store behavior | Expected result / status | Validity |
|---|---|---|---|---|---|---|---|---|
| BV-C8-B1 | B1 | `LK-STEP=-10` `00 01 0D` | S | 5,0 | 10 - 10 = 0 | integer store | VAL `00 00 0C` [D]; UNIN [H5] | valid |
| BV-C8-B2 | B2 | `LK-STEP=+99989` `99 98 9C` | S | 5,0 | 99999 = +max | integer store | `99 99 9C` [D]; UNIN [H5] | valid |
| BV-C8-B3 | B3 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |
| BV-C8-B4 | B4 | `LK-STEP=-9` `00 00 9D` | S | 5,0 | 1 = 10⁰ | integer store | `00 00 1C` [D]; UNIN [H5] | valid |
| BV-C8-B5 | B5 | `LK-STEP=+99988` `99 98 8C` | S | 5,0 | 99998 = max - 1 | integer store | `99 99 8C` [D]; UNIN [H5] | valid |
| BV-C8-B6 | B6 | `LK-STEP=+99990` `99 99 0C` | S | 5,0 | 100000 = 10⁵ → size error | no clause ⇒ **H3** | result bytes [H3]; UNIN [H5] | overflow |
| BV-C8-B7 | B7 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |
| BV-C8-B8 | B8 | **OPEN — REQUIRES DESIGN DECISION** | | | | | | |

C8-B3 OPEN reason: identical arithmetic bound as C7, **and structurally stronger** — `IS INITIAL` re-bases ACC at +10 for every call, so no cross-call accumulation (the C7 proposal) can even be expressed. No resolution without a fixture change (out of scope). C8-B7/B8: same as C7.

**Boundary64 summary:** 64 uniquely identified vectors (`BV-C1-B1` … `BV-C8-B8`); **45 fully specified** (valid/overflow/invalid-packed inputs with exact operand bytes and oracle-derived expected bytes or H-tagged recorded outcomes); **19 OPEN — REQUIRES DESIGN DECISION** (C1: B2/B3/B5/B6; C2: B2/B3/B5/B6; C3: B5; C5: B7/B8; C6: B7/B8; C7: B3/B7/B8; C8: B3/B7/B8), each with a verified unrepresentability reason and, where one exists, a smallest compatible resolution proposal. AC-06 is correspondingly **PARTIALLY CLOSED**. This is the honest expressiveness map of the existing fixture set — not a deficiency silently papered over.

## 10. Supervisor worker-identity procedure (R64-07)

Supersedes the Rev6.4 §3 F-10 Class-B bullet "worker PID/process identity (supervisor-spawned child; `waitpid`)": `waitpid()` identifies only the supervisor's **direct child — the bwrap launcher** (the Rev5 launch chain `prlimit → setpriv → env -i → bwrap` is a pure exec chain, so one PID) — and the final exit status. The worker inside bwrap's PID namespace requires **host-side discovery**, independent of anything EVILMOD reports:

1. **Launcher PID:** the supervisor records the PID returned by its `fork()`; the exec chain preserves it ⇒ this is the bwrap launcher PID `L`.
2. **Worker host-PID discovery:** scan host `/proc/[0-9]+/stat` for candidates whose parent PID (field 4) equals `L`; for each candidate read `/proc/<P>/status` and select those whose **`NSpid`** field has **≥ 2 entries** (membership in a nested PID namespace; bwrap itself has a single host-only entry). Expected shape: `NSpid: <host_pid> 1` (host PID first, sandbox-namespace PID `1` last), consistent with bwrap's single-process sandbox design.
3. **Cgroup confirmation:** `/proc/<P>/cgroup` must list membership in the experiment's cgroup (`…/necro.slice/spike.scope`, Rev5 §8); a candidate outside it is rejected.
4. **Executable identity:** `readlink /proc/<P>/exe` must resolve to the sandboxed worker binary path; recorded (subject to the ptrace access check — permissions paragraph below).
5. **`NSpid` hierarchy recorded verbatim** (space-separated list).
6. **Host vs innermost:** evidence labels distinguish `host_pid` (first `NSpid` entry) from the innermost namespace PID (last entry, expected `1`); every "worker PID" claim means `host_pid`.
7. **Correlation tuple:** `{host_pid, NSpid list, cgroup path, exe path, launcher PID}` recorded as one identity tuple; any component mismatch invalidates the observation and raises a finding.
8. **PID-reuse defense:** immediately `pidfd_open(host_pid)` and hold the fd (immune to reuse); additionally record `/proc/<P>/stat` field 22 (**starttime**) and re-verify it (or poll the pidfd) before each later read of the same identity. A mismatch ⇒ the observation is invalidated and a finding recorded.
9. **Multiple candidates:** if more than one process satisfies the full tuple (not expected under the single-process design), **all** candidates are recorded with their tuples and the observation set is marked ambiguous/degraded; no silent selection.
10. **Worker exits before observation:** `/proc/<P>/…` reads fail (ENOENT) or the pidfd reports hang-up ⇒ the property is recorded **UNAVAILABLE-EXITED** — never back-filled from Class-A (module-reported) diagnostics.

**Permissions (declared):** reads of `/proc/<pid>/{root,exe,fd,maps,ns/*,mountinfo,status}` are governed by the kernel's ptrace access checks (`PTRACE_MODE_READ_FSCREDS`; proc(5)). The supervisor must run as **host root in the initial user namespace** (the Rev5 Exp-4 posture); a UID-0 identity mapped inside an unprivileged user namespace does **not** satisfy these checks against host processes. Host `/proc` mount options (e.g. `hidepid`) can additionally deny visibility; the supervisor records its own `/proc/self/mountinfo` proc flags. **Any property that cannot be read independently is recorded UNAVAILABLE with the reason; module-reported values are never substituted.** All other Class-B items (uid/gid via `/proc/<pid>/status`, caps, `Seccomp`/`Seccomp_filters`, exit status via `waitpid(L)`, cgroup events, host-side hashes/framing counts) keep their Rev6.4 collection methods, now keyed by the identity tuple above instead of a bare `waitpid` PID.

## 11. Corrected CAT_STOP_RUN contract (R64-08)

One unambiguous expected-response contract for Exp-2 test 2D (fixture T2STOP, which is **parser-rejected as NVS-0** — `RETURN-CODE`/`STOP RUN` are reserved — and **separately compiled directly with `cobc` for the runtime test**; the two roles are distinct and both stand):

1. **API return category (mandatory normative assertions [D-manual]):** `cob_call_ret = 1`, `outcome_cat = CAT_STOP_RUN (1)`, `tainted = 1` — per the documented GnuCOBOL category mapping (Rev5 §2.3.2), unchanged.
2. **`cobol_exit_code = 42` is a normative expected assertion derived from the fixture source** (`MOVE 42 TO RETURN-CODE` before `STOP RUN`) — the COBOL `RETURN-CODE` value at STOP RUN, carried in the `CALL_ACK` i32 field. Its **empirical propagation through the worker/runtime is Unverified until Exp-2 records it**; the assertion and the empirical status are different layers and are both stated, with no double language. The Rev6.4 "recorded-not-asserted" label for this field is **superseded**.
3. **Acceptance condition (gate = status-consistency rule, single source):** 2D PASS requires the exact observation `{ret=1, cat=1, tainted=1, cobol_exit_code=42}` plus the flush-then-`_exit(10)` worker exit. A recorded `cobol_exit_code ≠ 42` is a **spec-vs-runtime finding** (fail-visible, recorded, dispositioned) — never silently accepted, never pre-excused by this specification. The Rev6.4 §7 clause "`cobol_exit_code` must equal the STOP RUN code" is restated as: `outcome_cat = 1` ⇒ `cobol_exit_code` = the COBOL `RETURN-CODE` at STOP RUN, fixture-derived (T2STOP: 42) — identical rule in the consistency table and the gate.
4. **Layer distinction:** `cobol_exit_code` (42, in-protocol, COBOL level) ≠ the worker's `_exit(10)` (protocol-mandated tainted-exit, host-visible via the bwrap decode). 2D records both; neither is reported as the other.

## 12. Supersession table (old Rev6.4 statement → Rev6.4.1 replacement)

| # | Rev6.4 location (unchanged file) | Superseded statement | Replacement |
|---|---|---|---|
| 1 | §3 F-01 code fragment | `seccomp_rule_add_array(ctx2, …, syscall(__NR_shmat), 1, SCMP_CMP(…))` | §4: `seccomp_syscall_resolve_name` + `seccomp_rule_add_exact_array` + typed `struct scmp_arg_cmp[1]`; rule semantics unchanged |
| 2 | §3 F-01 completeness/failure text | implicit failure mapping | §4 five-case fail-closed table (name/arch/comparison/rule-add/load) |
| 3 | §3 F-02 "Reset failure" row | `cob_cancel(prog_name) != 0` → `RESET_FAILED` ACK → `_exit(10)` | §6: void API; process-level handling only; no fabricated category/exit |
| 4 | §3 F-02 "Does reset invoke…", "Cancel vs…" rows | retained semantics, restated | §6 (unchanged meaning, corrected evidencing) |
| 5 | §3 F-03 CAT_STOP_RUN row | `cobol_exit_code=42` "recorded-not-asserted" + exact-response wording | §11 single contract |
| 6 | §3 F-03 revised gate (b) | "exact observations above" (ambiguous for 42) | §11 acceptance condition (identical rule in gate and consistency) |
| 7 | §3 F-09 row 4H-4 | "4H-3's RW map reused"; unguarded `pkey_mprotect(p,…,-1)` | §7 self-contained alloc→mmap→pkey_mprotect contract |
| 8 | §3 F-09 rows 4H-5/4H-6 | `shmget(…, 0600)`; single control grading | §5 `IPC_CREAT\|0700` + ownership/`IPC_STAT` checks; CONTROL-INVALID/UNAVAILABLE/STRONG; fresh-worker independence; cleanup/kill semantics |
| 9 | §3 F-10 Class B bullet 1 | "worker PID/process identity (supervisor-spawned child; `waitpid`)" | §10 identity-tuple discovery procedure; `waitpid` = launcher only |
| 10 | §3 F-11 boundary64 paragraphs | 8-class recipe (incl. `SV999`/`SV99` as receiver classes); B4/B8 ambiguities; unsigned-B3 gap | §9 corrected 8-instance enumeration + full 64-row table; 19 rows OPEN |
| 11 | §6 matrix rows 4H-4/5/6 | probe details (mode/segment-mode/reuse) | §5/§7; rule actions and comparisons unchanged |
| 12 | §7 "Flags and padding" | unused-slot zero rule applied to `CMD_CALL.len_i (i ≥ argc)` | §8 split CMD_CALL/CALL_ACK validation + recomputed payload formulas |
| 13 | §7 status-consistency | "`cobol_exit_code` … must equal the STOP RUN code (2D expectation: 42, Unverified)" | §11 clause 3 (single rule, gate-consistent) |

Nothing else in Rev6.4 is modified; in particular §1–§2, F-04…F-08, F-10 (other bullets), F-12, F-13/§7 (remainder), §12 (P0), §13 AC-01…AC-17 (as amended by this layer's §13 for AC-06), §14, §15 remain controlling.

## 13. Acceptance checklist

| ID | Condition | Disposition | Note |
|---|---|---|---|
| AC-01 | Correct libseccomp API usage and syscall resolution | **CLOSED — DOCUMENTATION** | §4, verified against v2.6.0 declarations; compilation remains unexecuted |
| AC-02 | Executable shared-memory permission sufficient for the off-mode control | **CLOSED — DOCUMENTATION** | §5 (`IPC_CREAT\|0700`, owner==attacher euid, `IPC_STAT` checks; kernel `S_IXUGO` path verified) |
| AC-03 | `cob_cancel()` return semantics accurate | **CLOSED — DOCUMENTATION** | §6 (void API verified; no invented status remains) |
| AC-04 | 4H-4 uses independently established mapping and valid key | **CLOSED — DOCUMENTATION** | §7 |
| AC-05 | Request and response unused-length rules correct | **CLOSED — DOCUMENTATION** | §8 (formulas recomputed; maxima re-verified 32836/33872/33880) |
| AC-06 | All 64 boundary vectors reconstructible | **PARTIALLY CLOSED** | §9: 45 rows fully reconstructible; **19 rows OPEN — REQUIRES DESIGN DECISION** (verified structural unrepresentability, each with a proposed smallest resolution) |
| AC-07 | Supervisor-side host PID discovery specified | **CLOSED — DOCUMENTATION** | §10 |
| AC-08 | CAT_STOP_RUN expectations and gate rules agree | **CLOSED — DOCUMENTATION** | §11 |
| AC-09 | Rev6.4 unchanged and hashes still match | **CLOSED — DOCUMENTATION** | §2 (pre/post `sha256sum -c` 2/2, 6/6, 11/11 OK) |
| AC-10 | P0 disposition unchanged | **CLOSED — DOCUMENTATION** | §2; amendment digest unchanged |
| AC-11 | No implementation or technical experiment took place | **CLOSED — DOCUMENTATION** | §15 footer; read-only verification only (source clones/fetches removed after inspection) |

## 14. Remaining design decisions

1. **The 19 OPEN boundary vectors** (§9): adopt or reject the proposed smallest resolutions (nearest-reachable sentinels for C1/C2; two-call sequence for C7-B3; documented coverage gaps for B7/B8 on quantum-limited classes and C3-B5/C8-B3). Decision owner: specification maintainer; no fixture changes are proposed.
2. Q8 (post-census Stage-2 tightening), the broker-architecture option, and the P0 closure channel (user-owned) carry over from Rev6.4 §14 unchanged.
3. Implementation-fidelity checkpoint: the corrected fragments (§4, §5, §7) and procedures (§10) must be materialized exactly as specified in any future authorized implementation; deltas become new findings.

## 15. Change log (Rev 6.4 → Rev 6.4.1)

1. R64-01: seccomp fragment corrected (runtime name resolution; typed comparison array; exact-array variant); five-case fail-closed table added; verified against libseccomp v2.6.0 headers.
2. R64-02: 4H-5/4H-6 shm contract corrected (mode 0700 + ownership + `IPC_STAT`; CONTROL-INVALID/UNAVAILABLE/STRONG; independent fresh-worker controls; namespace-teardown kill semantics; supervisor `/proc` corroboration declared with feasibility limits). Kernel `acc_mode |= S_IXUGO` path verified.
3. R64-03: reset semantics corrected to the void `cob_cancel()` API; all return-value logic removed; process-level death recording; reset request ≠ proof of reset.
4. R64-04: 4H-4 made self-contained (pkey_alloc → own mmap → checked pkey_mprotect); PKU-absent ⇒ CONTROL-UNAVAILABLE/INCONCLUSIVE, entry-gate vs mechanism evidence separated.
5. R64-05: CMD_CALL/CALL_ACK validation split; nonexistent request slots no longer validated; response unused slots mandatorily zero; payload formulas restated; maxima re-verified.
6. R64-06: receiver-class enumeration corrected (actual fixture receivers); complete 64-row Boundary64 table with machine-verified encodings; B1–B8 definitions corrected (B4 F=0 unit; B6 I=0 n/a; unsigned B3 = invalid-sign probe); 45 rows specified, 19 OPEN with reasons and proposals.
7. R64-07: supervisor worker-identity procedure (NSpid, cgroup, exe, pidfd/starttime, multi-candidate, pre-exit, ptrace-access permissions) replaces the `waitpid`-as-identity claim.
8. R64-08: single CAT_STOP_RUN contract; 42 normative + Unverified-until-recorded; gate and consistency rule unified; `_exit(10)` distinction fixed.
9. No historical byte changed; P0 unchanged; no empirical claim introduced.

`NOT EXECUTED — no code written or modified, no dependencies installed, no containers built, no compilation performed, no arithmetic, FFI, parser, IPC, state or sandbox experiments run, and no deployment performed.`
