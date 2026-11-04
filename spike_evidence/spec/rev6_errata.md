# NecroSpec Rev 6 — Targeted Final Errata

## Deliverable 1 — Rev 6 Errata (corrected sections, exact numbers, replacement text)

Each erratum below **supersedes** the cited Rev 5 section. All other Rev 5 content remains normative per §0.

---

### E-0 → NEW Rev 5 §0 (resolves Finding 5 — self-containment, Option B)

> **§0 Document Identity and Dependency**
> 1. The normative corpus is the ordered union of: **Rev 4** §2.2.2 (Lark grammar) and §3.1–§3.3 (fixture sources #1–#19); **Rev 5** in full (sections §1–§13); and this **Rev 6 errata** (E-0…E-7). Where an erratum supersedes a Rev 5 section, the erratum text alone is normative.
> 2. **Rev 6 is not independently self-contained.** Fixture sources #1–#19 and the grammar exist only in Rev 4 (as incorporated by Rev 5 §2.2, §3.1–§3.2); all unamended procedures, bounds, and policy text exist only in Rev 5. Rev 5 is likewise not self-contained without Rev 4.
> 3. Document identity: "Rev 5" denotes the specification message titled *"NecroSpec — Phase-0 Technical Spike Execution Specification (Rev 5)"* emitted in this session on 2026-11-04; "Rev 4" likewise the message of the same session. **No SHA-256 digest can be cited today** because no file exists in the workspace (the repository is intentionally untouched); the corpus is currently *transcript-anchored*, not hash-anchored. This is a stated limitation.
> 4. Hash anchoring procedure (mandatory first Env-0 step, before image builds): assemble the corpus into `spike_evidence/spec/` as `rev4_extract.md` (Rev 4 §2.2.2, §3.1–§3.3, verbatim), `rev5.md`, `rev6_errata.md`; record `SHA256SUMS` over the three files plus this errata's vector table; reference the digest from every subsequent evidence artifact. From that moment the corpus is `HASH-ANCHORED`; before it, any transcription dispute is resolved against the session transcript, not against memory.

---

### E-1 → SUPERSEDES Rev 5 §4.3 (rows `/bin`, `/usr`), §4.4 (profile), §5.3 (rows 4F-5/4F-6) (resolves Finding 1)

> **§4.3a Sandbox executable layout (replacement rows)**
>
> | Sandbox path | Source / mechanism | Mode | Purpose / verification |
> |---|---|---|---|
> | `/bin` | **`--symlink usr/bin /bin`** operand — creates a symlink at sandbox-root `/bin` with target `usr/bin`, resolving *inside* the sandbox to the ro-bound `/usr/bin` (bubblewrap.c:347, `--symlink SRC DEST`) | symlink | Rev 5's profile mounted no host `/bin`; merged-usr host symlinks are irrelevant to the sandbox root. `/bin/sh` is reachable **only** because of this operand. |
> | `/usr/bin/sh` | Debian `dash` package (Essential) in the runtime image, visible via the existing `--ro-bind /usr /usr` | `0755` | Mode F exec target. |
> | loader + libc for `sh` | `libc6` (`ld-linux-x86-64.so.2`, `libc.so.6`) under the existing `--ro-bind /lib /lib`, `--ro-bind /lib64 /lib64` | — | dash's runtime dependencies; versions from `env0/dpkg_manifest.txt`. |
>
> **§4.3b Host-side positive control (per run, recorded in `staging_manifest.json`):** before launch the supervisor (host) records: `[ -x /usr/bin/sh ]` result; `readlink -f /bin/sh` output; `dpkg-query -W -f '${Version}' dash` output. If the executable is absent in the source tree, the run is aborted before launch — it is never "discovered" in-band.
>
> **§4.3c In-sandbox verification:** the worker records `exec_sh_ok = (faccessat(AT_FDCWD, "/bin/sh", X_OK, 0) == 0)` in `INIT_ACK` (already in Rev 5 §2.3.2 — unchanged); EVILMOD Mode F independently records the same probe into `rc[1]/err[1]` before any exec attempt.
>
> **§4.4 (replacement profile — one line added, position after the `/lib64` bind):**
> ```bash
> bwrap --unshare-all --unshare-user --disable-userns --new-session --die-with-parent \
>       --cap-drop ALL --uid 10001 --gid 10001 \
>       --ro-bind /usr /usr --ro-bind /lib /lib --ro-bind /lib64 /lib64 \
>       --symlink usr/bin /bin \
>       --ro-bind /opt/necro /opt/necro \
>       --ro-bind /var/lib/necro-stage/$UUID /stage \
>       --proc /proc --dev /dev \
>       --perms 0777 --dir /ro_probe \
>       --perms 1777 --size 33554432 --tmpfs /work \
>       --perms 0755 --tmpfs /tmp \
>       --chdir /work \
>       --remount-ro / -- \
>       /opt/necro/<worker> --worker-seccomp=<off|on>
> ```
>
> **§5.3a (replacement rows 4F-5/4F-6 + new negative control):**
>
> | Probe | Flag | Input | Expected observation |
> |---|---|---|---|
> | **4F-5 / 4F-6** | off | ('F',5/6), `exec_sh_ok=1` | process replaced by `/bin/sh`; FDs 3/4 were `FD_CLOEXEC` (Rev 5 §2.3.1); stdin = `/dev/null` → dash reads EOF, exits 0 → **no CALL_ACK header, bwrap exit 0** (a nonzero dash exit is recorded, observational) |
> | **4F-5 / 4F-6** | on | ('F',5/6) | SIGSYS at the `execve`/`execveat` call → **headerless death, bwrap exit 159** |
> | **4F-5-NEG** (new) | off | ('F',5) under the **identical profile minus the `--symlink usr/bin /bin` operand** | `INIT_ACK.exec_sh_ok=0` (faccessat → ENOENT); CALL_ACK header `rc[1]=-1, err[1]=2`, `rc[0]=-1, err[0]=2`; worker survives and tears down normally |
>
> **ENOENT-vs-seccomp decision rule:** a missing executable produces an **in-band header carrying `errno=ENOENT(2)` with a live worker** (proven signature by 4F-5-NEG); a seccomp denial produces **no header and process death with exit 159**. The two outcomes are never confusable. A seccomp-on run in which `exec_sh_ok=0` is a **profile-manifest failure before the probe is credited**, not a seccomp result.

---

### E-2 → SUPERSEDES Rev 5 §6 (architecture/x32 paragraph and rule-set notes) (resolves Finding 2)

> **§6.1 Architecture assumptions (exact):** x86_64 userspace on an x86_64 kernel. The kernel presents `seccomp_data.arch == AUDIT_ARCH_X86_64` for **both** native and x32-ABI invocations; an x32 invocation is distinguishable **only** by bit 30 of the syscall number (`X32_SYSCALL_BIT = 0x40000000`, libseccomp `arch-x32.h:27`; kernel equivalence documented at `arch-x32.c:77`, `.token_bpf = AUDIT_ARCH_X86_64`, "the kernel treats x32 like x86_64 here").
>
> **§6.2 Exact syscall-number check (generated BPF, libseccomp `main@2814474`, `gen_bpf.c:1735–1749`):** for a filter containing **only** `SCMP_ARCH_X86_64` (no X32 secondary), libseccomp emits immediately before the syscall-number rules:
> `if (nr >= 0x40000000) goto BADARCH;` — implemented as `BPF_JMP+BPF_JGE, K=0x40000000`, false-branch → rule chain, true-branch → fallthrough to `if (nr != (uint32_t)-1) goto BADARCH;` (the `-1` exception is libseccomp's tracer-skip accommodation per its comment and seccomp(2)). Because `ACT_BADARCH` is set to `SCMP_ACT_KILL_PROCESS`, **every x32-numbered syscall is killed**, independent of the deny list and independent of the allow default. The earlier Rev 5 mechanism was correct but undocumented and untested; that insufficiency is what this erratum repairs.
>
> **§6.3 Negative constraint (source-motivated):** `seccomp_arch_add(ctx, SCMP_ARCH_X32)` is **forbidden** in this policy. When an X32 filter is present, libseccomp merges both chains as primary/secondary (`gen_bpf.c:2065–2085`) and **skips the `JGE 0x40000000` gate** (`gen_bpf.c:1733`, condition `db_secondary == NULL`); under an allow-default, x32 syscalls absent from the deny list would then fall through to ALLOW. The x86_64-only configuration is both stricter and source-verified.
>
> **§6.4 Default actions:** unchanged from Rev 5 (`ACT_DEFAULT = SCMP_ACT_ALLOW` for both stages — default-deny cannot be justified before the Exp-4A census; `ACT_BADARCH = SCMP_ACT_KILL_PROCESS`, API level ≥ 3). Stage-1/Stage-2 deny lists unchanged, **plus one addition**: `modify_ldt` is added to the Stage-1 process/ABI group (x86-specific legacy ABI hardening; not needed by libcob/libgmp/dash).
>
> **§6.5 Empirical gate 4F-9 (new; claim arbiter):** EVILMOD Mode F `sub=9` issues the raw x32 probe `syscall(SYS_socket | 0x40000000UL, AF_INET, SOCK_STREAM | SOCK_NONBLOCK, 0)` (closing the fd on success).
> - **Off-control first:** records the kernel x32 regime — `rc[0]=0` (`CONFIG_X86_X32_ABI=y`, vector live) or `rc[0]=-1, err=38 (ENOSYS)` (x32 disabled). Both regimes are valid; the regime is recorded (**H8**).
> - **On-mode:** in either regime, the filter's number-gate fires at syscall entry, **before** any dispatch: expected outcome is headerless death, bwrap exit **159**. Because off-mode returns a graceful in-band ENOSYS while on-mode kills, the test distinguishes filter action from kernel rejection even in the x32-disabled regime.
> - **Claim rule:** "x32 protection" may be claimed **only** if 4F-9 on-mode shows the SIGSYS/159 signature; a header with `rc[0]=0` under seccomp=on is an x32 bypass → **Exp-4 FAIL**, hard gate.
> - **Static evidence:** the worker optionally calls `seccomp_export_bpf_mem` after each `seccomp_load` and writes the raw BPF to `exp4/seccomp_stage{1,2}.bpf` (SHA-256 recorded), allowing independent inspection of the `JGE 0x40000000 → badarch` instruction sequence.
>
> **§6.6 Contingency C-1:** if, at implementation time, `seccomp_export_bpf_mem` output or 4F-9 shows the gate is absent (e.g. unexpected library behavior), Stage-1/Stage-2 must be rebuilt with default action `SCMP_ACT_ERRNO(ENOSYS)` plus an explicit allow list derived from the Exp-4A census **before** any seccomp-on result is credited. Fail-visible; no silent hole.

---

### E-3 → SUPERSEDES Rev 5 §3.3 (fixture #20), §5.1 (schema), §5.3 (rows 4D-0/2, 4D-1, 4E-0 flag names) (resolves Finding 3)

> **§3.3a Fixture #20 `EVILMOD.c` v3 (full replacement source; supersedes v2).** Compiles under `-O2 -Wall -Wextra -Werror`; `sizeof` pinned at compile time.
>
> ```c
> /* === #20: EVILMOD.c v3 (L2-loaded C probe module; Rev 6 errata E-3) === */
> #define _GNU_SOURCE
> #include <arpa/inet.h>
> #include <errno.h>
> #include <fcntl.h>
> #include <linux/sched.h>
> #include <sched.h>
> #include <signal.h>
> #include <stdint.h>
> #include <stdio.h>
> #include <stdlib.h>
> #include <string.h>
> #include <sys/stat.h>
> #include <sys/syscall.h>
> #include <unistd.h>
>
> extern char **environ;
>
> /* Regions: 128 + 4096 + 512 + 512 + 2048 + 9088 = 16384 */
> enum {
>     DIAG_BUF_TOTAL = 16384,
>     OFF_STATUS = 128,    CAP_STATUS    = 4096,
>     OFF_UID_MAP = 4224,  CAP_UID_MAP   = 512,
>     OFF_GID_MAP = 4736,  CAP_GID_MAP   = 512,
>     OFF_ENV     = 5248,  CAP_ENV_NAMES = 2048,
>     OFF_MNTINFO = 7296,  CAP_MNTINFO   = 9088
> };
>
> struct __attribute__((packed)) evil_diag_hdr {   /* v3: 128 bytes (v2 summed to 127; reserved1 is 37, not 36) */
>     uint32_t magic;          /* 0x4556494C "EVIL"                     +0    */
>     uint8_t  mode, submode;  /* request echo                          +4    */
>     uint16_t hdr_bytes;      /* 128                                   +6    */
>     uint8_t  schema;         /* 3                                     +8    */
>     uint8_t  eof_flags;      /* bit0..4: kernel EOF (read()==0) seen  +9    */
>     uint8_t  trunc_flags;    /* bit0..4: capacity full WITHOUT EOF    +10   */
>     uint8_t  open_fail_flags;/* bit0..3: status,uid,gid,mountinfo     +11   */
>     uint8_t  reserved0;      /* 0                                     +12   */
>     int32_t  rc[4];          /* per-mode probes; -2 = unused slot     +13..28 */
>     int32_t  err[4];         /* probe errnos (0 if rc>=0)             +29..44 */
>     int32_t  open_err[4];    /* open() errno per proc slice           +45..60 */
>     int32_t  read_err[4];    /* read() errno per proc slice           +61..76 */
>     uint32_t aux_u32;        /* 'I': st_mode; 'D': env var count      +77..80 */
>     uint16_t status_len;     /* stored bytes                          +81    */
>     uint16_t uid_map_len;    /*                                       +83    */
>     uint16_t gid_map_len;    /* dedicated field                       +85    */
>     uint16_t env_names_len;  /*                                       +87    */
>     uint16_t mountinfo_len;  /*                                       +89    */
>     uint8_t  reserved1[37];  /* 0x00 * 37                             +91..127 */
> };
> _Static_assert(sizeof(struct evil_diag_hdr) == 128, "diag header must be 128");
>
> static void read_proc_slice(const char *path, uint8_t *dst, size_t cap,
>                             uint16_t *out_len, uint8_t *eof, uint8_t *trunc,
>                             uint8_t *openfail, int32_t *oerr, int32_t *rerr,
>                             uint8_t bit) {
>     *out_len = 0; *rerr = 0;
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
>     if (full) {   /* exact-fit is ambiguous: one extra read disambiguates */
>         char probe; ssize_t r;
>         do { r = read(fd, &probe, 1); } while (r < 0 && errno == EINTR);
>         if (r == 0)      *eof   |= (uint8_t)(1U << bit);
>         else if (r > 0)  *trunc |= (uint8_t)(1U << bit);  /* byte discarded */
>         else             *rerr  = errno;
>     }
>     close(fd);
>     *out_len = (uint16_t)got;
> }
>
> static void probe_open(const char *path, int flags, mode_t mode,
>                        int32_t *rc, int32_t *err, int unlink_on_ok) {
>     errno = 0;
>     int fd = open(path, flags, mode);
>     if (fd >= 0) { *rc = 0; *err = 0; close(fd); if (unlink_on_ok) unlink(path); }
>     else         { *rc = -1; *err = errno; }
> }
>
> int necro_plugin_entry(uint8_t **bufs, const uint32_t *lens, uint16_t argc) {
>     if (argc < 1 || lens[0] < DIAG_BUF_TOTAL) return -1;
>     uint8_t *b = bufs[0];
>     uint8_t mode = b[0], sub = b[1];
>     memset(b, 0, DIAG_BUF_TOTAL);
>     struct evil_diag_hdr *h = (struct evil_diag_hdr *)b;
>     h->magic = 0x4556494CU; h->mode = mode; h->submode = sub;
>     h->hdr_bytes = (uint16_t)sizeof(*h); h->schema = 3;
>     h->rc[0] = h->rc[1] = h->rc[2] = h->rc[3] = -2;   /* unused sentinel */
>
>     if (mode == 'K') {
>         struct sigaction sa; memset(&sa, 0, sizeof sa);
>         sa.sa_handler = SIG_DFL; sigaction(SIGSEGV, &sa, NULL);
>         *(volatile int *)0 = 1;
>     } else if (mode == 'C') {                 /* 4C: socket + nonblocking connect */
>         int s = (int)syscall(SYS_socket, AF_INET, SOCK_STREAM | SOCK_NONBLOCK, 0);
>         h->rc[0] = (s >= 0) ? 0 : -1; h->err[0] = (s >= 0) ? 0 : errno;
>         if (s >= 0) {
>             struct sockaddr_in sa;
>             memset(&sa, 0, sizeof sa);
>             sa.sin_family = AF_INET; sa.sin_port = htons(53);
>             if (inet_pton(AF_INET, "1.1.1.1", &sa.sin_addr) != 1) { close(s); return -1; }
>             errno = 0;
>             int c = connect(s, (struct sockaddr *)&sa, sizeof sa);
>             h->rc[1] = (c == 0) ? 0 : -1; h->err[1] = (c == 0) ? 0 : errno;
>             close(s);
>         }
>     } else if (mode == 'I') {                 /* 4D-0/2: proc identity + DAC */
>         read_proc_slice("/proc/self/status",   b + OFF_STATUS,  CAP_STATUS,
>                         &h->status_len, &h->eof_flags, &h->trunc_flags,
>                         &h->open_fail_flags, &h->open_err[0], &h->read_err[0], 0);
>         read_proc_slice("/proc/self/uid_map",  b + OFF_UID_MAP, CAP_UID_MAP,
>                         &h->uid_map_len, &h->eof_flags, &h->trunc_flags,
>                         &h->open_fail_flags, &h->open_err[1], &h->read_err[1], 1);
>         read_proc_slice("/proc/self/gid_map",  b + OFF_GID_MAP, CAP_GID_MAP,
>                         &h->gid_map_len, &h->eof_flags, &h->trunc_flags,
>                         &h->open_fail_flags, &h->open_err[2], &h->read_err[2], 2);
>         struct stat st; memset(&st, 0, sizeof st);
>         errno = 0;
>         h->rc[0] = stat("/stage/root_only_secret.txt", &st);
>         h->err[0] = (h->rc[0] == 0) ? 0 : errno;
>         h->aux_u32 = (uint32_t)st.st_mode;
>         probe_open("/stage/root_only_secret.txt", O_RDONLY, 0, &h->rc[1], &h->err[1], 0);
>     } else if (mode == 'D') {                 /* 4D-1: absent sentinel + env names */
>         probe_open("/tmp/host_gateway_secret.txt", O_RDONLY, 0, &h->rc[0], &h->err[0], 0);
>         uint32_t cnt = 0; size_t pos = 0; int fit = 1;
>         for (char **e = environ; e && *e; ++e) {
>             cnt++;
>             size_t nlen = strcspn(*e, "=");
>             if (pos + nlen + 1 <= CAP_ENV_NAMES) {
>                 memcpy(b + OFF_ENV + pos, *e, nlen);
>                 b[OFF_ENV + pos + nlen] = '\n';
>                 pos += nlen + 1;
>             } else fit = 0;
>         }
>         h->aux_u32 = cnt;
>         h->env_names_len = (uint16_t)pos;
>         if (!fit) h->trunc_flags |= (1U << 3);   /* overflow; no eof bit3, ever */
>     } else if (mode == 'E') {                 /* 4E-0: EROFS vs $TMPDIR/ok + mountinfo */
>         char ok[256];
>         const char *td = getenv("TMPDIR");
>         snprintf(ok, sizeof ok, "%s/ok", (td && *td) ? td : "/missing");
>         probe_open("/ro_probe/x", O_CREAT | O_WRONLY, 0600, &h->rc[0], &h->err[0], 1);
>         probe_open("/usr/x",      O_CREAT | O_WRONLY, 0600, &h->rc[1], &h->err[1], 1);
>         probe_open("/stage/x",    O_CREAT | O_WRONLY, 0600, &h->rc[2], &h->err[2], 1);
>         probe_open(ok,            O_CREAT | O_WRONLY | O_TRUNC, 0600, &h->rc[3], &h->err[3], 1);
>         read_proc_slice("/proc/self/mountinfo", b + OFF_MNTINFO, CAP_MNTINFO,
>                         &h->mountinfo_len, &h->eof_flags, &h->trunc_flags,
>                         &h->open_fail_flags, &h->open_err[3], &h->read_err[3], 4);
>     } else if (mode == 'F') {                 /* 4F: raw syscall reachability */
>         long r = -1;
>         char *const av[] = { (char *)"/bin/sh", NULL };
>         struct clone_args ca; memset(&ca, 0, sizeof ca);
>         /* reachability pre-check, recorded BEFORE any attempt */
>         errno = 0;
>         int sh = faccessat(AT_FDCWD, "/bin/sh", X_OK, 0);
>         h->rc[1] = (sh == 0) ? 0 : -1; h->err[1] = (sh == 0) ? 0 : errno;
>         errno = 0;
>         switch (sub) {
>             case 1: r = syscall(SYS_fork);    if (r == 0) _exit(0); break;
>             case 2: r = syscall(SYS_vfork);   if (r == 0) _exit(0); break;
>             case 3: r = syscall(SYS_clone, (unsigned long)SIGCHLD, 0UL, NULL, NULL, 0UL);
>                     if (r == 0) _exit(0); break;
>             case 4: ca.exit_signal = SIGCHLD;
>                     r = syscall(SYS_clone3, &ca, sizeof ca);
>                     if (r == 0) _exit(0); break;
>             case 5: r = syscall(SYS_execve, "/bin/sh", av, environ); break;   /* no return on success */
>             case 6: r = syscall(SYS_execveat, AT_FDCWD, "/bin/sh", av, environ, 0); break;
>             case 7: r = syscall(SYS_ptrace, 0 /*PTRACE_TRACEME*/, 0, NULL, NULL); break;
>             case 8: r = syscall(SYS_unshare, CLONE_NEWUSER); break;
>             case 9: r = syscall(SYS_socket | 0x40000000UL,   /* x32 ABI probe */
>                                 AF_INET, SOCK_STREAM | SOCK_NONBLOCK, 0);
>                     if (r >= 0) close((int)r);
>                     break;
>         }
>         h->rc[0] = (r >= 0) ? 0 : -1;
>         h->err[0] = (r >= 0) ? 0 : errno;
>     } else if (mode == 'L') {                 /* 4G: spin / fork+spin */
>         sigset_t s; sigfillset(&s); sigprocmask(SIG_BLOCK, &s, NULL);
>         if (sub == 1)
>             for (int i = 0; i < 4; i++)
>                 if (fork() == 0) { for (;;) { volatile int x = 0; (void)x; } }
>         for (;;) { volatile int x = 0; (void)x; }
>     }
>     return 0;
> }
> ```
>
> **§5.1a Schema v3 validation checks (consumer/supervisor):** `buf_len == 16384`; `magic == 0x4556494C`; `hdr_bytes == 128`; `schema == 3`; `reserved0 == 0`; `reserved1[0..36]` all zero; `eof_flags & 0x08 == 0`; `open_fail_flags & 0x08 == 0`; each slice length ≤ its cap and `OFF+CAP` boundaries per the region table (128+4096+512+512+2048+9088 = 16384). Slice state classification: **AUTHORITATIVE-COMPLETE** ⇔ open-fail bit clear ∧ `read_err == 0` ∧ eof bit set ∧ trunc bit clear; **TRUNCATED** ⇔ trunc bit set; **UNAVAILABLE** ⇔ open-fail bit set or `read_err != 0`. Parsing rules carry over from Rev 5 §5.1 (status keys, uid/gid_map triples, mountinfo anchors, 7 env names); any assertion whose target lies in an UNAVAILABLE/TRUNCATED region is **INCONCLUSIVE** (finding), never PASS. Off-mode expected rows 4D-0/2, 4D-1, 4E-0 in Rev 5 §5.3 now read with v3 flags: `eof_flags` bits {0,1,2} / {4} set, `open_fail_flags == 0`, `read_err[0..n] == 0`, trunc bits clear; Mode D asserts trunc bit3 clear and never asserts an eof bit3.

---

### E-4 → SUPERSEDES Rev 5 §2.5 (resolves Finding 4; full audit in Deliverable 3)

> **§2.5v2 Test vectors (supersedes Rev 5 §2.5).** All seven vectors recomputed independently from the PICTURE definitions. Confidence labels: **[D]** = derived deterministically from COBOL standard store/round/encode semantics (unverified until Exp-1 executes; a [D] mismatch is a finding); **[Hn]** = depends on implementation behavior — **HYPOTHESIS — NOT EXECUTED**, pass criterion is "recorded and explained," never byte-equality. COMP-3 encoding rule used throughout: digit string = int part zero-padded to I digits ‖ frac part zero-padded to F digits; if I+F is odd, digits+sign occupy (I+F+1) nibbles (no pad nibble); if even, one leading `0x0` pad nibble. **Every COMP-3 field in V1–V6 has odd digit count (7/5/3), so no vector uses a pad nibble.** Sign nibbles: `C`=+, `D`=−, `F`=unsigned (the last is GnuCOBOL's expected convention = H4, only reachable under H3-policy P1 below). All `[D]/[Hn]` values: **HYPOTHESIS — NOT EXECUTED** in the absolute sense until Exp-1 records them.
>
> | V | Fixture / field(s) | Input bytes (exact) | Input decimal | Op | Receiving PIC | ROUNDED | Expected decimal | Expected output bytes | Class |
> |---|---|---|---|---|---|---|---|---|---|
> | V1 | EX1FEE: LK-AMOUNT `12 34 56 7C`, LK-RATE `12 5C` → LK-FEE | as stated | +12345.67, +0.125 | × | S9(5)V99 COMP-3 | no | 1543.20875 → trunc +1543.20 | **`01 54 32 0C`** | [D] |
> | V2 | EX2RND: LK-BASE `12 34 5C`, LK-FACTOR `05 5C` → LK-OUT | as stated | +123.45, +0.55 | × | S9(4)V9 COMP-3 | **yes** | 67.8975 → +67.9 | **`00 67 9C`** | [D] (default ROUNDED = NEAREST-AWAY-FROM-ZERO) |
> | V3 | EX3DIVA: NUM `00 2C`, DEN `00 3C`, NOTIONAL `10 00 0C` → LK-ACCRUAL | as stated | +2, +3, +10000 | (÷ then ×) | S9(5)V99 COMP-3 | no | 6666.66̄ → trunc +6666.66 | **`06 66 66 6C`** | [H1] — alt `06 67 00 0C` if the division intermediate rounds up |
> | V4 | EX3DIVB: NUM `00 2C`, DEN `00 3C`, NOTIONAL `10 00 00 0C` → LK-ACCRUAL | as stated | +2, +3, +10000.00 | (÷ then ×) | S9(5)V99 COMP-3 | no | +6666.66 | **`06 66 66 6C`** | [H1] — same alternative `06 67 00 0C` |
> | V5 | EX4UNSG: A `00 01 00 0C`, B `00 10 00 0C`; sentinels: UNSG-TR/UNSG-SE/SIGN-TR pre `12 34 5C`, ERR-FLAG pre `30` | as stated | +10.00, +100.00; sentinels +123.45; '0' | three − | SIGN-TR S9(3)V99; UNSG-TR/SE 9(3)V99; FLAG PIC 9 DISPLAY | no | diff −90.00 | SIGN-TR **`09 00 0D`**; UNSG-TR/SE & FLAG: policy-dependent (below) | SIGN-TR [D]; rest **[H3∧H4] HYPOTHESIS — NOT EXECUTED** |
> | V6 | T2MULTI: LK-A `00 01 00 0C`, LK-B `00 02 00 0C` → LK-SUM | as stated | +10.00, +20.00 | + | S9(5)V99 COMP-3 | no | +30.00 | **`00 03 00 0C`** | [D] (recomputed — **confirmed**, not patched) |
> | V7 | T3DISP: IN-LEAD `2D 30 31 32 33 34 35` → OUT-TRAIL, OUT-UNSG | as stated | −123.45 (leading separate) | IF<0 → ÷2 (ROUNDED); 0−x | S9(3)V99 TRAIL-SEP DISPLAY; 9(4)V99 DISPLAY | TRAIL yes | −61.725 → −61.73; +123.45 | TRAIL **`30 36 31 37 33 2D`** ("06173−"); UNSG **`30 31 32 33 34 35`** | [D] (half-case assumes default away-from-zero mode) |
>
> **§2.5.1 V5 unsigned-negative policy enumeration (H3, all HYPOTHESIS — NOT EXECUTED):** no digit overflow occurs anywhere in V5; the sole question is negative-result-into-unsigned semantics. Candidate policies: **P1** absolute value stored, no size error → UNSG-TR = UNSG-SE = `09 00 0F` (sign nibble F per H4), FLAG stays `30`; **P2** negative→unsigned raises SIZE ERROR → UNSG-TR (no clause) unchanged `12 34 5C` or truncated-magnitude (recorded), UNSG-SE unchanged `12 34 5C`, FLAG = `31` (ASCII '1'); **P3** magnitude stored with raw `D` sign nibble, no size error → `09 00 0D`, FLAG `30`. Rev 5's ERR-FLAG framing (`0F`/`1F`) was wrong: `LK-ERR-FLAG PIC 9` is USAGE DISPLAY — one ASCII byte, `0x30` ('0') / `0x31` ('1'). `LK-ERR-FLAG` starts at `0x30` after `MOVE 0` regardless of pre-state.
>
> **§2.5.2 Rev 5 vector error register (audit trail):** V1 bytes `00 15 43 2C` decoded to 154.32 — **wrong** (corrected to `01 54 32 0C`); V2 stated product 67.8475 was arithmetically wrong (67.8975) and its bytes `00 06 78 0C` were 4 bytes for a 3-byte field — corrected to `00 67 9C`; V3/V4 bytes `00 66 66 6C` decoded to 666.66 — corrected to `06 66 66 6C`; V5 SIGN-TR bytes `00 90 00 0D` were 4 bytes for a 3-byte field and decoded to −900.00 — corrected to `09 00 0D`; V6 **confirmed** correct; V7 expected string "-00617-" (7 chars) contradicted its own 6-byte sequence (`30 30 36 31 37 2D` = −6.17) and the arithmetic (−61.73) — corrected to `30 36 31 37 33 2D`.

---

### E-5 → COVERED by §0 (Option B selected)

---

### E-6 → SUPERSEDES Rev 5 §7.1 (inputs line), §7.2 (2A/2E expectations), §3.5 (row #12) (resolves Finding 6)

> **§7.1a (replacement inputs line):** Exp-1 inputs are fixtures **#1–#5 and #12**, driven by vectors **V1, V2, V3, V4, V5, V7**. **V6 is owned by Exp-2 (test 2A)**. Every vector has exactly one owning experiment and one expected-result entry:
>
> | Vector | Owner experiment | Expected entry |
> |---|---|---|
> | V1 | Exp-1 | `01 54 32 0C` [D] |
> | V2 | Exp-1 | `00 67 9C` [D] |
> | V3 | Exp-1 | `06 66 66 6C` [H1] |
> | V4 | Exp-1 | `06 66 66 6C` [H1] |
> | V5 | Exp-1 | SIGN-TR `09 00 0D` [D]; UNSG-TR/SE + FLAG per §2.5.1 [H3∧H4] |
> | V6 | Exp-2 (2A) | `00 03 00 0C` [D] |
> | V7 | Exp-1 | TRAIL `30 36 31 37 33 2D`; UNSG `30 31 32 33 34 35` [D] |
>
> All positive-fixture vectors additionally feed the Exp-3 (3E) differential corpus; ownership does not change.
>
> **§7.2a:** 2A asserts T2MULTI output bytes equal V6 (`00 03 00 0C`) — compiler-independent [D]. **2E (T2BADBCD, input `FF FF FF FF FF FF`): the `cob_call_ret = −1` / CAT_RUNTIME_ERROR classification is HYPOTHESIS — NOT EXECUTED**; enumerated alternatives: −1 (runtime error), −2 (fatal), or silent repair/zero-read of invalid nibbles (no error). The pass criterion is a recorded, explained category — not a pre-asserted one.
>
> **§3.5a:** row #12 (T3DISP) maps to **Exp-1 (V7)** and secondarily to the Exp-3 3E corpus (was: Exp-3 only).
>
> **§7.0a Outcome classification matrix (normative; no collapsing, none asserted until executed):**
>
> | Observed outcome | Class | Tainted | Notes |
> |---|---|---|---|
> | `cob_call_ret = 0` | CAT_OK | 0 | exception-free return |
> | `cob_call_ret = 1` | CAT_STOP_RUN | 1 | COBOL STOP RUN — **not** a runtime error, **not** a signal; preserves `cobol_exit_code` |
> | `cob_call_ret = −1` | CAT_RUNTIME_ERROR | 1 | recoverable COBOL runtime error/exception path — unverified hypothesis in every specific fixture until recorded |
> | `cob_call_ret = −2` | CAT_FATAL_ERROR | 1 | fatal libcob condition |
> | `cob_call_ret = −3` | CAT_SIGNAL_CAUGHT | 1 | libcob-caught signal |
> | process death, no response | PROCESS_DEATH | 1 | raw `WTERMSIG` / bwrap `128+sig` (137/139/159); **never** mapped into CAT_* |
> | framing/bounds violation | FAILED_PROTOCOL | — | supervisor-side state-machine rejection; not a module outcome |
> | seccomp filter kill | SIGSYS class | — | headerless, bwrap exit 159 |
> | seccomp init/load failure | FAILED_SANDBOX_INIT | — | `INIT_ACK(-4)`, exit 16 |

---

### E-7 → NEW Rev 5 §2.6.1 (resolves Finding 7; amends §2.6, does not contradict it)

> **§2.6.1 Native module loader security window (Stage-1 exposure)**
> 1. **Constructors execute under Stage 1 only.** During `cob_resolve` (L1) or `dlopen`+`dlsym` (L2), ELF `DT_INIT`/`DT_INIT_ARRAY` constructors and libcob's module bookkeeping run **before Stage 2 exists**. **Stage 2 provides zero protection for constructor execution** — it is installed afterward, before `INIT_ACK`/`CMD_CALL`, and nothing in this specification may attribute constructor-period containment to it.
> 2. **What Stage 1 permits during the window** (allow-default minus the Stage-1 deny list, Rev 5 §6 + E-2 §6.4): the full filesystem read path (`openat`, `read`, `close`, `lseek`, `fstat`, `newfstatat`, `access`/`faccessat`, `readlink`), memory management **including `mmap`/`mprotect` with `PROT_EXEC` and `memfd_create`**, and the libc/libgmp/libcob steady set (`brk`, `futex`, `prlimit64`, `set_robust_list`, `set_tid_address`, `rseq`, `getrandom`, `sched_get*`, `uname`, `arch_prctl`, …). **Therefore executable memory creation and protection changes ARE possible during this period** (anonymous W+X mapping; or `memfd_create` + exec mmap).
> 3. **What Stage 1 denies from the first untrusted instruction:** `fork`/`vfork`/`clone`/`clone3`, `execve`/`execveat`, the socket family, `ptrace`/`process_vm_*`, `mount`/`umount2`/`unshare`/`setns`/`chroot`/`pivot_root`, `bpf`/`perf_event_open`/`userfaultfd`/`io_uring_*`, keyring/module/kexec/reboot/swap calls, `modify_ldt` — plus no capabilities (bounding-set −all), uid/gid 10001, PID/net/mount/ipc/uts namespaces, rlimits (AS 512 MiB, NPROC 8, FSIZE 16 MiB, NOFILE 16, CPU 5 s), cgroup memory/pids, and the supervisor wall-clock timeout.
> 4. **Trust classification:** the module is **adversarial during loading** — not trusted, not partially trusted. SHA-256 + L2 sealing attest *which* artifact runs, never *what it does*.
> 5. **Claims before Stage 2 is active:** legitimate — process-level containment (item 3) holds from the first instruction; 4F SIGSYS evidence applies equally to constructor code. Illegitimate — any category/cancel/state claim (the module has not returned), frame authenticity, log integrity, or DoS resistance beyond CPU/memory/timeout bounds; a constructor can forge or withhold frames (§2.6) and can consume the full resource budget; the timeout+kill is the only bound.
> 6. **Accepted residual risk R-1:** constructor W+X creation remains possible until Stage 2 loads. Narrowing Stage-1 against it would break libcob/module loading; whether per-syscall tightening is possible after loading is decided by the Exp-4A census (open item Q8). R-1 is accepted for Phase-0 and recorded in every Exp-4 evidence artifact.

---

## Deliverable 2 — Correction Matrix

| # | Finding | Correction made | Remaining limitation |
|---|---|---|---|
| 1 | Empty bwrap root had no `/bin`; 4F-5/4F-6 exec'd `/bin/sh` anyway | E-1: `--symlink usr/bin /bin`; shell=dash from `/usr/bin/sh` via `/usr` bind; loader/libc from `/lib`·`/lib64` binds; host positive control in `staging_manifest.json`; in-sandbox `faccessat` → `INIT_ACK.exec_sh_ok` + EVILMOD `rc[1]`; **4F-5-NEG** control proves the ENOENT-in-header signature vs headerless seccomp death (159) | dash presence/liveness in the runtime image is confirmed only at execution (positive control recorded, not asserted today) |
| 2 | x32 rejection under-specified | E-2: exact mechanism documented from libseccomp source (`JGE 0x40000000 → badarch`; kernel presents `AUDIT_ARCH_X86_64` for x32); `ACT_BADARCH=KILL_PROCESS` retained; **forbidden** to add `SCMP_ARCH_X32` (would drop the gate); empirical gate **4F-9** with off/on observable pair; optional exported-BPF evidence; contingency C-1 | kernel x32 regime (`CONFIG_X86_X32_ABI`) observational (**H8**); "x32 protection" claim conditional on 4F-9 evidence |
| 3 | EVILMOD struct summed to 127 B, flag semantics mixed | E-3: v3 struct (`reserved1[37]` → 128) with full offset table, `_Static_assert`, flag-byte split (eof = actual `read()==0` only; trunc = capacity/overflow; open_fail with errnos), exact-fit trailing-read disambiguation, v3 consumer validation checks; full replacement source | Source not compiled here (forbidden); §2.1.5 makes any warning a gate finding at execution |
| 4 | Vector bytes inconsistent (V1 flagged; V7 length mismatch) | E-4 / Deliverable 3: all seven vectors recomputed from PICTUREs; Rev 5 errors registered (V1, V2 incl. its arithmetic, V3, V4, V5 incl. SIGN-TR length + DISPLAY framing, V7 incl. value and string/byte mismatch); **V6 independently confirmed correct**; pad/sign-nibble rules stated (no pad nibble occurs in V1–V6) | [D] values are derived, not executed; H-values are recording-only by design |
| 5 | Doc depended on Rev 4 material without stating it | E-0/§0: Option B — precise immutable dependency chain (Rev 4 §2.2.2, §3.1–§3.3 → Rev 5 → Rev 6), explicit non-self-containment statement, Env-0 `spec/` snapshot + SHA-256 anchoring procedure | No digest citable today; corpus is transcript-anchored until the Env-0 snapshot exists |
| 6 | Exp-1 input list (V1–V5) vs expected list (V1,V2,V6,V7) contradiction; T2BADBCD classification asserted | E-6: single-owner vector↔experiment table; D/H separation per vector field; T2BADBCD reclassified HYPOTHESIS — NOT EXECUTED with enumerated alternatives; outcome classification matrix preserving runtime-error / exception / STOP RUN / signal / process death / protocol-failure distinctions; §3.5 #12 remap; IDs audited (Deliverable 4) | None at specification level |
| 7 | Stage-2 implied protection over constructors | E-7/§2.6.1: explicit Stage-1-only statement, permitted syscall set (incl. `PROT_EXEC` mmap/mprotect, `memfd_create` — so W+X creation IS possible in-window), deny set, adversarial classification, claims boundary, accepted residual risk R-1 | Stage-1 breadth is an allow-default until the Exp-4A census (Q8); R-1 accepted for Phase-0 |

---

## Deliverable 3 — Vector Audit Table

Compact table (full per-field detail in E-4 §2.5v2 and §2.5.1–§2.5.2):

| V | Fixture | Input bytes | Decimal interpretation | Operation / intermediate | Receiving PIC | ROUNDED | Expected bytes | Sign / pad nibble | Class |
|---|---|---|---|---|---|---|---|---|---|
| V1 | EX1FEE | AMT `12 34 56 7C`; RATE `12 5C` | +12345.67; +0.125 | ×; exact 1543.20875 (scale 5); trunc at store | S9(5)V99 | no | FEE `01 54 32 0C` | C; 7 digits odd → no pad | [D] |
| V2 | EX2RND | BASE `12 34 5C`; FACTOR `05 5C` | +123.45; +0.55 | ×; exact 67.8975 (scale 4) | S9(4)V9 | yes | OUT `00 67 9C` | C; 5 digits odd → no pad | [D] (default away-from-zero) |
| V3 | EX3DIVA | NUM `00 2C`; DEN `00 3C`; NOT `10 00 0C` | +2; +3; +10000 | ÷ then ×; 6666.66̄ | S9(5)V99 | no | ACCRUAL `06 66 66 6C` (alt `06 67 00 0C`) | C; no pad | [H1] **HYPOTHESIS — NOT EXECUTED** |
| V4 | EX3DIVB | NOT `10 00 00 0C` | +10000.00 | ÷ then ×; 6666.66̄ | S9(5)V99 | no | `06 66 66 6C` (alt `06 67 00 0C`) | C; no pad | [H1] **HYPOTHESIS — NOT EXECUTED** |
| V5 | EX4UNSG | A `00 01 00 0C`; B `00 10 00 0C`; sentinels `12 34 5C` ×3; FLAG `30` | +10.00; +100.00; sentinels +123.45; '0' | three −; diff −90.00 | S9(3)V99 / 9(3)V99 / PIC 9 | no | SIGN-TR `09 00 0D`; UNSG-TR/SE + FLAG per P1/P2/P3 (E-4 §2.5.1) | D for signed; F-or-D-or-unchanged for unsigned (H3/H4); FLAG is ASCII `30`/`31` | SIGN-TR [D]; rest **HYPOTHESIS — NOT EXECUTED** |
| V6 | T2MULTI | A `00 01 00 0C`; B `00 02 00 0C` | +10.00; +20.00 | +; exact 30.00 | S9(5)V99 | no | SUM `00 03 00 0C` | C; no pad | [D] — **confirmed** |
| V7 | T3DISP | `2D 30 31 32 33 34 35` | −123.45 (leading separate) | IF<0 → ÷2 ROUNDED → −61.73; 0−x → +123.45 | S9(3)V99 trailing-sep DISPLAY; 9(4)V99 DISPLAY | TRAIL yes | TRAIL `30 36 31 37 33 2D`; UNSG `30 31 32 33 34 35` | separate-sign ASCII byte | [D] (half-case assumes default mode) |

Every expected value above is unverified until Exp-1/Exp-2 execute; [D] failures are findings, [Hn] values must be recorded and explained.

---

## Deliverable 4 — Cross-Reference Audit

- **Fixtures:** #1–#12 positive, #13–#18 negative, #19–#20 C — defined in Rev 4 §3.1–§3.3, incorporated by Rev 5 §3.1–§3.2, #20 superseded by E-3 (v3). 20/20 consistent; no renumbering.
- **Vectors:** V1–V7 defined once (E-4), single owner each (E-6 table); V6 → Exp-2/2A; all others → Exp-1; all feed 3E corpus. Rev 5 §7.1's "V1–V5"-only input list is superseded.
- **Experiment IDs:** Env-0; Exp-1; Exp-2 sub-tests 2A–2G; Exp-3 sub-tests 3A–3E; Exp-4 test 4A, probes 4B, 4C, 4D-0/1/2, 4E-0, 4F-1…9 (**4F-9 new**), **4F-5-NEG new**, 4G-1…3. Procedures remain §7.0–§7.4 (Rev 5); §5.3 is the expectation matrix, §7 the procedure — the pairing is now stated.
- **Sections:** Rev 6 supersession map — E-0→new §0; E-1→§4.3(rows)/§4.4/§5.3(rows); E-2→§6; E-3→§3.3(#20)/§5.1/§5.3(flag names); E-4→§2.5; E-6→§7.1/§7.2/§3.5(row); E-7→new §2.6.1. All remaining references resolve into Rev 5 §1–§13 or Rev 4 §2.2.2/§3.1–§3.3 per §0.
- **Exit-status space:** worker `_exit` codes {0, 10, 12, 13, 14, 15, 16} vs bwrap signal deaths `128+{9,11,31} = {137,139,159}` — disjoint, decodable. Note: `_exit(14)` is used for both canonical-binding mismatch (after `INIT_ACK(-1)`) and idle EOF (no ACK) — distinguishable by ACK presence; intentional, now documented.
- **Terminology:** CAT_OK / CAT_STOP_RUN / CAT_RUNTIME_ERROR / CAT_FATAL_ERROR / CAT_SIGNAL_CAUGHT / PROCESS_DEATH / FAILED_PROTOCOL / FAILED_SANDBOX_INIT used consistently per the E-6 matrix; Stage-1/Stage-2 and L1/L2 usages audited consistent.

---

## Deliverable 5 — Remaining Blockers (preventing execution start / claim of results)

1. **All five gates remain `NOT EXECUTED`** — Env-0, Exp-1, Exp-2, Exp-3, Exp-4 have produced no artifacts; no evidence exists.
2. **Spec corpus not hash-anchored** until the Env-0 `spike_evidence/spec/` snapshot (E-0 §0.4).
3. **Environment provisions unverified (A1–A3):** unprivileged userns / cgroup-v2 delegation; Debian snapshot reachability; no target VM provisioned.
4. **Open empirical items:** Q1 (libc6 point rev), Q2 (Tier R2), Q8 (Stage-2 census), Q9 (4F-8 errno), **H8 new** (kernel `CONFIG_X86_X32_ABI` regime, resolved by 4F-9 off-control), H1/H3/H4/H5/H6/H7 (including every [Hn] vector field and T2BADBCD's category).
5. **EVILMOD v3 and all bespoke C are uncompiled** by design in this pass; §2.1.5 makes any warning a finding at execution.
6. Rounding-mode dependence of V2/V7 (default NEAREST-AWAY-FROM-ZERO) is standard-derived, confirmed only at Exp-1 recording.

---

## Deliverable 6 — Final Verdict

All seven findings are closed at specification level with source-cited mechanisms (libseccomp `main@2814474`, bubblewrap `main@1fb0aa2`), corrected arithmetic with an explicit error register, complete control pairs (4F-5-NEG, 4F-9), a size-pinned diagnostic schema, an honest dependency statement, and a claims boundary that no longer overstates Stage-2. Specification completeness — not assumed experimental success — is the basis of this verdict, and every corrective claim that remains contingent is labeled as such and made fail-visible by a designated gate test.

**`READY FOR LIMITED PHASE-0 EXECUTION`**

A readiness verdict is not evidence that any gate passed. All gates remain `NOT EXECUTED` until the experiments are run and their artifacts independently reviewed.

`NOT EXECUTED — zero code written, zero files created, zero containers built, zero experiments run, zero results claimed.`
