# NecroSpec — P0 Specification Evidence Corpus

## 1. What this is

NecroSpec is a proposed COBOL-to-Python differential verification workflow (`NVS-0`). Before any implementation may begin, a bounded **Phase-0 Technical Spike** must be specified, authorized, and executed under evidence gates (`Env-0`, `Exp-1`–`Exp-4`). This directory publishes the **specification corpus** — the controlling specification revision (Rev 5), its errata chain (Rev 6 through Rev 6.3), the Rev 4 dependency extracts it incorporates, and the provenance records produced by the mandatory **P0 dependency-anchoring precondition** — so that independent reviewers can inspect exactly what the specification says and how its provenance stands. **This is an evidence-publication only; it is not a claim of readiness for technical execution.**

## 2. Specification documents and revision coverage

| File | Required source content | Published as |
|---|---|---|
| `spec/rev4_extract.md` | Rev 4 §2.2.2 (lexical rules + Lark LALR(1) grammar) and §§3.1–3.3 (fixtures #1–#20) | Extract (dependency range only) |
| `spec/rev5.md` | Rev 5 §§1–13 (full normative specification) | Full document |
| `spec/rev6_errata.md` | Rev 6 errata E-0 … E-7 (+ deliverables) | Full document |
| `spec/rev61_errata.md` | Rev 6.1 errata E-8 … E-11 (+ deliverables) | Full document |
| `spec/rev62_errata.md` | Rev 6.2 errata E-12 … E-13 (+ deliverables) | Full document |
| `spec/rev63_errata.md` | Rev 6.3 errata E-14 … E-16 (+ matrix/cross-ref/verdict) | Full document |

The extracts are frozen **as-emitted**: later corrections are **not** retro-applied to earlier documents. The supersession chain (recorded in `env0/spec_manifest.json` → `supersession_map`) is the consumption order; e.g. the V3/V4 alternate bytes `06 67 00 0C` visible in the Rev 6/Rev 6.2 tables are superseded by Rev 6.3 E-15 (`06 66 70 0C`). Superseded material is intentionally preserved.

## 3. Provenance classification (per document)

**Every one of the six specification documents is classified: `TRANSCRIPT-DERIVED COPY`.** The original NecroSpec documents exist only as conversation-transcript messages from the authoring session (2026-11-04); no original files or byte-accessible original message streams were available. Each extract is a best-effort verbatim transcription (no paraphrase, no normalization, no reflow), with the transcript as the appeal authority. **They are not original files and no byte-for-byte identity with the inaccessible originals is claimed.** No original-source hashes are recorded anywhere in this corpus, and none may be invented.

Provenance records published alongside:

| File | Content |
|---|---|
| `spec/SHA256SUMS` | Original evidence manifest — SHA-256 of the six extracts (generated mechanically by `sha256sum`). |
| `spec/preexec_checks.md` | Pre-execution protocol-semantics checks PEC-1 (flag-bit→error-slot mapping) and PEC-2 (`read_err[]` semantics). Note: this file resides under `spec/`, not `env0/`, in the working evidence tree; it is published at its actual path. |
| `env0/spec_manifest.json` | Extraction/verification manifest: document identities, section-presence checklists, extraction method and boundary conventions, per-file hashes, supersession map, limitations. |
| `env0/p0_disposition_amendment.json` | Corrected P0 disposition (see §4). Append-only amendment; the earlier manifest's `p0_result` field is superseded by it. |

## 4. Current corrected P0 disposition

```
ABORTED-P0 — SOURCE PROVENANCE INCOMPLETE
```

Issued by `env0/p0_disposition_amendment.json` under the original fail-stop P0 requirements (E-11 §0.4v2 steps 4 and 6): SHA-256 over each **original** document stream was required but could not be computed because the originals were not byte-accessible; the fail-stop condition is therefore met.

## 5. Outstanding provenance limitation

**The original-source provenance requirement remains INCOMPLETE.** Zero original-stream hashes exist; no independent byte-level comparison of originals against the extracts has been performed. Closure requires byte-accessible originals (platform transcript export, or user-attested faithful copies under a recorded, weaker provenance grade) per the closure procedure in `env0/p0_disposition_amendment.json`.

## 6. Superseded claim

A prior `P0 PASS` claim (in `env0/spec_manifest.json` and the session P0 report of 2026-11-04) **was superseded** by the disposition amendment and is withdrawn. `env0/spec_manifest.json` is preserved byte-for-byte for evidence-chain integrity; wherever it conflicts with the amendment, **the amendment controls**.

## 7. Execution status

**Env-0 is blocked** (ABORTED-P0, per E-11 step 6) and **all experimental gates (`Exp-1`, `Exp-2`, `Exp-3`, `Exp-4`) remain `NOT EXECUTED`**. Nothing has been compiled, installed, built, run, or deployed. This corpus does **not** indicate that the project is ready for technical execution.

## 8. Independent verification of the six extract hashes

The original evidence manifest records bare filenames relative to `spike_evidence/spec/`. Verify from that directory:

```bash
cd spike_evidence/spec
sha256sum -c SHA256SUMS
```

Expected: six lines, each `<file>: OK`. At publication time (commit recorded in the branch history) all six verified OK.

## 9. Document integrity vs. original-source provenance

These are **different verifications** and must not be conflated:

- **Document integrity verification — COMPLETED.** The six extracts have internally recorded, mechanically computed, re-verifiable SHA-256 digests (`SHA256SUMS`). Anyone can confirm the published bytes match the recorded digests. This proves only that the *published corpus* is self-consistent and unaltered since hashing.
- **Original-source provenance verification — INCOMPLETE (blocking).** This would require hashing the *original* transcript streams and byte-comparing them to the extracts. It has **not** been performed and cannot be until byte-accessible originals are provided. Until then, fidelity of the transcription rests on best-effort process plus the transcript as appeal authority — not on cryptographic evidence.

## Publication metadata

- Repository: `timmyspurs12/kiroween` — branch: session branch `arena/c6d3bcf5-kiroween` (the session is bound to this branch; the requested name `evidence/p0-specification-corpus` could not be created — see the publication report).
- Publication integrity manifest: `PUBLICATION_SHA256SUMS` (covers every published file including this README; distinct from, and additive to, the original `spec/SHA256SUMS`, which is preserved untouched).
