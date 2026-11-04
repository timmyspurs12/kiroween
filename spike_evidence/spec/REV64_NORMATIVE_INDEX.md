# REV64 Normative Index — NecroSpec Corpus (Post-Rev6.4)

Layer `spike_evidence/spec/rev64_errata.md` (Rev6.4) + this index. **Consumption order:** Rev4_extract (§2.2.2, §3.1–3.3 by reference) → Rev5 → Rev6 → Rev6.1 → Rev6.2 → Rev6.3 → **Rev6.4**; later layers control on conflict. Statuses: **Normative** (controlling), **Historical** (kept verbatim, not controlling), **Superseded** (replaced by a later layer), **Unverified** (specified, empirically unproven until recorded by an authorized experiment), **Open** (deliberately unresolved decision).

## A. Documents

| Artifact | Status | Note |
|---|---|---|
| `rev4_extract.md` | Historical (extract) | source of fixtures #1–#20 and grammar layers; controlling only via later layers' references |
| `rev5.md` | Normative (base) | Rev6.4 §3/§4/§7 supersede listed statements only |
| `rev6_errata.md` | Normative | E-0…E-7; E-15-correctable occurrences superseded (F-07) |
| `rev61_errata.md` | Normative | E-8…E-11; "#1–#19" range superseded (F-06) |
| `rev62_errata.md` | Normative | E-12/E-13; old-byte lines 73/77 superseded (F-07) |
| `rev63_errata.md` | Normative | E-14…E-16; E-15 citations superseded (F-07); PEC-1 restated (F-x audit) |
| `rev64_errata.md` | Normative (this layer) | F-01…F-13, §6/§7 matrices, §12 P0 |
| `SHA256SUMS`, `preexec_checks.md` | Historical | integrity records + preflight/AST constants (26/24 distinction; PEC-1) |
| `../README.md`, `../PUBLICATION_SHA256SUMS` | Historical | publication index + 11-entry manifest |
| `../env0/spec_manifest.json` / `p0_disposition_amendment.json` | Historical; amendment controls | manifest `P0 PASS` superseded by `ABORTED-P0` |

## B. Topic index (controlling text, historical origin, Rev6.4 action, empirical status)

| Topic | Controlling text | Historical origin | Rev6.4 action | Empirical status |
|---|---|---|---|---|
| VM/environment pins (Debian trixie, gcc 14.2, gnucobol 3.2-3, libseccomp 2.6.0-2, bwrap 0.12.0-1, snapshot 20261020T000000Z, SOURCE_DATE_EPOCH, -frandom-seed) | Rev5 §2 | Rev5 | audit only | Unverified (Env-0) |
| Python lock (8 dists) | Rev5 §2.1.3 **as amended by Rev6.4 F-12** | Rev5 | Class 1/Class 2 split; hypothesis=Class 2 capture | Unverified (Env-0) |
| Grammar layers L1–L6 (preflight, lexer, grammar, AST, semantics, native) | Rev5 §3; Rev4 by reference | Rev4/Rev5 | F-04 semantics table | rejection rules Unverified; tuple expectations H-tagged |
| Preflight/AST constants (26-row audit vs 24 pointer-fixes; PEC-1/PEC-2) | Rev5 §3.4/3.5; preexec_checks.md | Rev6.3/6.2/6.1 | restated, unchanged | Unverified |
| Staging & staging manifest | Rev5 §4.3 **as superseded by Rev6.4 F-05** | Rev5 | canonical 9-step sequence; chmod ≠ mount immutability | Unverified |
| Worker launch profile (prlimit→setpriv→env -i→bwrap, E-1) | Rev5 §4.4 + rev6 E-1 | Rev5/Rev6 | audit only | Unverified |
| Stage-1 seccomp policy + x32 gate (H8) | Rev5 §6 + rev6 E-2 | Rev5/Rev6 | audit only (shmat untouched in Stage-1) | Unverified (4F/4C) |
| Stage-2 seccomp policy | Rev5 §6 **as amended by Rev6.4 F-01** | Rev5 | + shmat SHM_EXEC masked rule | Unverified (4H) |
| Stage-2 exec-mechanism tests | Rev6.4 §3 F-09, §6 (new) | Rev5 §5.3 superseded in scope | 4H-1…4H-6 matrix | Unverified |
| Worker↔supervisor protocol | Rev5 §2.3.2 **as superseded by Rev6.4 §7** | Rev5 | full wire contract, state machine, `_exit(11)` | Unverified |
| `reset_flag` | Rev6.4 §3 F-02 | Rev5 (undefined) | fully defined; reset ≠ proof | Unverified (Exp-3) |
| Exit-code space (worker/bwrap) | Rev5 §11 **as amended** (adds 11) | Rev5 | extended | Unverified |
| EVILMOD v3.1 structure (offsets, modes K/C/I/D/E/F/L) | rev61 E-8 + rev62 E-12 | Rev6.1/6.2 | extended with Modes 'M'/'P' (specified only, §3 F-09/F-10) | Unverified; Mode M/P source not yet materialized |
| Canonical module binding (L1/L2) | Rev5 §2.3.3 **as superseded by Rev6.4 F-08** | Rev5 | single grammar both loaders | Unverified (binding battery) |
| Trust model (adversarial module, R-1, A2) | Rev5 §2.6/§2.6.1 **as operationalized by Rev6.4 F-10** | Rev5/Rev6 | Class A/B; 2H-1…2H-5; forgery unavoidability | Unverified |
| Vector bytes V1–V7 (incl. `06 66 66 6C` primary / `06 66 70 0C` alt) | Rev6.1 E-4, E-10, Rev6.2 E-13, Rev6.3 E-15 (canonical), Rev6.4 F-07 restatement | Rev6–6.3 | refs corrected; old bytes superseded | HYPOTHESIS — NOT EXECUTED |
| Fixture inventory #1–#20 | Rev6.4 §3 F-06 | Rev4; E-0/E-11 ranges superseded | 20-entry ownership table | sources present; behavior Unverified |
| Exp-2 categories & gate | Rev6.4 §3 F-03 | Rev5 §7.2/§9 superseded | honest gate (CAT_OK/STOP_RUN mandatory) | Unverified |
| Exp-3 corpus/replay/state tests | Rev6.4 §3 F-11 | Rev5 §7.3 superseded | boundary64, derandomize, M1–M5, sequences | Unverified; threshold = target only |
| Exp-4 (cgroups, 4A census, off-control-first) | Rev5 §8 | Rev5 | audit only; Q8 open | Unverified |
| Provenance / P0 disposition | env0/p0_disposition_amendment.json; Rev6.4 §12 | P0 + amendment | unchanged, controlling | **`ABORTED-P0 — SOURCE PROVENANCE INCOMPLETE`** |
| Hypotheses | Rev5 §2.5 + E-2 (H8) **+ Rev6.4 (H9)** | Rev5/Rev6 | H9 zero-divide category (recording-only) | all Unverified |
| Open decisions | Rev6.4 §14 | — | Q8; broker option; P0 channel (user); implementation-fidelity | **Open** |

## C. Explicitly superseded statements (never normative, never edit history)

1. Rev5 §4.3 chmod-before-sentinel ordering (F-05).
2. Rev5 §2.3.3 L2 regex `[A-Za-z0-9][A-Za-z0-9_]{0,30}` (F-08).
3. Rev5 §7.2 "all five categories observed" + §9 Exp-2 gate (F-03).
4. Rev6 E-0 / Rev6.1 E-11 "fixtures #1–#19" (F-06) — sole occurrences `rev6_errata.md` §0.1, `rev61_errata.md` line 247.
5. Old division output bytes `06 67 00 0C` at `rev6_errata.md` lines 293/294/379/380 and `rev62_errata.md` lines 73/77; E-15's "Rev 6.1 E-4"/"Rev 6.1 E-13" citations and "corrected" wording (F-07).
6. Rev5 §2.1.3 reference-hash rule applied to Hypothesis (F-12).
7. Any Stage-2 completeness claim omitting `shmat` (F-01); any Stage-2 test claim citing §5.3 alone (F-09).

`NOT EXECUTED — zero code written or modified, no packages installed, no containers built, no compilation performed, no experiments run, no results claimed.`
