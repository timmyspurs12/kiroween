# NecroSpec Rev 6.1 — Final Four-Point Errata (E-8 … E-11)

Four errata only. Everything else in Rev 5/Rev 6 stands per §0. No new scope, no redesign, no executed claims.

---

## Deliverable 1 — Corrected Sections

### E-8 → SUPERSEDES Rev 6 E-3 §3.3a (fixture #20 source v3 → v3.1). Wire layout unchanged.

**Defect (audit of complete v3 source):** the diagnostic header is `__attribute__((packed))` with every multi-byte member at an **odd** byte offset (`rc[]` +13, `err[]` +29, `open_err[]` +45, `read_err[]` +61, `aux_u32` +77, all five `*_len` +81…+89). v3 passed **24 pointers to packed members** into `read_proc_slice`/`probe_open` (4 `uint16_t*` lengths, 8 `int32_t*` errno arrays across 4 `read_proc_slice` calls; 12 `int32_t*` across 6 `probe_open` calls). Under GCC 14, `-Wall` enables `-Waddress-of-packed-member`; with §2.1.5's `-Werror` all 24 are compile failures, and the accesses are UB by C alignment rules regardless of target.

**Rule (normative):** no pointer derived from a packed-structure member is ever passed to a function whose parameter type has alignment > 1. All multi-byte values flow through **aligned locals** into the functions, then are **copied by assignment** into the packed structure (assignment through a packed lvalue is well-defined under GCC `packed` semantics; only address-taking is defective). Pointers to `uint8_t` flag members are permitted (alignment 1). The 128-byte wire layout, field order, schema byte (3), and all §5.1a consumer checks are **unchanged**. This erratum does not verify compilation (forbidden); §2.1.5 governs at execution.

```c
/* === #20: EVILMOD.c v3.1 (L2-loaded C probe module; Rev 6.1 errata E-8) ===
   Wire layout IDENTICAL to v3 (schema 3, 128-byte header). Internal change:
   all multi-byte values pass through aligned locals; no pointer into the
   packed header with alignment > 1 is ever taken. */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/sched.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

extern char **environ;

/* Regions: 128 + 4096 + 512 + 512 + 2048 + 9088 = 16384 */
enum {
    DIAG_BUF_TOTAL = 16384,
    OFF_STATUS = 128,    CAP_STATUS    = 4096,
    OFF_UID_MAP = 4224,  CAP_UID_MAP   = 512,
    OFF_GID_MAP = 4736,  CAP_GID_MAP   = 512,
    OFF_ENV     = 5248,  CAP_ENV_NAMES = 2048,
    OFF_MNTINFO = 7296,  CAP_MNTINFO   = 9088
};

struct __attribute__((packed)) evil_diag_hdr {   /* offsets audited below: 128 B */
    uint32_t magic;           /* +0    */
    uint8_t  mode, submode;   /* +4,+5 */
    uint16_t hdr_bytes;       /* +6    */
    uint8_t  schema;          /* +8    */
    uint8_t  eof_flags;       /* +9    */
    uint8_t  trunc_flags;     /* +10   */
    uint8_t  open_fail_flags; /* +11   */
    uint8_t  reserved0;       /* +12   */
    int32_t  rc[4];           /* +13   */
    int32_t  err[4];          /* +29   */
    int32_t  open_err[4];     /* +45   */
    int32_t  read_err[4];     /* +61   */
    uint32_t aux_u32;         /* +77   */
    uint16_t status_len;      /* +81   */
    uint16_t uid_map_len;     /* +83   */
    uint16_t gid_map_len;     /* +85   */
    uint16_t env_names_len;   /* +87   */
    uint16_t mountinfo_len;   /* +89   */
    uint8_t  reserved1[37];   /* +91..127 */
};
_Static_assert(sizeof(struct evil_diag_hdr) == 128, "diag header must be 128");

/* All pointer parameters are aligned caller locals, or uint8_t (alignment 1). */
static void read_proc_slice(const char *path, uint8_t *dst, size_t cap,
                            uint16_t *out_len, uint8_t *eof, uint8_t *trunc,
                            uint8_t *openfail, int32_t *oerr, int32_t *rerr,
                            uint8_t bit) {
    *out_len = 0; *rerr = 0;
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) { *openfail |= (uint8_t)(1U << bit); *oerr = errno; return; }
    size_t got = 0; int full = 0;
    for (;;) {
        if (got == cap) { full = 1; break; }
        ssize_t r = read(fd, dst + got, cap - got);
        if (r < 0) { if (errno == EINTR) continue; *rerr = errno; break; }
        if (r == 0) { *eof |= (uint8_t)(1U << bit); break; }
        got += (size_t)r;
    }
    if (full) {   /* exact-fit disambiguation (unchanged from v3) */
        char probe; ssize_t r;
        do { r = read(fd, &probe, 1); } while (r < 0 && errno == EINTR);
        if (r == 0)     *eof   |= (uint8_t)(1U << bit);
        else if (r > 0) *trunc |= (uint8_t)(1U << bit);
        else            *rerr  = errno;
    }
    close(fd);
    *out_len = (uint16_t)got;
}

static void probe_open(const char *path, int flags, mode_t mode,
                       int32_t *rc, int32_t *err, int unlink_on_ok) {
    errno = 0;
    int fd = open(path, flags, mode);
    if (fd >= 0) { *rc = 0; *err = 0; close(fd); if (unlink_on_ok) unlink(path); }
    else         { *rc = -1; *err = errno; }
}

int necro_plugin_entry(uint8_t **bufs, const uint32_t *lens, uint16_t argc) {
    if (argc < 1 || lens[0] < DIAG_BUF_TOTAL) return -1;
    uint8_t *b = bufs[0];
    uint8_t mode = b[0], sub = b[1];
    memset(b, 0, DIAG_BUF_TOTAL);
    struct evil_diag_hdr *h = (struct evil_diag_hdr *)b;
    h->magic = 0x4556494CU; h->mode = mode; h->submode = sub;
    h->hdr_bytes = (uint16_t)sizeof(*h); h->schema = 3;
    h->rc[0] = h->rc[1] = h->rc[2] = h->rc[3] = -2;

    if (mode == 'K') {
        struct sigaction sa; memset(&sa, 0, sizeof sa);
        sa.sa_handler = SIG_DFL; sigaction(SIGSEGV, &sa, NULL);
        *(volatile int *)0 = 1;
    } else if (mode == 'C') {
        int s = (int)syscall(SYS_socket, AF_INET, SOCK_STREAM | SOCK_NONBLOCK, 0);
        h->rc[0] = (s >= 0) ? 0 : -1; h->err[0] = (s >= 0) ? 0 : errno;
        if (s >= 0) {
            struct sockaddr_in sa; memset(&sa, 0, sizeof sa);
            sa.sin_family = AF_INET; sa.sin_port = htons(53);
            if (inet_pton(AF_INET, "1.1.1.1", &sa.sin_addr) != 1) { close(s); return -1; }
            errno = 0;
            int c = connect(s, (struct sockaddr *)&sa, sizeof sa);
            h->rc[1] = (c == 0) ? 0 : -1; h->err[1] = (c == 0) ? 0 : errno;
            close(s);
        }
    } else if (mode == 'I') {
        uint16_t len; int32_t oerr, rerr;               /* aligned locals */
        read_proc_slice("/proc/self/status", b + OFF_STATUS, CAP_STATUS,
                        &len, &h->eof_flags, &h->trunc_flags, &h->open_fail_flags,
                        &oerr, &rerr, 0);
        h->status_len = len; h->open_err[0] = oerr; h->read_err[0] = rerr;
        read_proc_slice("/proc/self/uid_map", b + OFF_UID_MAP, CAP_UID_MAP,
                        &len, &h->eof_flags, &h->trunc_flags, &h->open_fail_flags,
                        &oerr, &rerr, 1);
        h->uid_map_len = len; h->open_err[1] = oerr; h->read_err[1] = rerr;
        read_proc_slice("/proc/self/gid_map", b + OFF_GID_MAP, CAP_GID_MAP,
                        &len, &h->eof_flags, &h->trunc_flags, &h->open_fail_flags,
                        &oerr, &rerr, 2);
        h->gid_map_len = len; h->open_err[2] = oerr; h->read_err[2] = rerr;
        struct stat st; memset(&st, 0, sizeof st);
        errno = 0;
        int sret = stat("/stage/root_only_secret.txt", &st);
        h->rc[0] = (sret == 0) ? 0 : -1;
        h->err[0] = (sret == 0) ? 0 : errno;
        h->aux_u32 = (uint32_t)st.st_mode;
        int32_t prc, perr;                               /* aligned locals */
        probe_open("/stage/root_only_secret.txt", O_RDONLY, 0, &prc, &perr, 0);
        h->rc[1] = prc; h->err[1] = perr;
    } else if (mode == 'D') {
        int32_t prc, perr;
        probe_open("/tmp/host_gateway_secret.txt", O_RDONLY, 0, &prc, &perr, 0);
        h->rc[0] = prc; h->err[0] = perr;
        uint32_t cnt = 0; size_t pos = 0; int fit = 1;
        for (char **e = environ; e && *e; ++e) {
            cnt++;
            size_t nlen = strcspn(*e, "=");
            if (pos + nlen + 1 <= CAP_ENV_NAMES) {
                memcpy(b + OFF_ENV + pos, *e, nlen);
                b[OFF_ENV + pos + nlen] = '\n';
                pos += nlen + 1;
            } else fit = 0;
        }
        h->aux_u32 = cnt;
        h->env_names_len = (uint16_t)pos;
        if (!fit) h->trunc_flags |= (1U << 3);
    } else if (mode == 'E') {
        char ok[256];
        const char *td = getenv("TMPDIR");
        int n = snprintf(ok, sizeof ok, "%s/ok", (td && *td) ? td : "/missing");
        if (n < 0 || (size_t)n >= sizeof ok) return -1;  /* -Wall format-truncation compliance */
        int32_t prc, perr;
        probe_open("/ro_probe/x", O_CREAT | O_WRONLY, 0600, &prc, &perr, 1);
        h->rc[0] = prc; h->err[0] = perr;
        probe_open("/usr/x",      O_CREAT | O_WRONLY, 0600, &prc, &perr, 1);
        h->rc[1] = prc; h->err[1] = perr;
        probe_open("/stage/x",    O_CREAT | O_WRONLY, 0600, &prc, &perr, 1);
        h->rc[2] = prc; h->err[2] = perr;
        probe_open(ok,            O_CREAT | O_WRONLY | O_TRUNC, 0600, &prc, &perr, 1);
        h->rc[3] = prc; h->err[3] = perr;
        uint16_t mlen; int32_t oerr, rerr;
        read_proc_slice("/proc/self/mountinfo", b + OFF_MNTINFO, CAP_MNTINFO,
                        &mlen, &h->eof_flags, &h->trunc_flags, &h->open_fail_flags,
                        &oerr, &rerr, 4);
        h->mountinfo_len = mlen; h->open_err[3] = oerr; h->read_err[3] = rerr;
    } else if (mode == 'F') {
        long r = -1;
        char *const av[] = { (char *)"/bin/sh", NULL };
        struct clone_args ca; memset(&ca, 0, sizeof ca);
        errno = 0;
        int sh = faccessat(AT_FDCWD, "/bin/sh", X_OK, 0);
        h->rc[1] = (sh == 0) ? 0 : -1; h->err[1] = (sh == 0) ? 0 : errno;
        errno = 0;
        switch (sub) {
            case 1: r = syscall(SYS_fork);  if (r == 0) _exit(0); break;
            case 2: r = syscall(SYS_vfork); if (r == 0) _exit(0); break;
            case 3: r = syscall(SYS_clone, (unsigned long)SIGCHLD, 0UL, NULL, NULL, 0UL);
                    if (r == 0) _exit(0); break;
            case 4: ca.exit_signal = SIGCHLD;
                    r = syscall(SYS_clone3, &ca, sizeof ca);
                    if (r == 0) _exit(0); break;
            case 5: r = syscall(SYS_execve, "/bin/sh", av, environ); break;
            case 6: r = syscall(SYS_execveat, AT_FDCWD, "/bin/sh", av, environ, 0); break;
            case 7: r = syscall(SYS_ptrace, 0, 0, NULL, NULL); break;
            case 8: r = syscall(SYS_unshare, CLONE_NEWUSER); break;
            case 9: r = syscall(SYS_socket | 0x40000000UL,
                                AF_INET, SOCK_STREAM | SOCK_NONBLOCK, 0);
                    if (r >= 0) close((int)r);
                    break;
        }
        h->rc[0] = (r >= 0) ? 0 : -1;
        h->err[0] = (r >= 0) ? 0 : errno;
    } else if (mode == 'L') {
        sigset_t s; sigfillset(&s); sigprocmask(SIG_BLOCK, &s, NULL);
        if (sub == 1)
            for (int i = 0; i < 4; i++)
                if (fork() == 0) { for (;;) { volatile int x = 0; (void)x; } }
        for (;;) { volatile int x = 0; (void)x; }
    }
    return 0;
}
```
Field-by-field access audit (every field checked, not only flagged examples): direct packed-lvalue **assignment** only (well-defined, no pointer taken): `magic`, `mode`, `submode`, `hdr_bytes`, `schema`, `aux_u32`, `env_names_len`, all `rc[]`/`err[]` slots not routed through helpers, flag bytes. Written via **aligned locals then copied**: `status_len`, `uid_map_len`, `gid_map_len`, `mountinfo_len` (via `uint16_t len/mlen`), `open_err[0..3]`, `read_err[0..3]` (via `int32_t oerr/rerr`), and the 6 helper-routed `rc/err` slots (via `int32_t prc/perr`). `uint8_t*` flag pointers into the packed header are alignment-1 and permitted. One additional `-Wall` compliance adjustment within scope: the `snprintf` return value is now checked (`-Wformat-truncation`). No other behavioral change.

### E-9 → V6 ownership (amends Rev 5 §7.1/§3.5/§7.3; reaffirms Rev 6 E-6)

**Definition (normative):** a vector's **owner** is the sole experiment whose PASS criteria assert that vector's expected output bytes. Other experiments may use a vector as differential-corpus input without owning it.

- **(a) Rev 5 §7.1 "Expected" paragraph (inherited, unamended until now — defect):** replacement text: "**Expected:** V1/V2/V7 outputs match their [D] values byte-for-byte; V3/V4 recorded with H1 disposition; V5 recorded with H3/H4 dispositions; determinism across ≥ 3 runs; every output byte explained from generated C/runtime source; zero `cobc` warnings. **V6 is not an Exp-1 expectation; V6 is owned exclusively by Exp-2 test 2A** (E-6 §7.1a)."
- **(b) Rev 5 §3.5 row #6 replacement:** `| #6 T2MULTI | — | 2A (V6), 2B–2C (PID recycle) | 3E corpus input (no independent V6 expectation) | — |` (Exp-1 column is now empty).
- **(c) Rev 5 §7.3 Exp-3 inputs annotation:** "vectors V1–V7 serve as 3E differential-corpus input; **V6 carries no independent Exp-3 expected result**."
- **(d) Rev 6 E-6 §7.1a and E-6 §7.2a reaffirmed unchanged** (V6 → Exp-2/2A, expected `00 03 00 0C` [D]).

### E-10 → SUPERSEDES Rev 6 E-4 §2.5v2 table (vector PICTURE audit; full table = Deliverable 3 below)

All input fields now carry their exact COBOL PICTURE from the Rev 4 §3.1 fixture sources. **Two input-byte corrections fall out of the audit**: the V5 pre-state sentinels for the **unsigned** fields `LK-UNSG-TR`/`LK-UNSG-SE` (`PIC 9(3)V99 COMP-3`) are corrected from `12 34 5C` to **`12 34 5F`** — an unsigned COMP-3 field's sign-position nibble is `F` (H4); writing `C` would seed the fields with the malformed form H4 says they never take. `LK-SIGN-TR` (`PIC S9(3)V99`) keeps `12 34 5C`. Downstream candidates update accordingly (P1: `09 00 0F`; P2: unchanged `12 34 5F`, FLAG `31`; P3: `09 00 0D`). All other V1–V7 bytes re-derive unchanged. **Completeness statement:** every input field of every vector has an available fixture definition; **no vector is marked incomplete**, and no PICTURE was inferred from a byte sequence.

### E-11 → SUPERSEDES Rev 6 E-0 §0.4 (dependency hash anchoring becomes a blocking precondition)

> **§0.4v2 — Mandatory Env-0 precondition P0: dependency acquisition, extraction, verification, and hash anchoring.**
> **P0 blocks Env-0 build/installation steps and therefore all experiments.** Steps, in order:
> 1. Obtain the exact Rev 4 and Rev 5 source documents, plus Rev 6 (E-0…E-7) and Rev 6.1 (E-8…E-11), as verbatim byte streams (session transcript, 2026-11-04).
> 2. Verify presence of every required section: Rev 4 §2.2.2 (grammar) and §3.1–§3.3 (fixtures #1–#19); Rev 5 §1–§13; Rev 6 E-0…E-7; Rev 6.1 E-8…E-11. Any absence → P0 FAIL.
> 3. Extract dependency material byte-for-byte (no normalization, no reflow, no re-typing) into `spike_evidence/spec/`: `rev4_extract.md` (Rev 4 §2.2.2, §3.1–§3.3), `rev5.md`, `rev6_errata.md`, `rev61_errata.md`.
> 4. Compute and record SHA-256 over each original document stream and each extracted file → `SHA256SUMS`.
> 5. Record in `env0/spec_manifest.json`: document identity, version label, capture date, extraction method ("verbatim transcript copy, byte-for-byte"), per-file SHA-256, and the step-2 section-presence checklist results.
> 6. If any dependency cannot be obtained, any required section is missing, or any hash cannot be computed: **STOP**. No compilation, no container build, no experimentation; Env-0 is recorded `ABORTED-P0` until remediated and P0 re-run green.
> 7. **No hash value exists today and none may be fabricated.** Until P0 step 4 executes, the corpus is *transcript-anchored only*; every digest cited anywhere in the spike must come from `SHA256SUMS`.

---

## Deliverable 2 — Correction Matrix

| # | Issue | Resolution | Remaining limitation |
|---|---|---|---|
| 1 | Packed-struct pointers passed to aligned-expecting functions; would fail `-Wall -Wextra -Werror` (`-Waddress-of-packed-member`) | E-8: source v3.1; all 24 offending pointer arguments eliminated via aligned locals + assignment copies; every field audited; one `-Wformat-truncation` compliance fix (`snprintf` return checked); wire layout, offsets, schema, and consumer checks unchanged | Source not compiled here (forbidden); `-Werror` compliance is verified at execution under §2.1.5 |
| 2 | V6 still referenced under Exp-1 (Rev 5 §7.1 Expected inherited; §3.5 #6 Exp-1 column) | E-9(a)(b): both statements replaced; V6 expectation exists only in Exp-2/2A; Exp-3 usage reclassified as corpus input | None at specification level |
| 3 | Vector table lacked exact input PICTUREs; fractional-only PICs under-specified; V5 sentinels used a signed nibble in unsigned fields | E-10 / Deliverable 3: full 9-attribute table from fixture definitions; SV999/SV99 explicitly derived (I=0); V5 unsigned sentinels corrected to `12 34 5F`; no vector incomplete | [D]/[Hn] values remain unverified until Exp-1/Exp-2 record them |
| 4 | Dependency hashes not yet verified; no blocking condition | E-11: P0 six-step mandatory precondition with STOP semantics; hashes to be computed, never asserted | Corpus remains transcript-anchored until P0 executes; no digest citable today |

---

## Deliverable 3 — Document-Wide V6 / Vector-to-Experiment Cross-Reference

**Owner map (owner = sole experiment asserting the vector's expected bytes):**

| Vector | Owner | Owner's assertion | Secondary use |
|---|---|---|---|
| V1 | Exp-1 | `01 54 32 0C` [D] | 3E corpus |
| V2 | Exp-1 | `00 67 9C` [D] | 3E corpus |
| V3 | Exp-1 | `06 66 66 6C` [H1] | 3E corpus |
| V4 | Exp-1 | `06 66 66 6C` [H1] | 3E corpus |
| V5 | Exp-1 | SIGN-TR `09 00 0D` [D]; rest [H3∧H4] | 3E corpus |
| **V6** | **Exp-2 / test 2A — exclusively** | `00 03 00 0C` [D] | 3E corpus input (no independent expectation) |
| V7 | Exp-1 | TRAIL `30 36 31 37 33 2D`; UNSG `30 31 32 33 34 35` [D] | 3E corpus |

**Every V6 occurrence, audited:** Rev 5 §2.5 table row — superseded by E-4/E-10 (definition only; Owner cell = Exp-2/2A). Rev 5 §2.5.2 error register — definition-level, no Exp-1 attribution. Rev 5 §3.5 #6 Exp-1 column — **removed by E-9(b)**. Rev 5 §7.1 Expected ("V1/V2/V6/V7") — **removed by E-9(a)**. Rev 5 §7.1 Inputs — already V6-free via E-6 §7.1a. Rev 5 §7.2 (2A "byte-parity (V6)") — correct, Exp-2, retained. Rev 5 §7.3 inputs "V1–V7" — **annotated by E-9(c)**. Rev 6 E-6 §7.1a/§7.2a — V6→Exp-2/2A, reaffirmed. Rev 6 Deliverables 3–4 — already Exp-2/2A, consistent. **Result: zero residual V6 references under Exp-1; exactly one owner per vector, V1–V7.**

---

## Deliverable 4 — EVILMOD v3.1 Field-Offset / 128-Byte Consistency Confirmation

| Field | Offset | Size | Access method |
|---|---|---|---|
| `magic` | 0–3 | 4 | direct assignment |
| `mode`, `submode` | 4, 5 | 1, 1 | direct |
| `hdr_bytes` | 6–7 | 2 | direct assignment |
| `schema` | 8 | 1 | direct |
| `eof_flags`, `trunc_flags`, `open_fail_flags` | 9, 10, 11 | 1, 1, 1 | direct via `uint8_t*` (alignment 1) |
| `reserved0` | 12 | 1 | memset zero |
| `rc[0..3]` | 13, 17, 21, 25 | 4×4 | assignments; helper slots via aligned `prc/perr` |
| `err[0..3]` | 29, 33, 37, 41 | 4×4 | same |
| `open_err[0..3]` | 45, 49, 53, 57 | 4×4 | aligned `oerr` → copy |
| `read_err[0..3]` | 61, 65, 69, 73 | 4×4 | aligned `rerr` → copy |
| `aux_u32` | 77–80 | 4 | direct assignment |
| `status_len` | 81–82 | 2 | aligned `len` → copy |
| `uid_map_len` | 83–84 | 2 | aligned `len` → copy |
| `gid_map_len` | 85–86 | 2 | aligned `len` → copy |
| `env_names_len` | 87–88 | 2 | direct assignment from `uint16_t pos` |
| `mountinfo_len` | 89–90 | 2 | aligned `mlen` → copy |
| `reserved1[37]` | 91–127 | 37 | memset zero |

Arithmetic: last field ends at 90; 91 + 37 = **128 exactly**; `_Static_assert(sizeof == 128)` pins it at compile time. Field sum: 4+2+2+1+3+1+16+16+16+16+4+2+2+2+2+2+37 = 128 ✓. Buffer regions 128+4096+512+512+2048+9088 = 16384 ✓. All 16 multi-byte members sit at offsets ≥ 6 with the arrays/lens at odd offsets — confirming why the E-8 access rule was required. Wire layout is byte-identical to v3; §5.1a consumer validation checks carry over unchanged.

---

## Deliverable 5 — Remaining Limitations

1. All gates remain `NOT EXECUTED`; no artifacts exist.
2. EVILMOD v3.1 (and all bespoke C) is **not compiled** here by prohibition; `-Werror` cleanliness is an execution-time finding under §2.1.5.
3. Corpus is transcript-anchored only until P0 produces `SHA256SUMS`; no hash may be cited before then (E-11.7).
4. Environment assumptions A1–A3 and open items Q1–Q9, H1–H8 stand unchanged (including every [Hn] vector field, T2BADBCD's category, and the kernel x32 regime).
5. [D] vector values are derived from COBOL standard semantics, not executed; a [D] mismatch at Exp-1 is a finding, not a spec failure.

---

## Deliverable 6 — Final Specification-Readiness Verdict

All four findings are closed at specification level: the packed-structure access rule is now source-complete and offset-verified with an unchanged wire layout; V6 ownership is unique and document-wide consistent; the vector audit is derived from actual fixture PICTUREs with two sentinel bytes corrected and no vector incomplete; dependency anchoring is a mandatory, hash-verified, fail-stop Env-0 precondition with no fabricated digests. No unrelated sections were altered.

**`READY FOR LIMITED PHASE-0 EXECUTION`**

This verdict concerns specification completeness only. It is not evidence that any experiment ran or passed; all gates remain `NOT EXECUTED` until artifacts exist and are independently reviewed.

`NOT EXECUTED — zero code written, zero files created, zero containers built, zero experiments run, zero results claimed.`
