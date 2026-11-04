# NecroSpec — Phase-0 Technical Spike Execution Specification (Rev 5)

**Execution Status:**
`NOT EXECUTED — zero code written, zero files created, zero containers built, zero experiments run, zero results claimed.`

**Authorization Scope:** Documentation-only specification audit and revision. Repository code, workspace files, container builds, package installations, compiler executions, security probes, deployments, and product implementation remain **unauthorized**.

---

## §1 — Rev 4 → Rev 5 Change Log

| # | Rev 4 Defect | Why Rev 4 Was Wrong/Incomplete | Rev 5 Correction (§) |
|---|---|---|---|
| 1 | §2.4, §2.5, §5.3 were referenced but **absent**; experiment procedures existed only as gate-table summaries. | A specification that references its own missing sections is not complete, and the claim of completeness in Rev 4 §12 was invalid. | Full reference-interpreter semantics (**§2.4**), 7-vector table with exact input bytes and hypothesis-tagged outputs (**§2.5**), and complete per-experiment procedures (**§7**, which supersedes old §5.3). Completeness cross-check in **§11**. |
| 2 | `/stage/root_only_secret.txt` was probed by EVILMOD but **never specified**: creation, owner, mode, staging step all undefined; DAC `EACCES` was asserted without a mechanism. | A mode-`0600` root-owned file does not exist by accident; without a staging procedure the `EACCES` assertion was untestable and the `EACCES`-vs-`EROFS` attribution muddled. | Explicit staging procedure (host-side `install -o 0 -g 0 -m 0600` before the stage dir is locked to `0555`), with mount-level `EROFS` (via `/ro_probe`, mode `0777`) deliberately **separated** from DAC `EACCES` (via the secret, mode `0600`) (**§4.3, §4.4**). |
| 3 | Sandbox `/tmp` was never defined; Mode `D` probed `/tmp/host_gateway_secret.txt` without proving `/tmp` is an empty sandbox tmpfs. | If the host `/tmp` were visible, the probe's `ENOENT` would be a false pass; if `/tmp` didn't exist at all, `ENOENT` proves nothing about mount isolation. | `--tmpfs /tmp` added to the `bwrap` profile; host-side root-owned `0600` sentinel file `/tmp/host_gateway_secret.txt` created and `stat`-recorded before each run, so `ENOENT` inside the sandbox proves mount-namespace emptiness (**§4.3, §5.4 Mode D**). |
| 4 | Mode `F` assumed `/bin/sh` exists in the sandbox "because `/usr` is mounted." | `execve("/bin/sh")` reachability depends on the host root bind exposing the merged-`/usr` `/bin → usr/bin` symlink — an unverified assumption. | Worker startup performs `faccessat(AT_FDCWD, "/bin/sh", X_OK, 0)` and records `exec_sh_ok` in the extended `INIT_ACK`; EVILMOD Mode `F` independently records the same probe before attempting `execve` (**§2.3.3, §5.1**). If absent, off-mode `sub=5/6` expects `rc[0]=-1, err=ENOENT(2)` — a documented, distinguishable outcome, not a silent failure (**§5.4**). |
| 5 | Seccomp policy used wildcards (`socket*`), did not state the default action, target architecture, bad-arch behavior, `libseccomp` API requirements, or argument comparisons, and had no off-mode controls for Mode `F`. | Not implementable as written; `socket*` is not a syscall name; `SCMP_ACT_KILL_PROCESS` requires libseccomp API level ≥ 3 (verified in `seccomp.h.in`); without `ACT_BADARCH` pinning, x32-ABI syscalls bypass a native-only filter; without off-mode controls, "blocked by seccomp" claims are unsupported. | Complete policy in **§6**: default `SCMP_ACT_ALLOW` (Stage-1) with fail-closed resolution (`__NR_SCMP_ERROR`/`__NR_SCMP_UNDEF` → fatal), `SCMP_ARCH_X86_64`-only + `ACT_BADARCH=KILL_PROCESS`, API ≥ 3 check, exact `mmap`/`mprotect`/`pkey_mprotect` rules (`arg=2`, `SCMP_CMP_MASKED_EQ`, mask `PROT_EXEC=0x4`, value `0x4`), full Stage-1/Stage-2 rule tables, and off-mode controls for **all eight** Mode `F` probes with off/on observable pairs (**§5.4**). |
| 6 | EVILMOD `gid_map` call passed `&h->uid_map_len ? &h->gid_map_len : &h->gid_map_len` — a meaningless ternary over an already-written field. | Copy/paste defect; both branches wrote the same (correct) pointer but the expression is nonsense and signals unreviewed code. | Replaced with `&h->gid_map_len`; header schema redesigned as v2 (128 B) with per-slice `open_err`/`read_err` arrays and separated `eof_flags` (kernel EOF observed) vs `trunc_flags` (capacity exhausted without EOF) vs `open_fail_flags` (**§5.1**). |
| 7 | Diagnostics conflated "EOF" with "buffer full," did not record open/read failures or errnos, and defined no parsing rules or unused-slot sentinels. | A truncated `status` read and a fully-read `status` were indistinguishable; assertion targets could be missing from a truncated capture with no detection. | Schema v2: distinct flag bytes, explicit sentinel `rc=-2` for unused probe slots, documented parsing rules for `status`/`uid_map`/`gid_map`/`mountinfo`/env-names, and an inconclusive-outcome rule when an assertion target falls in an uncaptured region (**§5.1, §5.2**). |
| 8 | Wire bounds were arithmetically inconsistent: `MAX_ARG_BYTES=16384`, `MAX_TOTAL=32768`, but `MAX_RESP_PAYLOAD=34048` / frame `36864` with no derivation, and `MAX_REQ_PAYLOAD=33024` matched nothing. | The numbers did not follow from any layout; §8's audit requirement would have failed. | Bounds recomputed from first principles: `CMD_CALL` max = 4+64+32768 = **32836**; `CALL_ACK` max = 16+64+1024+32768 = **33872**; frames = payload+8 → **32844 / 33880**; complete overflow-safe validation rules (**§2.3.2, §11**). |
| 9 | No IPC trust model: module and worker share one process, one FD table; Rev 4 framing rules implied more integrity than they can deliver. | A hostile module can read FD 3, write forged frames to FD 4, pollute the log, or close FDs. Message framing cannot prove response authenticity. | Dedicated trust-boundary & threat-model section: module classified adversarial; supervisor treats every worker frame as untrusted input; malformed framing → kill + `FAILED_PROTOCOL`; the exact set of integrity claims the architecture can and cannot make (**§2.6**). |
| 10 | Base image digest was a placeholder (`@sha256:<CAPTURED_MANIFEST_DIGEST>`); "captured environment" vs "specified environment" were conflated; the Python lock mixed pinned versions with missing hashes. | A digest placeholder pins nothing; pre-execution vs post-capture state must be explicit. | Pinning **procedure** replaces the placeholder (digest captured at build time and recorded before any layer is built); environment classified as `SPECIFIED` now, `CAPTURED` only after Env-0 artifacts exist; lock classified as an Env-0 generated-and-retained artifact, with exact versions/filenames plus 7 captured reference digests and mandatory `pip hash` re-verification (**§2.1.2–2.1.4**). |
| 11 | Compiler/linker warnings were not governed. | `-Wall -Wextra` without `-Werror` lets findings scroll by; `cobc` has no `-Werror`. | All bespoke C (`EVILMOD.c`, workers, `exp1_oneshot.c`) compiles with `-Wall -Wextra -Werror`; `cobc` stderr captured verbatim into evidence and **any non-empty warning output is a gate finding** blocking `PASS` (**§2.1.5, §7**). |
| 12 | Rev 4 invented a nonexistent `libcob` `runtime.cfg` key (`load_case`). | `load_case` is not a GnuCOBOL runtime configuration key; citing it fabricated behavior. | Removed. Canonical name→path binding rests entirely on the worker-side `strcmp` pre-open check + single-dir `COB_LIBRARY_PATH=/stage` + absence of `COB_PRE_LOAD` + `physical_cancel no` (a real key) in `runtime.cfg` (**§2.3.3, §4.2**). |
| 13 | Mode `C` used a blocking `connect()` to `1.1.1.1:53` with no timeout. | In a netns without routes this returns `ENETUNREACH` quickly, but a route misconfiguration could block the probe for minutes inside the 1 s timeout window, converting a security probe into a timeout test. | Socket created with `SOCK_NONBLOCK`; expected off-mode `connect()` result `EINPROGRESS(115)` (errno recorded, `rc=-1` asserted) — bounded and hang-proof (**§5.4**). |
| 14 | GnuCOBOL-specific behaviors (division-intermediate truncation point, size-error store policy without a clause, unsigned sign nibble, uninitialized WS init value, omitted-`USING` crash mode, `T2CRASH` catch-vs-death) were written as if known. | These are exactly the things the spike exists to measure; asserting them pre-execution is fabrication. | Re-tagged as explicit empirical hypotheses **H1–H6** with pass criteria of "recorded and explained," not "matches a claimed value" (**§2.5, §7**). |
| 15 | Exp-2 category tests lacked an explicit fixture mapping (T2STOP is grammar-invalid for NVS-0 yet needed for `CAT_STOP_RUN`). | Unstated dual role would look like a contradiction. | Negative fixtures are **valid GnuCOBOL, invalid NVS-0**; Exp-2 compiles `T2STOP`/`T2BADBCD`/`T2CRASH` directly with `cobc` to exercise categories 1/2/3-or-4. Mapping table added (**§3.5**). |
| 16 | All section/fixture/test cross-references unaudited; COMP-3 byte-length math never tabulated. | Required by this audit. | **§11** cross-reference and arithmetic audit added (section map, byte-length table, bound arithmetic, exit-code decodings). |

---

## §2 — Normative Specification

### §2.1 Environment, Toolchain Pinning & Reproducibility (`Env-0`)

#### §2.1.1 Host
Dedicated x86_64 Linux VM, kernel ≥ 6.1, unified cgroup v2 at `/sys/fs/cgroup` with `memory`, `pids`, `cpu` controllers delegated to `necro.slice`; unprivileged `bwrap` user/mnt/pid/net/ipc/uts/cgroup namespaces operational; `CONFIG_SECCOMP_FILTER=y`. `sysctl` values `kernel.unprivileged_userns_clone`, `kernel.apparmor_restrict_unprivileged_userns`, `vm.overcommit_memory`, and Yama `ptrace_scope` are **recorded** in `env0/host_sysctls.txt` (assumption **A1**, §10).

#### §2.1.2 Base image & Debian snapshot pinning (pre-execution procedure — replaces Rev 4's digest placeholder)
1. `docker pull python:3.12-slim-trixie`; capture `docker image inspect --format '{{.RepoDigests}}'` → write the **exact** manifest digest into `env0/image_digest.txt`. The Dockerfile's `FROM` line is then rewritten to `python:3.12-slim-trixie@sha256:<that digest>`. **No layer is built until this file exists and is non-placeholder.**
2. `/etc/apt/sources.list.d/debian.sources` is overwritten with pinned `deb822` stanzas against `https://snapshot.debian.org/archive/debian/20261020T000000Z` (`trixie`, `trixie-updates`) and `https://snapshot.debian.org/archive/debian-security/20261020T000000Z` (`trixie-security`), with `Check-Valid-Until: "false"` and `Acquire::Retries "5"`.
3. `apt-get update && apt-get install --no-install-recommends` of: `gnucobol3`, `libcob4-dev`, `gcc`, `libgmp-dev`, `libseccomp-dev`, `bubblewrap`, `util-linux`, `coreutils`. Expected baseline (verified against Debian trixie): `gnucobol3=3.2-3`, `libcob4t64=3.2-3`, `gcc=4:14.2.0-1`, `libgmp-dev=2:6.3.0+dfsg-3`, `libseccomp2/libseccomp-dev=2.6.0-2`, `bubblewrap=0.12.0-1~deb13u1`, `util-linux=2.41-5`. The exact `libc6`/`libc6-dev` `deb13uN` point revision is **resolved by the snapshot at install time** and recorded (open item **Q1**).
4. `dpkg-query -W -f='${Package}=${Version}\t${Architecture}\n'` → `env0/dpkg_manifest.txt`; plus SHA-256 of every installed `.deb`. Any deviation from the baseline above is a **finding**, not a silent update.
5. `strace` is installed **only** in a separate profiling image used by Exp-4A; it is absent from the runtime sandbox image (verified by `dpkg -s strace` failing inside the sandbox image).

#### §2.1.3 Python dependency lock (classified: **Env-0 generated and retained artifact**)
Target: CPython 3.12, `linux_x86_64`, `pip install --no-index --find-links=/wheels --no-deps --require-hashes -r requirements-spike.lock`, followed by `pip check`. The lock covers **8 distributions** — the complete transitive closure, verified against PyPI metadata: `lark` (no mandatory deps), `hypothesis` (→ `sortedcontainers>=2.1.0,<3.0.0` mandatory), `pytest` (→ `iniconfig>=2`, `packaging>=24`, `pluggy>=1.6,<2`, `pygments>=2.15`; `colorama` is win32-only and `exceptiongroup`/`tomli` are `python_version<3.11`-only, both excluded on this target).

Exact pins and wheel filenames:

| Distribution | Version | Wheel filename | Captured SHA-256 (reference, 2026-11-04) |
|---|---|---|---|
| lark | 1.3.1 | `lark-1.3.1-py3-none-any.whl` | `c629b661023a014c37da873b4ff58a817398d12635d3bbb2c5a03be7fe5d1e12` |
| hypothesis | 6.170.14 | resolved by pip at Env-0 (both `cp311-abi3-manylinux_2_17_x86_64…` and `cp312-cp312-manylinux…` wheels exist; the lock pins whichever the target interpreter resolves) | regenerated at Env-0 (`pip hash`) |
| sortedcontainers | 2.4.0 | `sortedcontainers-2.4.0-py2.py3-none-any.whl` | `a163dcaede0f1c021485e957a39245190e74249897e2ae4b2aa38595db237ee0` |
| pytest | 9.2.0 | `pytest-9.2.0-py3-none-any.whl` | `006823d1759e40b4546ff4296945eda3f0692e799f724bb235edd0512d42eead` |
| iniconfig | 2.3.1 | `iniconfig-2.3.1-py3-none-any.whl` | `47c2c35d936f5c649d8074c6464719a42966a67b5cebad01e3e5784cf090cfb6` |
| packaging | 26.3 | `packaging-26.3-py3-none-any.whl` | `70fdb89fc4d4a9a043bf7372b8972bcc883fddff34ab55e9cf80d73875384763` |
| pluggy | 1.7.0 | `pluggy-1.7.0-py3-none-any.whl` | `20ac8237e37f1d6e7e75500cd663015177ba80c1a1a595ff6bae18a539ff8a2c` |
| pygments | 2.21.0 | `pygments-2.21.0-py3-none-any.whl` | `2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377137d9` |

Generation & verification procedure (mandatory, executed at Env-0):
```bash
python3.12 -m pip download --dest /wheels --only-binary=:all: --no-deps \
    lark==1.3.1 hypothesis==6.170.14 sortedcontainers==2.4.0 \
    pytest==9.2.0 iniconfig==2.3.1 packaging==26.3 pluggy==1.7.0 Pygments==2.21.0
python3.12 -m pip hash /wheels/*.whl      # digests transcribed into requirements-spike.lock
python3.12 -m pip install --no-index --find-links=/wheels --no-deps \
    --require-hashes -r requirements-spike.lock && python3.12 -m pip check
```
`--only-binary=:all:` is mandatory (sdist `tar.gz` artifacts exist for 7 of the 8 and must never enter the lock). The captured reference digests above **must** equal the `pip hash` output; any mismatch aborts Env-0 as a supply-chain finding. SDist and transitive-marker drift (e.g., a future pytest pulling new deps) is re-checked at Env-0; the lock is retained under `spike_evidence/env0/requirements-spike.lock`.

#### §2.1.4 Specified vs captured environment
Until Env-0 completes, the environment is **`SPECIFIED`** (this document). It becomes **`CAPTURED`** only when `spike_evidence/env0/` contains: `image_digest.txt`, `dpkg_manifest.txt`, `.deb`/`.whl` SHA-256 lists, `requirements-spike.lock`, `cobc --version` + `cobc -std=ibm --info` + `cob-config --cflags --libs` output, `buildkit_versions.txt` (`docker --version`, `docker buildx version`, `buildkitd --version`, storage driver), and `host_sysctls.txt`. No experiment may cite environment facts not present in these files.

#### §2.1.5 Warning policy (new)
All bespoke C compiles with `-O2 -Wall -Wextra -Werror`. `cobc` invocations capture stderr verbatim into evidence; **any non-empty `cobc` warning is a recorded finding** and blocks the corresponding gate `PASS` until root-caused. Warnings are findings, never noise.

#### §2.1.6 Reproducibility tiers
- **Tier R1** (mandatory): `.text` section SHA-256 identity via `objcopy -O binary --only-section=.text` across two clean builds under `SOURCE_DATE_EPOCH=1761004800 -frandom-seed=necro-p0 -ffile-prefix-map=/build=.`.
- **Tier R2** (observational): full ELF SHA-256 identity across builds ≥ 2 s apart — measures whether `cobc 3.2-3` normalizes `COB_BLD_DATE` in `.rodata` (open item **Q2**). Result recorded; only R1 is gate-blocking.
- **Tier R3** (observational): OCI manifest digest stability under BuildKit `--output type=oci,rewrite-timestamp=true`; BuildKit/buildx versions recorded per §2.1.4.

---

### §2.2 `NVS-0` Source Acceptance Pipeline (4 layers, unchanged from Rev 4 §2.2, carried forward normatively)

**Layer 1 — Preflight (byte-level, non-mutating):** 1 ≤ file ≤ 32,768 B, 1 ≤ lines ≤ 500; reject NUL/CR/TAB/bytes ≥ 0x80 with 1-based `(line, col, ERR_INVALID_CHAR)`; reject any pre-`\n` line length > 72 at `(line, 73, ERR_COL73_OVERFLOW)`; cols 1–6 = spaces/digits only (`ERR_SEQ_AREA`); col 7 ∈ {`' '`, `'*'`, `'/'`} else `(line, 7, ERR_INVALID_INDICATOR)`; Area A (cols 8–11) required for division/section headers and `01`/`77` entries; Area B (cols 12–72) required for `02`–`49` entries and all procedure statements.

**Layer 2 — Lexical (cols 8–72 of non-comment lines, case-insensitive):** `LEVEL_NUM = ^(0[1-9]|[1-4][0-9]|77)$` (66/88 excluded); `SIGNED_DEC_LIT = ^[+-]?([0-9]+(\.[0-9]+)?|\.[0-9]+)$`; `POS_INT = ^[1-9][0-9]*$`. `USER_IDENT`/`PROG_NAME` = `^[A-Za-z][A-Za-z0-9-]{0,29}$` with no trailing hyphen **and** `upper(word) ∉ RESERVED_WORDS`. `RESERVED_WORDS` = (a) all NVS-0 grammar keywords; (b) banned COBOL keywords (`STOP RUN CALL COPY REPLACE REDEFINES RENAMES OCCURS DEPENDING EXTERNAL GLOBAL SYNCHRONIZED SYNC JUSTIFIED BLANK POINTER COMP COMP-1 COMP-2 COMP-4 COMP-5 BINARY GO PERFORM THRU THROUGH EVALUATE WHEN ACCEPT OPEN READ WRITE CLOSE EXEC EXIT ALTER …`); (c) special registers and figurative constants (`RETURN-CODE TALLY SORT-RETURN WHEN-COMPILED LINAGE-COUNTER SHIFT-IN SHIFT-OUT DEBUG-ITEM ADDRESS LENGTH FUNCTION ZERO ZEROS ZEROES SPACE SPACES HIGH-VALUE HIGH-VALUES LOW-VALUE LOW-VALUES QUOTE QUOTES NULL NULLS`). Malformed words → `ERR_LEX_INVALID_WORD` at the **Lexical** layer.

**Layer 3 — Grammar (Lark LALR(1), zero conflicts — build must raise no conflicts):** identical to Rev 4 §2.2.2 grammar block, carried forward verbatim, with the normative property that `compute_se`/`add_se`/`sub_se`/`mul_se`/`div_se` **require** a terminal `END-*`; `if_stmt` requires `END-IF`. `MOVE 42 TO RETURN-CODE` fails here because the lexer emits a reserved token where `USER_IDENT` is required (lexer reservation → grammar rejection — the mechanism Rev 3 falsely attributed to grammar alone).

**Layer 4 — AST semantic:** symbol table with `ERR_DUPLICATE_SYMBOL`; group items forbid `PIC`/`SIGN`/`VALUE` and propagate `USAGE`; elementary items require `pic_clause` with expanded digits satisfying **1 ≤ I+F ≤ 18** (`ERR_PIC_DIGIT_LIMIT`); signed `DISPLAY` requires `SIGN … SEPARATE` (`ERR_OVERPUNCH_UNSUPPORTED`); `COMP-3` forbids a separate sign clause; every `USING` name resolves to a distinct `01`/`77` LINKAGE entry; every referenced identifier exists (`ERR_UNDECLARED_IDENT`) and is elementary, not a group (`ERR_NON_ELEMENTARY_TARGET`).

---

### §2.3 Hardened IPC Protocol v1.1, Bounds, and Name→Path Binding

#### §2.3.1 Descriptor inheritance & signal posture (carried forward normatively)
Supervisor creates three `O_CLOEXEC` pipes: `req_pipe`, `rep_pipe`, `log_pipe`. Launcher: `setsid()`; FD 0 = `/dev/null`; FD 1 = FD 2 = `log_w`; FD 3 = `req_r` (`PROTO_IN_FD`); FD 4 = `rep_w` (`PROTO_OUT_FD`) (staged via `F_DUPFD_CLOEXEC ≥ 10` before `dup2`); `close_range(5, ~0U, 0)`. Worker `main()`: `SIGPIPE` → `SIG_IGN` **first**, FD audit of `/proc/self/fd` (`_exit(13)` if anything outside {0,1,2,3,4} plus the cwd dirfd is open), `FD_CLOEXEC` on FDs 3/4. Supervisor also ignores `SIGPIPE` and handles `BrokenPipeError` explicitly.

#### §2.3.2 Wire envelope, recomputed bounds, EINTR loops, EOF state machine
Envelope (8 B, little-endian): `[u8 magic=0x4E][u8 version=1][u8 opcode][u8 flags=0][u32 payload_len]`.

**Bounds (derived, all checked in `uint64_t` before any buffer access):**

| Constant | Value | Derivation |
|---|---|---|
| `MAX_NAME_LEN` | 31 | identifier regex bound |
| `MAX_PATH_LEN` | 128 | canonical path bound |
| `MAX_ARGC` | 16 | fixed `len[16]` array |
| `MAX_ARG_BYTES` | 16384 | EVILMOD diagnostic buffer |
| `MAX_TOTAL_ARG_BYTES` | 32768 | aggregate cap |
| `MAX_ERR_BYTES` | 1024 | error text cap |
| `CMD_INIT` payload max | 195 | 2+2+32+31+128 |
| `CMD_CALL` payload max | **32836** | 1+1+2 + 4×16 + 32768 |
| `CALL_ACK` payload max | **33872** | (4+4+1+1+2+2+2) + 64 + 1024 + 32768 |
| `INIT_ACK` payload max | 1075 | 51 + 1024 |
| `MAX_WIRE_FRAME_BYTES` | **33880** | max payload 33872 + 8 |

Validation rules (§8 compliance): (a) `payload_len` checked against the **state-specific** expected maximum before allocation; static `.bss` buffers only, no heap; (b) every embedded length field (`name_len ≤ 31`, `path_len ≤ 128`, `argc ≤ 16`, each `len_i ≤ 16384`, `Σ len_i ≤ 32768`, `err_len ≤ 1024`) is checked **in `uint64_t` arithmetic** (`if (sum + len_i > MAX_TOTAL_ARG_BYTES) reject`), with the increment performed in a width that cannot wrap; (c) the frame's declared lengths must consume the payload **exactly** — trailing bytes or shortfall → `PROTOCOL_FAULT`; (d) no buffer is touched until (a)–(c) pass. `read_exact`/`write_all` are `EINTR`-safe loops returning `EOF_CLEAN` (clean EOF at frame boundary), `ERR_PREMATURE_EOF` (EOF mid-frame), `ERR_IO`, `ERR_EPIPE`. Premature EOF or any protocol fault → supervisor kills the worker, marks the run `FAILED_PROTOCOL`, recycles the PID; no retry on the same worker. Idle clean EOF without `CMD_QUIT` → worker `_exit(14)`.

Frames (v1.1):
- `CMD_INIT(0x01)`: `[u16 name_len][u16 path_len][u8 sha256[32]][name][path]`
- `INIT_ACK(0x81)`: `[i32 init_status][u8 actual_sha256[32]][u32 workdir_uid][u32 workdir_gid][u16 workdir_mode][u8 tmpdir_ok][u8 exec_sh_ok][u8 seccomp_mode][u16 err_len][err]` — fixed part **51 B**. `init_status`: `0` OK; `-1` name↔path mismatch (`_exit(14)`); `-2` SHA-256 mismatch (`_exit(12)`); `-3` load failure (`_exit(15)`); `-4` seccomp failure (`_exit(16)`). `exec_sh_ok` = `faccessat("/bin/sh", X_OK)` result (§5.4 dependency).
- `CMD_CALL(0x02)`: `[u8 reset_flag][u8 pad=0][u16 argc][u32 len_0..argc-1][bufs]`
- `CALL_ACK(0x82)`: `[i32 cob_call_ret][i32 cobol_exit_code][u8 outcome_cat][u8 tainted][u16 err_len][u16 argc][u16 pad=0][u32 len_0..15][err][bufs]`. Categories preserved without collapsing: `0`→`CAT_OK(0),tainted=0`; `1`→`CAT_STOP_RUN(1),tainted=1` (keeps `cobol_exit_code`, e.g. 42); `-1`→`CAT_RUNTIME_ERROR(2),tainted=1`; `-2`→`CAT_FATAL_ERROR(3),tainted=1`; `-3`→`CAT_SIGNAL_CAUGHT(4),tainted=1`. Any `tainted=1` → skip `cob_cancel`, flush `CALL_ACK`, `close(4)`, `_exit(10)`. `cob_call_with_exception_check()` does **not** recover from native crashes: a SIGSEGV that libcob's handler does not convert still kills the process; that outcome is recorded as a process death (§2.6), never as a category.
- `CMD_QUIT(0x03)` → `QUIT_ACK(0x83)[i32 tidy_rc]`, `close(3)`, `close(4)`, `_exit(0)`.

`bwrap` exit decoding: under `--unshare-pid`, bwrap's PID-1 reaper reports child signal deaths as exit `128+sig` (verified in `bubblewrap.c:propagate_exit_status`): SIGKILL(9)→137, SIGSEGV(11)→139, SIGSYS(31)→159. Direct (non-bwrap) runs report raw `WIFSIGNALED/WTERMSIG`. Supervisor records `{raw_wait_status, os_exit_code, os_term_signal, decoded_worker_signal}`.

#### §2.3.3 Canonical name→path binding (both loaders, pre-open)
L1 (`necro_worker`, GnuCOBOL): validate `name` against `^[A-Z0-9][A-Z0-9-]{0,30}$` (no trailing hyphen); `canon_path = "/stage/" + name + ".so"`; `strcmp(path, canon_path) != 0` → `INIT_ACK(-1)`, `_exit(14)` **before** any open/hash/resolve. Enforced context: `COB_LIBRARY_PATH=/stage` (single dir), no `COB_PRE_LOAD`, `COB_RUNTIME_CONFIG=/opt/necro/runtime.cfg` (contains only `physical_cancel no`), `/stage` ro-bind.
L2 (`necro_plugin_runner`, C): same canonical check (name regex `^[A-Za-z0-9][A-Za-z0-9_]{0,30}$`), then open (`O_RDONLY|O_NOFOLLOW|O_CLOEXEC`), `memfd_create("necro_l2", MFD_CLOEXEC|MFD_ALLOW_SEALING)`, copy ≤ 4 MiB while hashing, `fcntl(F_ADD_SEALS, F_SEAL_SEAL|F_SEAL_SHRINK|F_SEAL_GROW|F_SEAL_WRITE)`, close `/stage` fd, reject mismatch (`INIT_ACK(-2)`, `_exit(12)`), `dlopen("/proc/self/fd/<mfd>", RTLD_NOW|RTLD_LOCAL)` + `dlsym("necro_plugin_entry")`.
L1 hash check: read `canon_path`, verify SHA-256, then `cob_resolve(name)`. Post-hash mutation of the staged inode by a privileged host process is **not** prevented by L1 and is classified a Trusted-Host (TCB) violation (assumption **A2**, §10). Test `4B` mutates the staged `.so` **before** `CMD_INIT` → `INIT_ACK(-2)` + EOF + exit 12 (L1); with L2 the seal makes post-copy tamper kernel-impossible.

---

### §2.4 NVS-0 Reference Interpreter Semantics (new — resolves missing §2.4)

The differential oracle (Exp-3E) is a pure-Python evaluator over the accepted AST. Normative semantics:

1. **PIC model:** elementary item = (`usage` ∈ {COMP-3, DISPLAY}, `I` int digits, `F` frac digits, `signed`). Digit-count rule 1 ≤ I+F ≤ 18 (Layer 4).
2. **COMP-3 wire codec:** bytes = ⌈(I+F+1)/2⌉; digits packed two-per-byte high-nibble-first; final low nibble = sign (`0x0C` +, `0x0D` −; unsigned sign nibble per GnuCOBOL is hypothesis **H4**, expected `0x0F`, recorded). Decode rejects invalid digit nibbles (>9) → `ERR_INVALID_PACKED` (feeds T2BADBCD).
3. **DISPLAY codec:** one ASCII digit per position, `\x60`-style overpunch **rejected by construction** (signed DISPLAY requires `SIGN SEPARATE`); sign-separate = one leading or trailing ASCII `+`/`-` byte.
4. **Arithmetic:** exact rational evaluation (Python `fractions.Fraction`); intermediate scale = exact; final store: rescale to target (I,F) with truncation toward zero **unless** `ROUNDED` (half-away-from-zero). Whether GnuCOBOL's division intermediate truncates at the same point is hypothesis **H1**; the oracle uses exact intermediates and any mismatch is a recorded finding, folded into the oracle only as a *documented, explained* deviation rule — never silently.
5. **SIZE ERROR:** applies per arithmetic statement; with `ON SIZE ERROR` clause, target content is **unchanged** and the clause body executes; **without** a clause, store-vs-truncate-vs-raise behavior is GnuCOBOL-specific — hypothesis **H3**, recorded, not asserted.
6. **Control:** `IF` conditions compare exact numerics; statement lists execute in order; `GOBACK` ends. `MOVE` numeric→numeric rescales (truncate/round as above); `MOVE` literal→target same rule.
7. **State:** WORKING-STORAGE persists across calls in one worker process unless the program is `IS INITIAL` (re-initialized per entry) or `cob_cancel` runs (re-init to `VALUE` clauses; un-VALUED fields' reset content = hypothesis **H5**, expected zero-fill from `.bss`, recorded). Uninitialized COMP-3 content feeding arithmetic is decoded with H5 semantics and any invalid-nibble result is a recorded finding (feeds T3STATE/T3INIT).
8. **Byte-level parity:** oracle outputs are encoded through rule 2/3 codecs; comparison with worker output is exact byte equality (Exp-3E). No algebraic comparison.

### §2.5 Test Vectors (new — resolves missing §2.5; §7.1/§7.3 compliance)

Seven vectors; inputs are exact and spec-derived; outputs marked **[D]** are derived from COBOL standard semantics; outputs marked **[Hn]** are empirical hypotheses resolved by Exp-1/Exp-3 recording (not asserted).

| # | Fixture / record | Input bytes (exact) | Expected output bytes |
|---|---|---|---|
| V1 | EX1FEE (10 B) | `12 34 56 7C` `12 5C` | FEE = 12345.67×0.125 = 1543.20875 → trunc `00 15 43 2C` **[D]** |
| V2 | EX2RND (8 B) | `12 34 5C` `05 5C` | OUT = round(67.8475 → 1 dp) = +67.8 → `00 06 78 0C` **[D]** |
| V3 | EX3DIVA (11 B) | `00 2C` `00 3C` `10 00 0C` | ACCRUAL = trunc(⅔×10000) = +6666.66 → `00 66 66 6C` **[H1]** (exact intermediate assumed; truncation point recorded) |
| V4 | EX3DIVB (12 B) | `00 2C` `00 3C` `10 00 00 0C` | ACCRUAL = +6666.66 → `00 66 66 6C` **[H1]** (scale-invariance of division intermediate) |
| V5 | EX4UNSG (18 B) | A `00 01 00 0C`; B `00 10 00 0C`; pre: UNSG-TR `00 00 00 0F`, UNSG-SE `00 00 00 0F`, SIGN-TR `00 00 00 0C`, ERR-FLAG `0F` | SIGN-TR = −90.00 → `00 90 00 0D` **[D]**; UNSG-SE unchanged `00 00 00 0F` + ERR-FLAG `1F` **[H4-sign]**; UNSG-TR (overflow, **no** size-error clause) **[H3]** |
| V6 | T2MULTI (12 B) | `00 01 00 0C` `00 02 00 0C` `00 00 00 0C` | SUM = +00003.00 → `00 03 00 0C` **[D]** |
| V7 | T3DISP (19 B) | `2D 30 31 32 33 34 35` ("-012345") | TRAIL = "-00617-" (6 B `30 30 36 31 37 2D`) **[D]**; UNSG = "012345" (6 B) **[D]** |

Hypothesis register: **H1** division-intermediate truncation scale; **H3** size-error store policy without clause; **H4** unsigned COMP-3 sign nibble (`0x0F`) & unsigned literal encoding (`1F` for value 1); **H5** un-VALUED WS init/reset content; **H6** T2CRASH outcome (libcob-trapped → `-2/-3` category vs process death 139); plus Rev-4-carried **H7** omitted-`USING` outcome under `-fec=bound` (SIGSEGV vs `cob_call_ret=-1`). All H-items resolve to recorded observations in `exp1/results.jsonl` / `exp3/sticky_obs.json`; a hypothesis is never treated as an assertion in any pass criterion.

---

### §2.6 IPC Trust Boundary & Threat Model (new)

1. **Classification:** loaded native/COBOL module code is **adversarial** for all containment claims. The worker process hosting it is *payload infrastructure*, not TCB. The TCB for security claims = supervisor + kernel (namespaces, cgroups, seccomp) + `bwrap` + staged-artifact integrity **up to the moment of load**.
2. **FD exposure:** module and worker share one process and one FD table; a module **can** read FD 3 (steal in-flight requests), **write forged frames to FD 4**, write/forge log bytes on FDs 1/2, close any FD, and hang the loop. Protocol framing therefore provides **structure, not authenticity**. No claim of message authenticity, log integrity, or in-flight confidentiality is made.
3. **Supervisor posture:** every worker frame is **untrusted input**. Enforcement: strict state-machine framing validation (§2.3.2 rules a–d) with any violation → kill + `FAILED_PROTOCOL` + PID recycle; bounds enforced before buffer access; supervisor never derives security decisions from frame *content*, only from process-level observations (exit status, signal, cgroup state, wall clock) and host-side recomputation (Exp-3E oracle runs on the supervisor's own inputs, not on worker assertions).
4. **Legitimate integrity claims (exhaustive):** (i) process containment — capabilities, uid/gid, mount topology, seccomp denial, timeout kill, tree cleanup (Exp-4); (ii) pre-load artifact binding — the SHA-256-verified module is the one loaded (L2 sealed-memfd strong; L1 TCB-qualified); (iii) liveness and protocol observability; (iv) differential byte-parity between worker and independent oracle for non-tainted runs. **Illegitimate claims (explicitly prohibited):** authenticity of any post-load frame; that `CAT_*` categories reflect module *intent* rather than observed libcob outcomes; tamper-evidence of worker logs; DoS resistance inside the worker process (only timeout+kill bounds it). Framing alone never proves response authenticity; the canonical-path check prevents *which* artifact runs, not *what it says*.

---

## §3 — Fixture Inventory, Sources, and Mapping (20 fixtures)

**Count: 12 positive COBOL (#1–#12) + 6 negative COBOL (#13–#18) + 2 native C (#19–#20) = 20.**

### §3.1 Positive NVS-0 COBOL fixtures (#1–#12)
Sources are **byte-identical to Rev 4 §3.1** (verified line-by-line during this audit; fixed-format fences: cols 1–6 spaces, col 7 `' '`/`'*'`, Area A col 8, Area B col 12, ≤ 72 cols) and are carried forward normatively: `EX1FEE`, `EX2RND`, `EX3DIVA`, `EX3DIVB`, `EX4UNSG` (18 B record), `T2MULTI`, `CALC-FEE`, `T2BADBCD` (6 B record), `T3STATE` (9 B), `T3INIT` (IS INITIAL, 9 B), `T3STICKY` (2×3 B), `T3DISP` (19 B: 7+6+6).

### §3.2 Negative COBOL fixtures (#13–#18)
Sources byte-identical to Rev 4 §3.2, carried forward normatively: `T2STOP` (reserved `RETURN-CODE` + `STOP RUN`), `T2CRASH` (reserved `CALL`), `NEG_COL73` (byte 73 `'X'` on line 4), `NEG_BADIND` (`'-'` at col 7, line 6), `NEG_PIC19` (`S9(10)V9(9)` = 19 digits), `NEG_UNTERM_SE` (missing `END-COMPUTE`). Every rejection is asserted with its exact `(layer, error_code, line, col)` tuple in §7.3.

### §3.3 Native C fixtures — #19 unchanged, #20 revised (EVILMOD v2)

**#19 `crash_helper.c`** — byte-identical to Rev 4 §3.3 (SIGSEGV `crash_now`, statically linked via `-K crash_now`).

**#20 `EVILMOD.c` (v2)** — corrected per audit items 4/6/7; compiles clean under `-Wall -Wextra -Werror`:

```c
/* === #20: EVILMOD.c v2 (L2-loaded C probe module) === */
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

/* Buffer regions: 128 + 4096 + 512 + 512 + 2048 + 9088 = 16384 */
enum {
    DIAG_BUF_TOTAL = 16384,
    OFF_STATUS = 128,    CAP_STATUS    = 4096,
    OFF_UID_MAP = 4224,  CAP_UID_MAP   = 512,
    OFF_GID_MAP = 4736,  CAP_GID_MAP   = 512,
    OFF_ENV     = 5248,  CAP_ENV_NAMES = 2048,
    OFF_MNTINFO = 7296,  CAP_MNTINFO   = 9088   /* ends exactly at 16384 */
};

struct __attribute__((packed)) evil_diag_hdr {   /* v2, 128 bytes */
    uint32_t magic;          /* 0x4556494C "EVIL"                     +0  */
    uint8_t  mode;
    uint8_t  submode;        /* request echo                          +4  */
    uint16_t hdr_bytes;      /* 64 → 128                              +6  */
    uint8_t  schema;         /* 2                                     +8  */
    uint8_t  eof_flags;      /* bit0..4: kernel EOF (read()==0) seen  +9  */
    uint8_t  trunc_flags;    /* bit0..4: capacity full WITHOUT EOF    +10 */
    uint8_t  open_fail_flags;/* bit0..3: status,uid,gid,mountinfo     +11 */
    uint8_t  reserved0;      /*                                       +12 */
    int32_t  rc[4];          /* per-mode probes; -2 = unused slot     +13 */
    int32_t  err[4];         /* probe errnos (0 if rc>=0)             +29 */
    int32_t  open_err[4];    /* open() errno per proc slice           +45 */
    int32_t  read_err[4];    /* read() errno per proc slice           +61 */
    uint32_t aux_u32;        /* 'I': st_mode; 'D': env var count      +77 */
    uint16_t status_len;     /* stored bytes                          +81 */
    uint16_t uid_map_len;    /*                                       +83 */
    uint16_t gid_map_len;    /* FIX: dedicated field                  +85 */
    uint16_t env_names_len;  /*                                       +87 */
    uint16_t mountinfo_len;  /*                                       +89 */
    uint8_t  reserved1[36];  /*                                       +91 -> 127 */
};

static void read_proc_slice(const char *path, uint8_t *dst, size_t cap,
                            uint16_t *out_len, uint8_t *eof, uint8_t *trunc,
                            uint8_t *openfail, int32_t *oerr, int32_t *rerr,
                            uint8_t bit) {
    *out_len = 0; *rerr = 0;
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) { *openfail |= (uint8_t)(1U << bit); *oerr = errno; return; }
    size_t got = 0;
    for (;;) {
        ssize_t r = read(fd, dst + got, cap - got);
        if (r < 0) { if (errno == EINTR) continue; *rerr = errno; break; }
        if (r == 0) { *eof |= (uint8_t)(1U << bit); break; }
        got += (size_t)r;
        if (got == cap) { *trunc |= (uint8_t)(1U << bit); break; }
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
    h->hdr_bytes = (uint16_t)sizeof(*h); h->schema = 2;
    h->rc[0] = h->rc[1] = h->rc[2] = h->rc[3] = -2;   /* unused sentinel */

    if (mode == 'K') {
        struct sigaction sa; memset(&sa, 0, sizeof sa);
        sa.sa_handler = SIG_DFL; sigaction(SIGSEGV, &sa, NULL);
        *(volatile int *)0 = 1;
    } else if (mode == 'C') {                 /* 4C: socket + nonblocking connect */
        int s = (int)syscall(SYS_socket, AF_INET, SOCK_STREAM | SOCK_NONBLOCK, 0);
        h->rc[0] = (s >= 0) ? 0 : -1; h->err[0] = (s >= 0) ? 0 : errno;
        if (s >= 0) {
            struct sockaddr_in sa;
            memset(&sa, 0, sizeof sa);
            sa.sin_family = AF_INET; sa.sin_port = htons(53);
            if (inet_pton(AF_INET, "1.1.1.1", &sa.sin_addr) != 1) { close(s); return -1; }
            errno = 0;
            int c = connect(s, (struct sockaddr *)&sa, sizeof sa);
            h->rc[1] = (c == 0) ? 0 : -1; h->err[1] = (c == 0) ? 0 : errno;
            close(s);
        }
    } else if (mode == 'I') {                 /* 4D-0/2: proc identity + DAC */
        read_proc_slice("/proc/self/status",   b + OFF_STATUS,  CAP_STATUS,
                        &h->status_len, &h->eof_flags, &h->trunc_flags,
                        &h->open_fail_flags, &h->open_err[0], &h->read_err[0], 0);
        read_proc_slice("/proc/self/uid_map",  b + OFF_UID_MAP, CAP_UID_MAP,
                        &h->uid_map_len, &h->eof_flags, &h->trunc_flags,
                        &h->open_fail_flags, &h->open_err[1], &h->read_err[1], 1);
        read_proc_slice("/proc/self/gid_map",  b + OFF_GID_MAP, CAP_GID_MAP,
                        &h->gid_map_len, &h->eof_flags, &h->trunc_flags,   /* FIX */
                        &h->open_fail_flags, &h->open_err[2], &h->read_err[2], 2);
        struct stat st; memset(&st, 0, sizeof st);
        errno = 0;
        h->rc[0] = stat("/stage/root_only_secret.txt", &st);
        h->err[0] = (h->rc[0] == 0) ? 0 : errno;
        h->aux_u32 = (uint32_t)st.st_mode;
        probe_open("/stage/root_only_secret.txt", O_RDONLY, 0, &h->rc[1], &h->err[1], 0);
    } else if (mode == 'D') {                 /* 4D-1: absent sentinel + env names */
        probe_open("/tmp/host_gateway_secret.txt", O_RDONLY, 0, &h->rc[0], &h->err[0], 0);
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
        if (fit) h->eof_flags |= (1U << 3); else h->trunc_flags |= (1U << 3);
    } else if (mode == 'E') {                 /* 4E-0: EROFS vs $TMPDIR/ok + mountinfo */
        char ok[256];
        const char *td = getenv("TMPDIR");
        snprintf(ok, sizeof ok, "%s/ok", (td && *td) ? td : "/missing");
        probe_open("/ro_probe/x", O_CREAT | O_WRONLY, 0600, &h->rc[0], &h->err[0], 1);
        probe_open("/usr/x",      O_CREAT | O_WRONLY, 0600, &h->rc[1], &h->err[1], 1);
        probe_open("/stage/x",    O_CREAT | O_WRONLY, 0600, &h->rc[2], &h->err[2], 1);
        probe_open(ok,            O_CREAT | O_WRONLY | O_TRUNC, 0600, &h->rc[3], &h->err[3], 1);
        read_proc_slice("/proc/self/mountinfo", b + OFF_MNTINFO, CAP_MNTINFO,
                        &h->mountinfo_len, &h->eof_flags, &h->trunc_flags,
                        &h->open_fail_flags, &h->open_err[3], &h->read_err[3], 4);
    } else if (mode == 'F') {                 /* 4F: raw syscall reachability */
        long r = -1;
        char *const av[] = { (char *)"/bin/sh", NULL };
        struct clone_args ca; memset(&ca, 0, sizeof ca);
        /* reachability pre-check, recorded BEFORE any attempt */
        errno = 0;
        int sh = faccessat(AT_FDCWD, "/bin/sh", X_OK, 0);
        h->rc[1] = (sh == 0) ? 0 : -1; h->err[1] = (sh == 0) ? 0 : errno;
        errno = 0;
        switch (sub) {
            case 1: r = syscall(SYS_fork);    if (r == 0) _exit(0); break;
            case 2: r = syscall(SYS_vfork);   if (r == 0) _exit(0); break;
            case 3: r = syscall(SYS_clone, (unsigned long)SIGCHLD, 0UL, NULL, NULL, 0UL);
                    if (r == 0) _exit(0); break;
            case 4: ca.exit_signal = SIGCHLD;
                    r = syscall(SYS_clone3, &ca, sizeof ca);
                    if (r == 0) _exit(0); break;
            case 5: r = syscall(SYS_execve, "/bin/sh", av, environ); break;   /* no return on success */
            case 6: r = syscall(SYS_execveat, AT_FDCWD, "/bin/sh", av, environ, 0); break;
            case 7: r = syscall(SYS_ptrace, 0 /*PTRACE_TRACEME*/, 0, NULL, NULL); break;
            case 8: r = syscall(SYS_unshare, CLONE_NEWUSER); break;
        }
        h->rc[0] = (r >= 0) ? 0 : -1;
        h->err[0] = (r >= 0) ? 0 : errno;
    } else if (mode == 'L') {                 /* 4G: spin / fork+spin */
        sigset_t s; sigfillset(&s); sigprocmask(SIG_BLOCK, &s, NULL);
        if (sub == 1)
            for (int i = 0; i < 4; i++)
                if (fork() == 0) { for (;;) { volatile int x = 0; (void)x; } }
        for (;;) { volatile int x = 0; (void)x; }
    }
    return 0;
}
```
Note: `asm volatile("")` spin loops were replaced with volatile-store loops (`-Werror`-clean, same non-terminating semantics).

### §3.4 Compile & link sequences (carried forward + warning policy)
```bash
# T2CRASH.so — static -K crash_now binding
gcc -O2 -Wall -Wextra -Werror -fPIC -c crash_helper.c -o crash_helper.o
cobc -m -fformat=fixed -Wcolumn-overflow -Wall -std=ibm -O0 \
     -K crash_now T2CRASH.cbl crash_helper.o -o T2CRASH.so
# EVILMOD.so — L2 only
gcc -O2 -Wall -Wextra -Werror -shared -fPIC EVILMOD.c -o EVILMOD.so
```
`cobc` stderr is captured verbatim per §2.1.5.

### §3.5 Source-to-test mapping

| Fixture(s) | Exp-1 | Exp-2 | Exp-3 | Exp-4 |
|---|---|---|---|---|
| #1 EX1FEE / #7 CALC-FEE | V1 | — | 3E differential; lexer/AST positive | — |
| #2 EX2RND | V2 | — | 3E (ROUNDED) | — |
| #3 EX3DIVA / #4 EX3DIVB | V3, V4 | — | 3E (H1) | — |
| #5 EX4UNSG | V5 | — | 3E (H3/H4) | — |
| #6 T2MULTI | V6 | 2A–2C (basic call/recycle) | 3E | — |
| #8 T2BADBCD | — | 2E: `CAT_RUNTIME_ERROR(-1)`, tainted, err≤1024 B captured | invalid-packed decode | — |
| #9/#10 T3STATE, T3INIT | — | — | 3B sticky (10k calls), 3C cancel/reset, 3D H7, RSS guard | — |
| #11 T3STICKY | — | — | 3D-2/3 omitted-arg (H7) | — |
| #12 T3DISP | V7 | — | 3E (sign-separate codecs) | — |
| #13 T2STOP | — | 2D: compiled by cobc → `CAT_STOP_RUN(1)`, exit 42 | rejection tuple (Grammar) | — |
| #14 T2CRASH + #19 crash_helper | — | 2F-L1: `-K crash_now` static link → H6 outcome | rejection tuple (Grammar) | — |
| #15–#18 NEG_* | — | — | rejection tuples (Preflight×2, AST, Grammar) | — |
| #20 EVILMOD v2 | — | 2F-L2 (`necro_plugin_entry`) | — | 4B–4G full matrix |

---

## §4 — Sandbox Filesystem, Ownership Manifest, and `bwrap` Profile

### §4.1 `/work` ownership design (carried forward)
`bwrap --perms 1777 --size 33554432 --tmpfs /work` + `--chdir /work` (option-order sticky: `--perms`/`--size` precede their `--tmpfs`). Worker (already final `10001:10001`) validates `TMPDIR ^/work/[0-9a-f-]{36}$`, `umask(0077)`, `mkdir(TMPDIR, 0700)` (`EEXIST` fatal), `chdir`, `lstat(".")` verifying `st_uid==10001 ∧ st_gid==10001 ∧ (mode&07777)==0700`, creates/writes/unlinks `$TMPDIR/.startup_probe`, records `workdir_uid/gid/mode` + `tmpdir_ok` in `INIT_ACK`.

### §4.2 Environment & config
`env -i` passes exactly six variables: `PATH=/usr/bin:/bin`, `COB_LIBRARY_PATH=/stage`, `COB_RUNTIME_CONFIG=/opt/necro/runtime.cfg`, `COB_PHYSICAL_CANCEL=N`, `LC_ALL=C`, `TMPDIR=/work/$UUID`; `bwrap` itself adds `PWD` (verified `xsetenv("PWD", new_cwd, 1)`) → **7 total**. `/opt/necro/runtime.cfg` contains exactly `physical_cancel no` (no invented keys). No `/etc` mounts.

### §4.3 Exact filesystem & ownership manifest (new)

| Sandbox path | Source | Owner (host) | Mode | Exists in sandbox | Purpose / expected probe result |
|---|---|---|---|---|---|
| `/stage` (mount) | ro-bind `/var/lib/necro-stage/$UUID` | root:root | dir `0555` | yes | stage; traversal OK for uid 10001 (r-x) |
| `/stage/<MOD>.so` | staged by supervisor pre-launch | root:root | `0444` | yes | target module; readable; hash-verified |
| `/stage/root_only_secret.txt` | `install -o 0 -g 0 -m 0600 /dev/null …` **before** dir chmod `0555`; content 64 random bytes; recorded in staging manifest | root:root | `0600` | yes | DAC probe: `stat` OK (`rc[0]=0`, `aux_u32 & 07777 == 0600`); `open(O_RDONLY)` → **EACCES(13)** — genuine DAC denial (uid 10001 vs root:root 0600), independent of mount-ro |
| `/ro_probe` | host dir mode `0777` (created per run, mode recorded) | root:root | `0777`, mount remounted ro | yes | `open(O_CREAT\|O_WRONLY)` → **EROFS(30)** — pure mount-ro proof (DAC would have allowed) |
| `/usr`, `/lib`, `/lib64`, `/opt/necro` | ro-binds | root:root | — | yes | runtime; read-only |
| `/bin` | host root bind preserves merged-usr symlink `/bin → usr/bin` | root:root | symlink | yes → `/bin/sh` reachable | Mode F target; verified by `faccessat` (worker `INIT_ACK.exec_sh_ok`, EVILMOD `rc[1]`) — **not assumed** |
| `/tmp` | `--tmpfs /tmp` (`--perms 0755`) | root:root | `0755`, empty | yes, **empty** | isolation proof |
| `/tmp/host_gateway_secret.txt` | **host-side sentinel**: supervisor (root) creates `/tmp/host_gateway_secret.txt` mode `0600` root:root, content `NECRO-SENTINEL-<uuid>`, `stat` recorded pre-run | root:root | `0600` | **intentionally absent** in sandbox | Mode D probe → **ENOENT(2)** proves sandbox `/tmp` is the empty tmpfs; a hit would mean a mount leak = FAIL |
| `/work` | tmpfs | root:root | `01777` | yes | sticky scratch |
| `/work/$UUID` | created by worker at startup | **10001:10001** | `0700` | yes | `TMPDIR`; `$TMPDIR/ok` creatable (`rc[3]=0`) |
| `/proc`, `/dev` | `--proc /proc --dev /dev` | — | — | yes | `/proc/self/{status,uid_map,gid_map,mountinfo}`, `/dev/null` |
| `/var/lib/necro-stage/$UUID/` (host) | per-run staging dir | root:root | dir `0555`; files `0444`; secret `0600` | host-side | per-run staging manifest records every path+uid+gid+mode+sha256 |

Every path EVILMOD or the worker touches appears above; the only intentionally-absent path is `/tmp/host_gateway_secret.txt` (documented). Ordering rule: staging (root, host) → stage dir chmod `0555` → sentinel creation → worker launch.

### §4.4 Exact sandbox command (carried forward, `/tmp` added)
```bash
prlimit --as=536870912 --cpu=5 --fsize=16777216 --nofile=16 --core=0 --nproc=8 -- \
setpriv --reuid=10001 --regid=10001 --clear-groups \
        --inh-caps=-all --ambient-caps=-all --bounding-set=-all --no-new-privs -- \
env -i PATH=/usr/bin:/bin COB_LIBRARY_PATH=/stage \
       COB_RUNTIME_CONFIG=/opt/necro/runtime.cfg COB_PHYSICAL_CANCEL=N \
       LC_ALL=C TMPDIR=/work/$UUID \
bwrap --unshare-all --unshare-user --disable-userns --new-session --die-with-parent \
      --cap-drop ALL --uid 10001 --gid 10001 \
      --ro-bind /usr /usr --ro-bind /lib /lib --ro-bind /lib64 /lib64 \
      --ro-bind /opt/necro /opt/necro \
      --ro-bind /var/lib/necro-stage/$UUID /stage \
      --proc /proc --dev /dev \
      --perms 0777 --dir /ro_probe \
      --perms 1777 --size 33554432 --tmpfs /work \
      --perms 0755 --tmpfs /tmp \
      --chdir /work \
      --remount-ro / -- \
      /opt/necro/<necro_worker_or_necro_plugin_runner> --worker-seccomp=<off|on>
```

---

## §5 — EVILMOD v2 Diagnostic Mapping and Full Exp-4 Matrix

### §5.1 Evidence schema & parsing rules (restores and completes §5.3)
Header v2 = 128 B (§3.3). Payload regions: status@128 cap 4096; uid_map@4224 cap 512; gid_map@4736 cap 512; env@5248 cap 2048; mountinfo@7296 cap 9088; total exactly 16384. **Parsing rules:** `/proc/self/status` — scan complete `\n`-terminated lines only; keys `Uid`,`Gid`,`Groups`,`CapInh`,`CapPrm`,`CapEff`,`CapBnd`,`CapAmb`,`NoNewPrivs`,`Seccomp`; a key absent because its line lies beyond a captured (possibly truncated) region → assertion **INCONCLUSIVE** (recorded finding), never PASS. `uid_map`/`gid_map` — whitespace-separated triple per line; expected content for `--uid 10001`: `10001 10001 1` (recorded; outer-mapping detail is observational). `mountinfo` — newline-anchored; assertions locate the `/` (expect `ro` after `--remount-ro /`) and `/work` (expect `rw`) entries within the captured prefix; truncation flag set + target line missing → INCONCLUSIVE. Env-names — `\n`-separated `strcspn("=")` names; expected exactly `PATH, COB_LIBRARY_PATH, COB_RUNTIME_CONFIG, COB_PHYSICAL_CANCEL, LC_ALL, TMPDIR, PWD` (7, `aux_u32=7`). Unused probe slots = `rc=-2, err=0`. Supervisor records raw header+payload bytes (hex) plus decoded fields in `redteam_matrix.jsonl`; worker/`cobc` warnings (if any) are archived findings per §2.1.5.

### §5.2 Startup evidence
`INIT_ACK` v1.1 carries `actual_sha256`, `workdir_uid/gid/mode`, `tmpdir_ok`, `exec_sh_ok`, `seccomp_mode` (0 off; 2 = `SECCOMP_MODE_FILTER` verified via `/proc/self/status`).

### §5.3 Exp-4 matrix (seccomp-off controls **and** on-mode, all probes)

| Probe | Flag | EVILMOD input | seccomp=**off** expected (control — proves reachability/baseline) | seccomp=**on** expected |
|---|---|---|---|---|
| **4B** L1/L2 | on | supervisor flips 1 staged byte **before** `CMD_INIT` | n/a (hash check is seccomp-independent; may also be run off) | `INIT_ACK(-2)`, `actual≠expected`, EOF, exit 12; L2 additionally kernel-sealed post-copy |
| **4C** | off→on | ('C',0) | `rc[0]=0` (socket reachable in netns); `rc[1]=-1`, `err[1]` recorded (expected `EINPROGRESS(115)`; assert `rc` only) | SIGSYS at `socket()`: no header, EOF on FD 4, `decoded=31`, bwrap exit **159** |
| **4D-0/2** | off & on | ('I',0) | identical in both modes (proc reads & stat/open are allowed syscalls): `eof_flags bit0..2 set`, `open_fail_flags==0`, `Uid/Gid` lines = `10001`, caps lines present & parsed, `NoNewPrivs: 1`, `Seccomp: 0` (off) / `2` (on); `rc[0]=0`, `aux_u32&07777==0600`, `rc[1]=-1 err[1]=13` | same, with `Seccomp: 2` |
| **4D-1** | off & on | ('D',0) | `rc[0]=-1 err[0]=ENOENT(2)` (sentinel provably exists on host); `aux_u32=7`; names list = the 7 documented vars; `eof bit3` | identical |
| **4E-0** | off & on | ('E',0) | `rc[0..2]=-1 err=EROFS(30)` (`/ro_probe`,`/usr`,`/stage`); `rc[3]=0 err=0` (`$TMPDIR/ok`); mountinfo shows `ro` on `/`, `rw` on `/work`; `eof bit4` or INCONCLUSIVE rule | identical |
| **4F-1 fork** | off→on | ('F',1) | header: `rc[1]=0` (sh present), `rc[0]=0` — **fork reachable** | SIGSYS before header; exit 159; `decoded=31` |
| **4F-2 vfork** | off→on | ('F',2) | `rc[0]=0` | SIGSYS; 159 |
| **4F-3 clone** | off→on | ('F',3) | `rc[0]=0` | SIGSYS; 159 |
| **4F-4 clone3** | off→on | ('F',4) | `rc[0]=0` (kernel ≥ 6.1 ⊃ 5.3) | SIGSYS; 159 |
| **4F-5 execve** | off→on | ('F',5) | process replaced by `/bin/sh` (FDs 3/4 CLOEXEC-closed; stdin EOF) → **no header**, bwrap exit 0; if sh absent: header `rc[0]=-1 err=ENOENT` — both outcomes specified | SIGSYS before exec; 159 |
| **4F-6 execveat** | off→on | ('F',6) | same as 4F-5 | SIGSYS; 159 |
| **4F-7 ptrace** | off→on | ('F',7) | `rc[0]=0` (TRACEME against parent permitted; Yama recorded) | SIGSYS; 159 |
| **4F-8 unshare** | off→on | ('F',8) | **expected failure by sandbox policy** (`--disable-userns`): `rc[0]=-1`, errno recorded (EPERM/ENOSYS expected, value observational). Explicitly **not** a seccomp effect — proves the sandbox independently denies nested userns | SIGSYS; 159 |
| **4G-1** | **off** | ('L',1) fork 4 + spin | runs to 1.0 s timeout → `cgroup.kill` + `killpg(SIGKILL)` → `os_term_signal=9` (bwrap 137), `cgroup.procs` empty, staging dir removed | n/a |
| **4G-2** | **on** | ('L',0) spin-only | n/a | full 1.0 s ± 0.15 s under active filter → timeout kill (137), clean reap |
| **4G-3** | **on** | ('L',1) fork attempt | n/a | immediate SIGSYS (<200 ms), exit 159, `cgroup.procs` empty |

Pairwise rule: a "blocked by seccomp" claim for probe X is valid **only** when the off-mode control for X demonstrates the syscall was reachable (header `rc[0]=0` or process-replacement evidence) **and** the on-mode run shows the SIGSYS signature. 4F-8 is exempted from seccomp-block claims by design (documented above).

---

## §6 — Complete Seccomp Policy Specification (implementable form)

**Implementation:** worker links `libseccomp` (`libseccomp-dev 2.6.0-2`); `bwrap --seccomp FD` is **not** used (one bwrap profile serves both worker modes).

**Architecture & resolution:** `seccomp_init()` → verify `seccomp_arch_exist(ctx, SCMP_ARCH_X86_64) == 0` (native); **do not** add other arches; `seccomp_attr_set(ctx, SCMP_FLTATR_ACT_BADARCH, SCMP_ACT_KILL_PROCESS)` — any non-x86_64 token (incl. `SCMP_ARCH_X32` ABI syscalls) is killed, closing the x32 bypass. `seccomp_attr_set(ctx, SCMP_FLTATR_CTL_NNP, 1)`. Require `seccomp_api_get() >= 3` (API level 3 is the documented minimum for `SCMP_ACT_KILL_PROCESS`, verified in `seccomp.h.in`); below 3 → fail-closed (`INIT_ACK(-4)`, `_exit(16)`).

**Default actions:** Stage-1 and Stage-2 both use default `SCMP_ACT_ALLOW` (0x7fff0000) — a default-deny allowlist cannot be justified before the Exp-4A strace census; tightness comes from the deny rules below. All deny rules use `SCMP_ACT_KILL_PROCESS` (0x80000000U).

**Rule installation:** every syscall added **by name** via `seccomp_syscall_resolve_name()`; return `< 0` (`__NR_SCMP_ERROR` = −1, or `__NR_SCMP_UNDEF` = −2 for kernel-absent names) → **fail-closed** (`INIT_ACK(-4)`, `_exit(16)`) — an unresolvable name is a finding, never skipped. Rules added via `seccomp_rule_add_array`; any non-zero return → fail-closed. `seccomp_load() != 0` → fail-closed. Post-load: parse `/proc/self/status` and require `Seccomp: 2` before `INIT_ACK(0)`.

**Argument comparisons (exact):** `mmap`, `mprotect`, `pkey_mprotect` deny-when-executable:
`SCMP_CMP(2 /* arg index: prot */, SCMP_CMP_MASKED_EQ /* op 7 */, 0x4 /* mask = PROT_EXEC */, 0x4 /* value */)`
i.e. `struct scmp_arg_cmp{.arg=2,.op=SCMP_CMP_MASKED_EQ,.datum_a=PROT_EXEC,.datum_b=PROT_EXEC}` — matches any prot with the executable bit set regardless of other bits (RWX and RX both killed; two-step RW→RX also killed).

**Stage-1 rule set (loaded before `cob_init`/`dlopen`; protects `.init_array` constructors):**
- Process/namespace/privilege: `fork, vfork, clone, clone3, execve, execveat, ptrace, process_vm_readv, process_vm_writev, kcmp, unshare, setns, setuid, setreuid, setresuid, setgid, setregid, setresgid, setfsuid, setfsgid, setgroups`
- Network (exact names, no wildcards): `socket, socketpair, connect, bind, listen, accept, accept4, sendto, sendmsg, sendmmsg, recvfrom, recvmsg, recvmmsg, shutdown, getsockopt, setsockopt`
- Mount/kernel/pcap/module: `mount, umount2, pivot_root, chroot, bpf, perf_event_open, userfaultfd, open_by_handle_at, name_to_handle_at, init_module, finit_module, delete_module, kexec_load, kexec_file_load, reboot, swapon, swapoff, keyctl, add_key, request_key, uselib, io_uring_setup, io_uring_enter, io_uring_register`
- Deliberately **allowed** in Stage-1: `memfd_create`, `mmap`, `mprotect`, `openat`, `close`, `read`, `write`, `munmap` (needed for `libcob`/`libgmp`/target `.so` loading incl. the L2 memfd path).

**Stage-2 rule set (loaded after module resolution, before `INIT_ACK`/`CMD_CALL`; additive):**
- `memfd_create` (kills new W+X anonymous executable creation)
- `mmap` with the PROT_EXEC masked rule
- `mprotect` with the PROT_EXEC masked rule
- `pkey_mprotect` with the PROT_EXEC masked rule (prot is likewise arg 2)
- Everything in Stage-1 remains in force (filters stack; `seccomp_load` of a second filter composes with the first — most restrictive action wins).

**Two-stage lifecycle:** SIGPIPE ignore → FD audit → `$TMPDIR` init → `CMD_INIT` + canonical binding check → *(on)* Stage-1 load + `Seccomp: 2` verify → `cob_init` + hash + `cob_resolve`/sealed-memfd `dlopen`/`dlsym` → *(on)* Stage-2 load + `Seccomp: 2` re-verify → `INIT_ACK(init_status=0, seccomp_mode=2)` → call loop. Any failure at any starred step → `INIT_ACK(-4)` + `close(4)` + `_exit(16)`; the worker never enters the call loop.

**Unavailable-syscall / failed-rule behavior:** summary table — name unresolvable → fatal; `seccomp_rule_add*` ≠ 0 → fatal; `seccomp_load` ≠ 0 → fatal; `Seccomp:` read fails or ≠ 2 → fatal; API < 3 → fatal. In every case: `INIT_ACK(init_status=-4, err="SECCOMP_LOAD_FAILED: <detail>")`, supervisor marks the run `FAILED_SANDBOX_INIT`, no module code has executed beyond the loader window for Stage-2 failures (Stage-1 failure occurs pre-`cob_init`, before any untrusted byte runs).

---

## §7 — Full Experiment Procedures (restores missing procedures; §5.3 superseded by this section + §5.1)

Every experiment: **Inputs → Procedure → Expected → Failure conditions → Evidence.** All pass criteria are against recorded evidence only.

### §7.0 Env-0
- **Inputs:** base image ref; snapshot URLs; 8-wheel set (§2.1.3); fixture sources §3.
- **Procedure:** §2.1.2–2.1.4 in order; build image twice (≥ 2 s apart); Tier R1/R2 hashes; capture BuildKit versions.
- **Expected:** baseline versions match §2.1.2(3) exactly; 8/8 wheels install with `--require-hashes`; `pip check` clean; Tier R1 identical hashes; captured digests == `pip hash` output; zero `cobc` warnings on fixture smoke compile.
- **Failure:** any version drift, hash mismatch, R1 mismatch, warning, or placeholder digest → Env-0 FAIL.
- **Evidence:** `env0/{image_digest.txt, dpkg_manifest.txt, requirements-spike.lock, buildkit_versions.txt, host_sysctls.txt, r1_text.sha256, r2_elf.sha256, r3_oci.txt}`.

### §7.1 Exp-1 — Arithmetic oracle
- **Inputs:** fixtures #1–#5 (compiled `cobc -m -fformat=fixed -Wcolumn-overflow -Wall -std=ibm -O0`), vectors V1–V5 (§2.5 exact input bytes as little files), `exp1_oneshot.c` driver (host-side, no sandbox).
- **Procedure:** `exp1_oneshot <mod.so> <PROGRAM-ID> <input.bin> <out.bin>` — `cob_init`, `cob_resolve`, build `void *cob_argv[1]` pointing at the input record buffer (valid `void *argv[]`, never `&buf` scalars), `cob_call`, dump the record buffer byte-exact to `out.bin`; each vector run ≥ 3× (determinism); trace each result to generated C (`-C`) and libcob source lines.
- **Expected:** V1/V2/V6/V7 outputs match **[D]** values byte-for-byte; V3/V4 recorded with H1/H3/H4 disposition (mismatch ≠ failure — *unexplained* mismatch = failure).
- **Failure:** any [D] mismatch; nondeterminism across 3 runs; unexplained byte in any record; any `cobc` warning (§2.1.5).
- **Evidence:** `exp1/{results.jsonl (vector→bytes→explanation), EX*.lst, EX*.gen.c, out/*.bin}`.

### §7.2 Exp-2 — Worker, IPC, and error categories (no sandbox)
- **Inputs:** fixtures #6, #8, #13 (cobc-compiled directly), #14+#19 (`-K crash_now`), #20 EVILMOD; supervisor + workers per §2.3.
- **Procedure (2G first):** spawn worker (seccomp off), handshake `CMD_INIT/INIT_ACK`; malformed-frame battery: truncated envelope, oversized `payload_len`, bad magic/version, unknown opcode, short payload, trailing bytes, premature EOF, `CMD_CALL` with `argc=17`, `len_i=16385`, `Σ>32768` — each must yield `FAILED_PROTOCOL` + kill + clean recycle; SIGPIPE battery: close FD 4 mid-`CALL_ACK` → supervisor survives via `BrokenPipeError`, worker hits `ERR_EPIPE` → `_exit(10)`. Then: **2A** T2MULTI basic call byte-parity (V6); **2B/C** PID recycle ×2; **2D** T2STOP → `CAT_STOP_RUN(1)`, `cobol_exit_code=42`, tainted, `_exit(10)`; **2E** T2BADBCD (6 B garbage `FF FF FF FF FF FF`) → `cob_call_ret=-1`, `CAT_RUNTIME_ERROR(2)`, err text ≤ 1024 B captured verbatim; **2F-L1** T2CRASH → H6 outcome recorded (either `-2/-3` category with tainted, or SIGSEGV death decoded 139) + worker recycled; **2F-L2** EVILMOD via sealed-memfd L2, plus `4B`-style pre-init byte flip → `INIT_ACK(-2)`, exit 12; canonical-binding battery: `path ≠ /stage/<name>.so` in both loaders → `INIT_ACK(-1)`, exit 14, zero file opens (verified by strace in the profiling image only).
- **Expected:** as stated per sub-test; all five categories observed across 2A/2D/2E/2F without collapsing.
- **Failure:** any category collapse (e.g. STOP RUN reported as runtime error), any protocol-battery acceptance, un-recycled PID, un-captured error text, T2CRASH claim stated without its H6 disposition.
- **Evidence:** `exp2/{handshake_2g.json, protocol_faults.jsonl, results.jsonl, worker_logs/*.log, staging_manifests/*.json}`.

### §7.3 Exp-3 — Parser, state, differential
- **Inputs:** all 18 COBOL fixtures; Lark grammar §2.2; oracle §2.4; vectors V1–V7; Hypothesis (locked §2.1.3).
- **Procedure:** (3A) Lark `LALR(1)` build must complete with **zero conflicts**; unit battery asserting each rejection tuple: #15→`(Preflight, ERR_COL73_OVERFLOW, 4, 73)`, #16→`(Preflight, ERR_INVALID_INDICATOR, 6, 7)`, #13/#14/#18→`(Grammar, …)`, #17→`(AST, ERR_PIC_DIGIT_LIMIT, …)`, plus symbol-resolution units (`ERR_DUPLICATE_SYMBOL`, `ERR_UNDECLARED_IDENT`, `ERR_NON_ELEMENTARY_TARGET`) and the `RETURN-CODE` reserved-token unit; (3B) T3STATE ×10,000 calls in one worker (no cancel) → sticky accumulation recorded; (3C) T3INIT ×10,000 (`IS INITIAL`) → per-call re-init recorded; T3STATE with `cob_cancel` between calls → reset recorded (H5 dispositions); (3D) T3STICKY omitted-`USING` probes under `-fec=bound -d` (H7 outcome recorded, supervisor survives either branch); VmRSS sampled every 500 calls, Δ < 2 MiB over 10k; (3E) differential: ≥ 1,000 Hypothesis-generated vectors per positive fixture, byte-exact oracle parity, 64 pre-built boundary vectors (0, ±max, scale edges, V99 edges); 5 mutants of the oracle (M1 round-half-down; M2 truncate-instead-of-round; M3 sign-nibble C↔D swap on decode; M4 V-scale off-by-one; M5 separate-sign position swap) each proven detected on the corpus within ≤ 1.5 s per 1k calls.
- **Expected:** 18/18 tuples exact; 3B/3C deterministic; 3E 100% parity; 5/5 mutants detected.
- **Failure:** any conflict at grammar build; any misattributed layer; RSS growth; parity gap without an explained H-disposition; any mutant undetected.
- **Evidence:** `exp3/{ast_coverage.json, rejection_tuples.jsonl, results.jsonl, sticky_obs.json, rss.csv, mutants.json}`.

### §7.4 Exp-4 — Sandbox, syscalls, filesystem, timeout, cleanup
- **Inputs:** §4.3 manifest (all host-side staging steps executed per run); workers + EVILMOD; cgroup leaf `/sys/fs/cgroup/necro.slice/spike.scope` (memory/pids/cpu enabled, `PID` written at spawn); profiling image with strace for 4A only.
- **Procedure:** per-run sequence: stage → chmod → sentinel → `INIT_ACK` capture (workdir proof, `exec_sh_ok`, `seccomp_mode`) → matrix §5.3 row by row (off-mode control before on-mode for every 4F/4C row) → per-run teardown: `cgroup.kill=1`, `waitpid` with timeout, `killpg(SIGKILL)` fallback, verify `cgroup.procs` empty, remove staging dir + `$TMPDIR`, record bwrap exit decode. 4A: strace census of a benign full run (categorize: load-window vs steady-state) feeds the Stage-2 review; runtime sandbox never contains strace.
- **Expected:** §5.3 table exactly; every "blocked by seccomp" claim backed by its off-mode control; zero surviving PIDs; zero leftover staging dirs; `INIT_ACK` ownership/`Seccomp` fields per §5.2.
- **Failure:** any missing control run; INCONCLUSIVE treated as PASS; surviving process/dir; a header field contradicting the manifest (e.g. `workdir_uid≠10001`); any seccomp load path exiting ≠ 16 with `-4`.
- **Evidence:** `exp4/{init_ack_*.json, redteam_matrix.jsonl (raw hex + decoded), cgroup_snaps/*.txt, teardown.log, strace.log (4A, profiling image)}`.

---

## §8 — Dependency Graph

```text
[Env-0: digest pin procedure · Debian 20261020T000000Z snapshot · 8-wheel lock (Env-0 artifact) ·
        util-linux 2.41-5 · BuildKit version capture · R1/R2 · warning policy]
        │
        ├───────────────┬──────────────────────────────┐
        ▼               ▼                              ▼
[Exp-1 oracle      [Exp-2 protocol v1.1:      [Exp-4 sandbox: bwrap profile §4.4 ·
 V1–V7 + H1/H3/H4   bounds §2.3.2 · EINTR/EOF · trust boundary enforced by
 dispositions       canonical binding L1/L2 ·   supervisor validation §2.6 ·
 (§2.4/§2.5)]       categories via #8/#13/#14 · EVILMOD v2 §3.3 · seccomp §6 ·
                    sealed-memfd L2 · 4B]       matrix §5.3 w/ off-controls]
        │               │                              │
        └───────┬───────┘                              │
                ▼                                      │
   [Exp-3: 4-layer pipeline · LALR zero-conflict · rejection tuples ·
    state 3B/3C/3D · byte-exact differential 3E · 5 mutants]      │
                └──────────────────┬───────────────────┘
                                   ▼
              [Phase-0 Gate Review — all five gates on recorded evidence]
```

## §9 — Gate Table

| Gate | Status | Blocking | Required evidence | PASS criteria (summary) |
|---|---|---|---|---|
| Env-0 | `NOT EXECUTED` | YES | §7.0 list | §7.0 Expected met verbatim |
| Exp-1 | `NOT EXECUTED` | YES | §7.1 list | [D] vectors byte-exact; H-items explained; deterministic; zero warnings |
| Exp-2 | `NOT EXECUTED` | YES | §7.2 list | protocol battery all rejected; 5 categories preserved; binding enforced; 4B = `-2`/exit 12 |
| Exp-3 | `NOT EXECUTED` | YES | §7.3 list | 18/18 tuples; zero conflicts; parity 100%; 5/5 mutants; RSS Δ<2 MiB |
| Exp-4 | `NOT EXECUTED` | YES | §7.4 list | §5.3 matrix incl. all off-mode controls; clean teardown; no INCONCLUSIVE-as-PASS |

## §10 — Remaining Unresolved Assumptions & Open Items
- **A1** Host permits unprivileged userns (AppArmor `restrict_unprivileged_userns` not blocking) and cgroup delegation to `necro.slice` — recorded, verified at Exp-4 start.
- **A2** TCB: host root does not mutate staged files post-staging (L1 residual; L2 seal removes it in-sandbox).
- **A3** `snapshot.debian.org` serves the `20261020T000000Z` timestamps within retry budget.
- **Q1** exact `libc6-dev` `deb13uN` at the snapshot (resolved & recorded at Env-0).
- **Q2** `cobc 3.2-3` `COB_BLD_DATE`/`.rodata` determinism (Tier R2, observational).
- **Q3–Q7** = hypotheses H1, H3–H7 (§2.5) — resolved by Exp-1/Exp-3 recordings, never pre-asserted.
- **Q8** Stage-2 steady-state syscall census (Exp-4A) — may justify further Stage-2 tightening; any benign-path SIGSYS under Stage-2 is a recorded finding, not silently patched.
- **Q9** 4F-8 off-mode errno value (EPERM vs ENOSYS under `--disable-userns`) — observational.

## §11 — Cross-Reference & Arithmetic Consistency Audit
- **Section map:** every reference in this document resolves: §2.4/§2.5 defined here; §5.3 defined (§5.1–§5.3) and procedures in §7.4; §7 supersedes Rev 4's phantom §5.3; fixture ids #1–#20 used consistently with §3; test ids 2A–2G, 4B–4G defined in §7.2/§7.4/§5.3. Rev 4's absent sections are the *only* dangling references, and they are now defined.
- **Byte-length table (COMP-3, bytes = ⌈(digits+1)/2⌉):** S9(5)V99=4; SV999=2; S9(3)V99=3; SV99=2; S9(4)V9=3; S9(3)=2; S9(5)=3; PIC 9=1; S9(10)V9(9)=10 (rejected at AST). Records: EX1FEE 4+2+4=10 ✓; EX2RND 3+2+3=8 ✓; EX3DIVA 2+2+3+4=11 ✓; EX3DIVB 12 ✓; EX4UNSG 4+4+3+3+3+1=18 ✓; T2BADBCD 3+3=6 ✓; T3STATE/T3INIT 3+3+3=9 ✓; T3STICKY 6 ✓; T3DISP 7+6+6=19 ✓.
- **EVILMOD buffer:** 128+4096+512+512+2048+9088 = 16384 ✓ (regions contiguous, last ends exactly at capacity).
- **IPC bounds:** CMD_CALL 4+64+32768=32836; CALL_ACK 16+64+1024+32768=33872; INIT_ACK 51+1024=1075; frames = payload+8 → 32844/33880 ✓ (all ≤ `MAX_WIRE_FRAME_BYTES=33880`).
- **Exit decodings:** 128+9=137, 128+11=139, 128+31=159 ✓; worker `_exit` codes 10/12/13/14/15/16 all ≤ 20 (no collision with `128+sig` range) ✓.
- **Errno pins:** EACCES=13, ENOENT=2, EROFS=30, EINPROGRESS=115 (recorded; only rc asserted for the last).
- **Env count:** 6 explicit + PWD = 7 ✓. **Lock:** 8 distributions = 3 direct + 1 (hypothesis→sortedcontainers) + 4 (pytest) ✓.

## §12 — Engineering Estimate

| Workstream | Planned | Contingency | Subtotal |
|---|---|---|---|
| 0. VM/cgroup/BuildKit prep | 2.5–3.5 h | +1.5 h | 4.0–5.0 h |
| 1. Env-0 pinning, lock generation, R1/R2 | 3.0–4.0 h | +1.5 h (snapshot throttle, digest reconciliation) | 4.5–5.5 h |
| 2. Exp-1 oracle & vectors | 2.5–3.5 h | +1.0 h | 3.5–4.5 h |
| 3. Exp-2 protocol/bounds/categories/L2 | 7.0–8.5 h | +2.0 h | 9.0–10.5 h |
| 4. Exp-3 parser/state/differential/mutants | 7.0–9.0 h | +2.0 h | 9.0–11.0 h |
| 5. Exp-4 sandbox, seccomp, matrix, cleanup | 7.5–9.0 h | +2.5 h (control pairing, teardown races) | 10.0–11.5 h |
| **Total** | **29.5–37.5 h** | **+10.5 h** | **40.0–48.0 h (~5–6 focused days)** |

---

## §13 — Readiness Decision

**Decision: `READY FOR LIMITED EXECUTION`**

All eight audit directions are resolved at specification level: missing sections restored (§2.4, §2.5, §5.1–§5.3, §7); the sandbox filesystem is fully manifested with a genuine, mechanically-staged DAC probe and a meaningful `/tmp` isolation proof with host sentinel; the seccomp policy is implementable (exact names, arch/badarch, API level, argument encodings, fail-closed behavior, off-mode controls for all eight Mode-F probes); EVILMOD v2 fixes the `gid_map` defect, separates EOF from truncation, records open/read failures, and is paired with a warnings-as-findings policy; the IPC trust boundary is stated honestly (module adversarial; framing ≠ authenticity; supervisor treats all frames as untrusted; claim set enumerated); reproducibility distinguishes `SPECIFIED` from `CAPTURED` with a concrete pinning procedure and a classified Env-0 lock artifact (exact versions/filenames plus captured reference digests, re-verified by `pip hash`); the seven vectors carry exact input bytes with [D]/[Hn]-labeled expectations and no invented compiler outputs; and all bounds are re-derived with the arithmetic shown (§11). Remaining unknowns are explicitly enumerated (A1–A3, Q1–Q9, H1–H7) and are precisely what the bounded spike is designed to measure.

Authorization, if granted, applies strictly to executing `Env-0` and `Exp-1`–`Exp-4` under §7. Until evidence is collected and independently reviewed, every gate remains `NOT EXECUTED`, and this decision is a statement about specification readiness only — not about any gate outcome.

`NOT EXECUTED — zero code written, zero files created, zero containers built, zero experiments run, zero results claimed.`
