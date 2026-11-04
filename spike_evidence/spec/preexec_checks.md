# NecroSpec P0 — Pre-Execution Protocol-Semantics Checks (PEC-1, PEC-2)

Recorded per the P0 directive §4. These are **explicit pre-execution checks**: they are registered here and enforced by the supervisor/diagnostic consumers at Exp-2/Exp-4 diagnostic ingestion time. Their registration is a specification-integrity act, not an execution; no experiment has run.

## PEC-1 — `open_fail_flags` bit → error-slot mapping (source: Rev 6.3 E-14; wire source: Rev 6.1 E-8)

Normative mapping (applies identically to `open_err[]` and `read_err[]`):

| Probe | `open_fail_flags` bit | Mapped error slot |
|---|---|---|
| `/proc/self/status` | 0 | `[0]` |
| `/proc/self/uid_map` | 1 | `[1]` |
| `/proc/self/gid_map` | 2 | `[2]` |
| `/proc/self/mountinfo` | 4 | `[3]` |

Consumer rules:
- Mapping function: `slot = (bit == 4) ? 3 : bit`. **Never index an error array directly by an arbitrary flag bit.**
- Unsupported probe-bit values (any bit other than 0, 1, 2, 4 set in `open_fail_flags`) ⇒ reject the record as inconsistent ⇒ finding.
- If a probe's open-failure flag is **clear**, its mapped `open_err` slot must equal `0`.
- If a probe's open-failure flag is **set**, its mapped `open_err` slot must contain the corresponding nonzero errno.
- `open_err[4]` does not exist; the arrays remain four elements; the 128-byte wire layout is unchanged.

Static producer-conformance verification of the **extracted** v3.1 source (`rev61_errata.md`, lines 135–144, 188–189), performed by text inspection on 2026-11-04:

```
135:                        &oerr, &rerr, 0);          -> 136: h->open_err[0] = oerr; h->read_err[0] = rerr;
139:                        &oerr, &rerr, 1);          -> 140: h->open_err[1] = oerr; h->read_err[1] = rerr;
143:                        &oerr, &rerr, 2);          -> 144: h->open_err[2] = oerr; h->read_err[2] = rerr;
188:                        &oerr, &rerr, 4);          -> 189: h->open_err[3] = oerr; h->read_err[3] = rerr;
```

Result: **PEC-1 REGISTERED and producer-verified** (bit→slot pairs {0→0, 1→1, 2→2, 4→3} confirmed in the anchored source text). Enforcement at diagnostic ingestion is an Exp-2/Exp-4 duty.

## PEC-2 — `read_err[]` semantics (source: Rev 6.1 E-8 field contract; Rev 6.2 E-12)

- `read_err[slot] == 0` means **no read syscall error was recorded**; a nonzero value is the captured errno (EINTR-retried reads are not errors; the loop retried per E-8/E-12 helper text).
- There is **no separate read-failure flag**; `read_err[]` is the sole read-error channel.
- If the corresponding open-failure bit is set, the helper returned before any read: `read_err[slot]` must be `0`.
- Initialisation guarantee (E-12, `rev62_errata.md` line 18): `*out_len = 0; *oerr = 0; *rerr = 0;` executes before `open()` on every entry, so stale errnos cannot leak across the reused Mode-'I' locals.

Result: **PEC-2 REGISTERED and init-guarantee text-verified** in the anchored corpus. Runtime confirmation of the guarantees themselves occurs only during Exp-2/Exp-4 (not executed).

— Both checks recorded as pre-execution obligations. No experiment, compile, or probe was run to produce this record.
