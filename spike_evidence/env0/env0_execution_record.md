# Env-0 Execution Record (append-only)

Execution ID: ENV0-1 · Date: 2026-11-04 · Branch: `arena/c6d3bcf5-kiroween` · Starting commit: `d0c609493a55b9164bd6f4f6c62b5bd52ca70559`
Controlling references: Rev5 §2.1 (as carried through the Rev6 chain) and `spec/REV642_NORMATIVE_INDEX.md`; P0 closure: `p0_channel_b_attestation.json` (`P0 PASS — CHANNEL B USER-ATTESTED BASELINE ACCEPTED` / `CHANNEL A FAILED — ORIGINAL SOURCE PROVENANCE INCOMPLETE`).

## 1. Authorization and scope

Owner authorization (2026-11-04, directive "NecroSpec — Env-0 Technical Execution Authorization"): `YES I AUTHORIZE` — **Env-0 only**. Scope executed: environment inventory, capability probes, Python dependency lock (Rev5 §2.1.3), prerequisite checks. **Not executed (boundary):** Exp-1, Exp-2/2A, Exp-3, Exp-4; no worker/supervisor implementation; no COBOL/Python fixtures compiled beyond the two Env-0 capability probes; no parity, FFI, parser, or sandbox-security claims of any kind.

## 2. Environment identity (actual, verified — nothing assumed)

| Property | Actual value | Rev5 §2.1 pin / expectation | Status |
|---|---|---|---|
| OS | Debian GNU/Linux 12 **bookworm** (container, host `e2b.local`) | Debian **trixie** image `python:3.12-slim-trixie` (pinned digest) | DEVIATION D-2 |
| Kernel | `Linux 6.1.158+ x86_64` | kernel ≥ 6.1 | **MEETS** pin |
| Arch | x86_64 | x86_64 | MEETS |
| CPU / RAM / disk | 2 × Xeon @2.60 GHz / 3939 MiB / 20 GiB free | resource-conscious execution | OK |
| Identity | uid 1001(user), sudo → root available | — | recorded |
| gcc | 12.2.0-14+deb12u1 | gcc 14.2.0-1 (trixie) | DEVIATION D-3 |
| Python | 3.11.2 (pip 23.0.1) | CPython 3.12 target | DEVIATION D-1 |
| cobc / cobcrun (GnuCOBOL) | **ABSENT** | gnucobol3=3.2-3, libcob4t64=3.2-3 | **BLOCKER B-1** |
| bubblewrap | **ABSENT** | bubblewrap=0.12.0-1~deb13u1 | **BLOCKER B-2** |
| libseccomp | runtime lib 2.5.4 present; **dev headers ABSENT** | libseccomp2/-dev=2.6.0-2 | **BLOCKER B-3** + deviation |
| util-linux (setpriv/unshare/prlimit/nsenter) | 2.38.1 | 2.41-5 | DEVIATION D-4 |
| docker / buildkit | **ABSENT** | required by §2.1.2 image pinning + §2.1.6 R3 | **BLOCKER B-4** |
| strace | ABSENT | §2.1.2.5 requires absence in runtime image | consistent (profiling image out of scope) |
| libc6 / glibc headers | 2.36-9+deb12u14; multiarch headers present | Q1 (libc revision resolved at install) | DEVIATION D-5 (bookworm rev) |

## 3. Capability check results (executed)

| Check | Method (exact) | Result |
|---|---|---|
| Unprivileged user namespace | `unshare -Ur true` | **PASS** (exit 0) |
| Full namespace set (user/mnt/net/pid/ipc + mount inside) | `unshare -Urmnfp --map-root-user sh -c '…mount -t tmpfs…'` | **PASS** (exit 0; pid=1 inside; tmpfs mount OK) — the bwrap-core primitive set is operational even though the bwrap binary is absent |
| seccomp filter (`CONFIG_SECCOMP_FILTER`) | compiled probe `probes/probe_seccomp.c` (NNP + raw cBPF: arch check, getpid→EPERM, default ALLOW), `-O2 -Wall -Wextra -Werror`, 3 runs | **PASS 3/3** — `PROBE-OK seccomp_mode=2 filters=1 getpid_blocked=yes(EPERM)`; `actions_avail` includes kill_process/kill_thread |
| SysV shared memory | compiled probe `probes/probe_shm.c` (shmget IPC_PRIVATE → shmat → write/read → shmdt → IPC_RMID) | **PASS** (2/2, exit 0) — prerequisite for the Rev6.4 §5 4H-5/4H-6 contract |
| cgroup v2 | `stat -fc %T` → `cgroup2fs`; controllers `cpuset cpu io memory hugetlb pids`; `sudo mkdir /sys/fs/cgroup/necro.probe` | **PASS** (writable as root; delegation boundary recorded: non-root mkdir denied, root succeeds; `nsdelegate,memory_recursiveprot` mount options recorded) |
| sysctls (A1) | recorded verbatim in `host_sysctls.txt` | **RECORDED** (yama/apparmor keys absent from this kernel — noted) |
| Python venv | `python3 -m venv /tmp/env0venv` | **PASS** (ensurepip 23.0.1) |

Probe bring-up findings preserved as evidence (§2.1.5 warnings-are-findings): the first `probe_seccomp.c` draft failed `-Werror` (missing `<stddef.h>`; macro partial initializers) and then failed filter load with EINVAL (agent BPF jump-offset off-by-one); both fixed in source; final sources compile warning-free and run. Raw log: `probes/probe_outputs.txt`.

## 4. Python dependency lock (Rev5 §2.1.3) — EXECUTED END-TO-END, WITH FINDING

Procedure executed exactly as pinned (system python 3.11.2 in place of the 3.12 target — D-1):

1. `python3 -m pip download --dest /wheels --only-binary=:all: --no-deps lark==1.3.1 hypothesis==6.170.14 sortedcontainers==2.4.0 pytest==9.2.0 iniconfig==2.3.1 packaging==26.3 pluggy==1.7.0 Pygments==2.21.0` → 8 wheels saved (sdist exclusion honored).
2. `python3 -m pip hash /wheels/*.whl` → digests captured; mechanical comparison against the reference digests **parsed from the published `spec/rev5.md` §2.1.3** (not from session memory):

| Distribution | Version | Wheel obtained | vs Rev5 reference | Actual SHA-256 |
|---|---|---|---|---|
| lark | 1.3.1 | `lark-1.3.1-py3-none-any.whl` | **MATCH** | `c629b661023a014c37da873b4ff58a817398d12635d3bbb2c5a03be7fe5d1e12` |
| sortedcontainers | 2.4.0 | `sortedcontainers-2.4.0-py2.py3-none-any.whl` | **MATCH** | `a163dcaede0f1c021485e957a39245190e74249897e2ae4b2aa38595db237ee0` |
| pygments | 2.21.0 | `pygments-2.21.0-py3-none-any.whl` | **MATCH** | `2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377137d9` |
| iniconfig | 2.3.1 | `iniconfig-2.3.1-py3-none-any.whl` | **MISMATCH** | `9121e2c1fdb355232495be3194c8dfe87ccc2d5dee45947b78e68f499790d7a7` (ref `47c2c35d…`) |
| packaging | 26.3 | `packaging-26.3-py3-none-any.whl` | **MISMATCH** | `d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c` (ref `70fdb89f…`) |
| pluggy | 1.7.0 | `pluggy-1.7.0-py3-none-any.whl` | **MISMATCH** | `7dd7b0d8832ba3cb632c306926ded123429211b83641b35dc5c41ad2d34f9bec` (ref `20ac8237…`) |
| pytest | 9.2.0 | `pytest-9.2.0-py3-none-any.whl` | **MISMATCH** | `07acdcf88ec174f907dc01af70bf52d49b014bbab03faeeade31c96b18c2e588` (ref `006823d1…`) |
| hypothesis | 6.170.14 | `hypothesis-6.170.14-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.whl` | **CAPTURED** (Class 2, F-12) | `3bf836cb28f07201e0fe7d3cf2ebe1b5f540ab798fd03edb174d98f064bd620a` |

**FINDING E0-F1 (supply-chain / reference-digest defect — abort condition per §2.1.3):** 4 of 7 predeclared reference digests do not match the actual PyPI artifacts. PyPI wheel artifacts are immutable, so the mismatch indicates the Rev5 §2.1.3 reference values for iniconfig/packaging/pluggy/pytest were themselves incorrect (never byte-verified) rather than upstream mutation. The pytest result additionally resolves the historical pytest digest conflict (recorded since pre-Rev-5) **against** the Rev5 reference: the actual artifact hash `07acdcf88ec174f…` ends with the pre-Rev-5-recorded fragment `88ec174f…` (which was historically transcribed without its leading characters). Per §2.1.3 ("any mismatch aborts Env-0 as a supply-chain finding") this is recorded as an abort-level finding for the lock's reference-match requirement. **No specification revision was made in this pass** (per directive §5); resolution requires a maintainer decision via a superseding record: either adopt the verified actual digests (retained here: `wheels/` + `WHEELS_SHA256SUMS` + `requirements-spike.lock`) or re-pin with evidence.

3. `requirements-spike.lock` written with the **actual** verified digests (8/8 hashed; Class-2 hypothesis entry captured per F-12).
4. `/tmp/env0venv/bin/pip install --no-index --find-links=/wheels --no-deps --require-hashes -r spike_evidence/env0/requirements-spike.lock` → **Successfully installed** all 8.
5. `pip check` → **No broken requirements found.**
6. Version smoke: lark 1.3.1, hypothesis 6.170.14, pytest 9.2.0, packaging 26.3, pluggy 1.7.0, pygments 2.21.0, iniconfig 2.3.1, sortedcontainers 2.4.0 — all imported and reported.

## 5. Blockers (mandatory §2.1.2 procedure cannot execute here)

| ID | Blocker | Evidence |
|---|---|---|
| B-1 | GnuCOBOL toolchain (`cobc`, `cobcrun`, libcob) absent; unobtainable | `command -v cobc` ABSENT; `sudo apt-get update` → `Connection failed [IP: 151.101.66.132 80]` for deb.debian.org/debian{,-security} (outbound network to Debian mirrors blocked in this environment; only PyPI/GitHub/npm reachable). No trixie snapshot access ⇒ pinned `gnucobol3=3.2-3` install impossible. |
| B-2 | bubblewrap absent; unobtainable (same network block; no Debian mirror) | `command -v bwrap` ABSENT; apt evidence above. (Underlying namespace primitives verified operational — §3.) |
| B-3 | libseccomp-dev headers absent (runtime lib 2.5.4 only, ≠ pin 2.6.0-2); unobtainable | `/usr/include/seccomp.h` ABSENT; `/usr/lib/x86_64-linux-gnu/libseccomp.so` ABSENT (only `.so.2.5.4`); apt evidence above. Capability itself proven via raw-cBPF probe. |
| B-4 | Docker/BuildKit absent ⇒ §2.1.2 image-digest pinning (`image_digest.txt`) and §2.1.6 R3 artifacts (`buildkit_versions.txt`) cannot be produced | `command -v docker` ABSENT. Per §2.1.4 the environment therefore cannot become `CAPTURED` for those elements; no placeholder files were created (placeholders are forbidden by §2.1.2). |
| B-5 | CPython 3.12 target unobtainable (no python.org access; bookworm ships 3.11.2) | `python3 --version` → 3.11.2. Lock executed on 3.11.2 (closure identical: exceptiongroup/tomli excluded on ≥3.11 exactly as §2.1.3 states). Hypothesis wheel resolved to `cp311-cp311` (spec anticipated cp312/abi3 — recorded). |
| B-6 | Tier R1 (`.text` reproducibility across two clean builds) requires `cobc` | B-1 ⇒ R1/R2 not executable; R3 requires docker (B-4). |

## 6. Deviations register (recorded, never silently accepted)

D-1 Python 3.11.2 vs pinned 3.12 target · D-2 Debian bookworm container vs trixie image pin · D-3 gcc 12.2.0 vs 14.2.0-1 · D-4 util-linux 2.38.1 vs 2.41-5 · D-5 libc6 2.36-9+deb12u14 vs trixie deb13uN (Q1 unresolved in this environment) · D-6 hypothesis wheel tag `cp311-cp311` vs anticipated `cp312`/`abi3` · D-7 no dedicated VM (sandbox container; owner-authorized environment).

## 7. Status summary and disposition

| Category | Result |
|---|---|
| Environment inventory + sysctls (A1) | **PASSED / RECORDED** |
| Namespace + seccomp + shm + cgroup capability checks | **PASSED** (6/6 executed checks) |
| Python lock §2.1.3 (download/hash/lock/install/check/smoke) | **EXECUTED END-TO-END**, mechanics PASS; **FINDING E0-F1** (4 reference-digest mismatches — abort-level per §2.1.3) |
| Debian snapshot toolchain install (gnucobol3, libcob4-dev, bubblewrap, libseccomp-dev, gcc pin) | **BLOCKED** (B-1…B-3) |
| Image pinning / BuildKit records (§2.1.2.1, §2.1.6 R3) | **BLOCKED** (B-4) |
| CPython 3.12 target | **BLOCKED** (B-5) |
| Tier R1 reproducibility | **BLOCKED** (B-6) |

## **ENV-0 DISPOSITION: `BLOCKED — ENVIRONMENT CAPABILITY PARTIAL; MANDATORY TOOLCHAIN UNOBTAINABLE; SUPPLY-CHAIN FINDING E0-F1 OPEN`**

Basis: Env-0 may be declared PASS only if **every** mandatory check executes and passes (§2.1.4 `CAPTURED` set + §2.1.3 reference match + §2.1.6 R1). Executed checks passed (with the E0-F1 abort finding on the lock's reference-match requirement), but the mandatory toolchain/image elements could not execute because this environment has no Debian-mirror or docker access and no GnuCOBOL/bubblewrap/libseccomp-dev/CPython-3.12. No requirement was weakened; no unavailable capability was converted into a pass; failed and skipped checks are preserved above and in `probes/probe_outputs.txt`.

## 8. What Env-0 does and does not authorize

Env-0 completion (if later achieved) authorizes **consideration** of the next experiment — it does not auto-execute Exp-1. In the current BLOCKED state: no experiment is authorized. A future PASS requires: (a) an environment with access to the Debian trixie snapshot (or docker + the pinned image) so B-1…B-4 artifacts can be produced; (b) CPython 3.12 or an owner-accepted superseding pin (D-1/B-5); (c) E0-F1 resolution by the specification maintainer (supersede Rev5 §2.1.3 reference digests with the byte-verified values retained here, or re-pin); (d) re-run of the blocked elements with evidence.

## 9. Execution declaration

`NOT EXECUTED — no application code written or modified, no dependencies installed outside the Env-0 evidence scope (8 pinned wheels acquired and hash-locked per Rev5 §2.1.3), no compilation performed beyond the two Env-0 capability probes, no experiments run, and no deployment performed.`
