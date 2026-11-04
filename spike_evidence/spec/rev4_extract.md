#### 2.2.2 Lexical Rules, Reserved Exclusions & Unambiguous Grammar (`Grammar` Layer — Zero Shift/Reduce Ambiguity):
- **Lexical Tokenization (`cols 8–72` of non-comment lines, case-insensitive keywords):**
  - `LEVEL_NUM`: `^(0[1-9]|[1-4][0-9]|77)$` (note `66` and `88` are lexically excluded from `LEVEL_NUM`).
  - `SIGNED_DEC_LIT`: `^[+-]?([0-9]+(\.[0-9]+)?|\.[0-9]+)$`; `POS_INT`: `^[1-9][0-9]*$`.
  - **`RESERVED_WORDS` (Never tokenized as `USER_IDENT`):** Includes (a) all `NVS-0` grammar keywords (`IDENTIFICATION`, `DIVISION`, `PROGRAM-ID`, `IS`, `INITIAL`, `DATA`, `WORKING-STORAGE`, `LINKAGE`, `SECTION`, `PIC`, `PICTURE`, `USAGE`, `COMP-3`, `PACKED-DECIMAL`, `DISPLAY`, `SIGN`, `LEADING`, `TRAILING`, `SEPARATE`, `CHARACTER`, `VALUE`, `PROCEDURE`, `USING`, `MOVE`, `TO`, `COMPUTE`, `ROUNDED`, `ON`, `NOT`, `SIZE`, `ERROR`, `END-COMPUTE`, `ADD`, `GIVING`, `END-ADD`, `SUBTRACT`, `FROM`, `END-SUBTRACT`, `MULTIPLY`, `BY`, `END-MULTIPLY`, `DIVIDE`, `INTO`, `END-DIVIDE`, `IF`, `THEN`, `ELSE`, `END-IF`, `GOBACK`), (b) banned COBOL keywords (`STOP`, `RUN`, `CALL`, `COPY`, `REPLACE`, `REDEFINES`, `RENAMES`, `OCCURS`, `DEPENDING`, `EXTERNAL`, `GLOBAL`, `SYNCHRONIZED`, `SYNC`, `JUSTIFIED`, `BLANK`, `POINTER`, `COMP`, `COMP-1`, `COMP-2`, `COMP-4`, `COMP-5`, `BINARY`, `GO`, `PERFORM`, `THRU`, `THROUGH`, `EVALUATE`, `WHEN`, `ACCEPT`, `OPEN`, `READ`, `WRITE`, `CLOSE`, `EXEC`, `EXIT`, `ALTER`), and (c) **special registers & figurative constants (`RETURN-CODE`, `TALLY`, `SORT-RETURN`, `WHEN-COMPILED`, `LINAGE-COUNTER`, `SHIFT-IN`, `SHIFT-OUT`, `DEBUG-ITEM`, `ADDRESS`, `LENGTH`, `FUNCTION`, `ZERO`, `ZEROS`, `ZEROES`, `SPACE`, `SPACES`, `HIGH-VALUE`, `HIGH-VALUES`, `LOW-VALUE`, `LOW-VALUES`, `QUOTE`, `QUOTES`, `NULL`, `NULLS`)**.
  - `USER_IDENT` / `PROG_NAME`: matches `^[A-Za-z][A-Za-z0-9-]{0,29}$` with no trailing hyphen (`!word.endswith("-")`) **and** `word.upper() not in RESERVED_WORDS`. Malformed words (e.g., trailing hyphen `FOO-` or $>30$ chars) fail at the **`Lexical`** layer (`ERR_LEX_INVALID_WORD`).
- **Lark LALR(1) Grammar (`Grammar` Layer — Zero Shift/Reduce Ambiguity):**
  ```ebnf
  program          : id_div data_div proc_div
  id_div           : "IDENTIFICATION" "DIVISION" "." "PROGRAM-ID" "." PROG_NAME ["IS" "INITIAL"] "."
  data_div         : "DATA" "DIVISION" "." [ws_sec] linkage_sec
  ws_sec           : "WORKING-STORAGE" "SECTION" "." data_entry*
  linkage_sec      : "LINKAGE" "SECTION" "." data_entry+

  data_entry       : LEVEL_NUM USER_IDENT [pic_clause] [usage_clause] [sign_clause] [value_clause] "."
  pic_clause       : ("PIC" | "PICTURE") ["IS"] pic_str
  pic_str          : ["S"i] digit_run ("V"i digit_run)?          -> pic_int_or_mixed
                   | ["S"i] "V"i digit_run                       -> pic_frac_only
  digit_run        : ("9" ["(" POS_INT ")"])+
  usage_clause     : ["USAGE" ["IS"]] ("COMP-3" | "PACKED-DECIMAL" | "DISPLAY")
  sign_clause      : ["SIGN" ["IS"]] ("LEADING" | "TRAILING") "SEPARATE" ["CHARACTER"]
  value_clause     : "VALUE" ["IS"] SIGNED_DEC_LIT

  proc_div         : "PROCEDURE" "DIVISION" ["USING" USER_IDENT+] "." sentence+
  sentence         : stmt+ "."
  stmt             : simple_stmt | compound_stmt

  simple_stmt      : move_stmt | compute_plain | add_plain | sub_plain | mul_plain | div_plain | "GOBACK"
  compound_stmt    : compute_se | add_se | sub_se | mul_se | div_se | if_stmt

  target_spec      : USER_IDENT ["ROUNDED"]
  size_err_clauses : ["ON"] "SIZE" "ERROR" stmt+ ("NOT" ["ON"] "SIZE" "ERROR" stmt+)?
                   | "NOT" ["ON"] "SIZE" "ERROR" stmt+

  move_stmt        : "MOVE" atom "TO" USER_IDENT+
  compute_plain    : "COMPUTE" target_spec "=" expr ["END-COMPUTE"]
  compute_se       : "COMPUTE" target_spec "=" expr size_err_clauses "END-COMPUTE"
  add_plain        : "ADD" atom+ ("TO" | "GIVING") target_spec ["END-ADD"]
  add_se           : "ADD" atom+ ("TO" | "GIVING") target_spec size_err_clauses "END-ADD"
  sub_plain        : "SUBTRACT" atom+ "FROM" target_spec ["END-SUBTRACT"]
                   | "SUBTRACT" atom "FROM" atom "GIVING" target_spec ["END-SUBTRACT"]
  sub_se           : "SUBTRACT" atom+ "FROM" target_spec size_err_clauses "END-SUBTRACT"
                   | "SUBTRACT" atom "FROM" atom "GIVING" target_spec size_err_clauses "END-SUBTRACT"
  mul_plain        : "MULTIPLY" atom "BY" atom "GIVING" target_spec ["END-MULTIPLY"]
  mul_se           : "MULTIPLY" atom "BY" atom "GIVING" target_spec size_err_clauses "END-MULTIPLY"
  div_plain        : "DIVIDE" atom ("BY" | "INTO") atom "GIVING" target_spec ["END-DIVIDE"]
  div_se           : "DIVIDE" atom ("BY" | "INTO") atom "GIVING" target_spec size_err_clauses "END-DIVIDE"
  if_stmt          : "IF" cond ["THEN"] stmt+ ["ELSE" stmt+] "END-IF"

  ?expr            : term (("+" | "-") term)*
  ?term            : factor (("*" | "/") factor)*
  ?factor          : ("+" | "-") factor | atom | "(" expr ")"
  atom             : USER_IDENT | SIGNED_DEC_LIT
  cond             : expr ("=" | "<>" | "<" | "<=" | ">" | ">=") expr
  ```

### 3.1 Positive `NVS-0` COBOL Fixtures (`#1–#12`)

```cobol
      * === #1: EX1FEE.cbl (Positive; LK-IO = 10B: 4+2+4) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. EX1FEE.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-IO.
           05  LK-AMOUNT    PIC S9(5)V99  COMP-3.
           05  LK-RATE      PIC SV999     COMP-3.
           05  LK-FEE       PIC S9(5)V99  COMP-3.
       PROCEDURE DIVISION USING LK-IO.
           COMPUTE LK-FEE = LK-AMOUNT * LK-RATE
           GOBACK.
```

```cobol
      * === #2: EX2RND.cbl (Positive; LK-IO = 8B: 3+2+3) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. EX2RND.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-IO.
           05  LK-BASE      PIC S9(3)V99  COMP-3.
           05  LK-FACTOR    PIC SV99      COMP-3.
           05  LK-OUT       PIC S9(4)V9   COMP-3.
       PROCEDURE DIVISION USING LK-IO.
           COMPUTE LK-OUT ROUNDED = LK-BASE * LK-FACTOR
           GOBACK.
```

```cobol
      * === #3: EX3DIVA.cbl (Positive; LK-IO = 11B: 2+2+3+4) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. EX3DIVA.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-IO.
           05  LK-NUM       PIC S9(3)     COMP-3.
           05  LK-DEN       PIC S9(3)     COMP-3.
           05  LK-NOTIONAL  PIC S9(5)     COMP-3.
           05  LK-ACCRUAL   PIC S9(5)V99  COMP-3.
       PROCEDURE DIVISION USING LK-IO.
           COMPUTE LK-ACCRUAL = (LK-NUM / LK-DEN) * LK-NOTIONAL
           GOBACK.
```

```cobol
      * === #4: EX3DIVB.cbl (Positive; LK-IO = 12B: 2+2+4+4) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. EX3DIVB.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-IO.
           05  LK-NUM       PIC S9(3)     COMP-3.
           05  LK-DEN       PIC S9(3)     COMP-3.
           05  LK-NOTIONAL  PIC S9(5)V99  COMP-3.
           05  LK-ACCRUAL   PIC S9(5)V99  COMP-3.
       PROCEDURE DIVISION USING LK-IO.
           COMPUTE LK-ACCRUAL = (LK-NUM / LK-DEN) * LK-NOTIONAL
           GOBACK.
```

```cobol
      * === #5: EX4UNSG.cbl (Positive; LK-IO = 18B: 4+4+3+3+3+1) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. EX4UNSG.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-IO.
           05  LK-A         PIC S9(5)V99  COMP-3.
           05  LK-B         PIC S9(5)V99  COMP-3.
           05  LK-UNSG-TR   PIC 9(3)V99   COMP-3.
           05  LK-UNSG-SE   PIC 9(3)V99   COMP-3.
           05  LK-SIGN-TR   PIC S9(3)V99  COMP-3.
           05  LK-ERR-FLAG  PIC 9.
       PROCEDURE DIVISION USING LK-IO.
           MOVE 0 TO LK-ERR-FLAG
           COMPUTE LK-UNSG-TR = LK-A - LK-B
           COMPUTE LK-UNSG-SE = LK-A - LK-B
               ON SIZE ERROR
                   MOVE 1 TO LK-ERR-FLAG
           END-COMPUTE
           COMPUTE LK-SIGN-TR = LK-A - LK-B
           GOBACK.
```

```cobol
      * === #6: T2MULTI.cbl (Positive; 3x 01 params: 4B+4B+4B) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. T2MULTI.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-A             PIC S9(5)V99  COMP-3.
       01  LK-B             PIC S9(5)V99  COMP-3.
       01  LK-SUM           PIC S9(5)V99  COMP-3.
       PROCEDURE DIVISION USING LK-A LK-B LK-SUM.
           COMPUTE LK-SUM = LK-A + LK-B
           GOBACK.
```

```cobol
      * === #7: CALC-FEE.cbl (Positive; Hyphenated ID, 10B) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALC-FEE.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-IO.
           05  LK-AMOUNT    PIC S9(5)V99  COMP-3.
           05  LK-RATE      PIC SV999     COMP-3.
           05  LK-FEE       PIC S9(5)V99  COMP-3.
       PROCEDURE DIVISION USING LK-IO.
           COMPUTE LK-FEE = LK-AMOUNT * LK-RATE
           GOBACK.
```

```cobol
      * === #8: T2BADBCD.cbl (Positive; LK-IO = 6B: 3B+3B) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. T2BADBCD.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-IO.
           05  LK-BAD       PIC S9(3)V99  COMP-3.
           05  LK-OUT       PIC S9(3)V99  COMP-3.
       PROCEDURE DIVISION USING LK-IO.
           COMPUTE LK-OUT = LK-BAD + 1
           GOBACK.
```

```cobol
      * === #9: T3STATE.cbl (Positive; Non-INITIAL, LK-IO = 9B) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. T3STATE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-ACC-VAL       PIC S9(5)     COMP-3 VALUE +10.
       01  WS-ACC-UNIN      PIC S9(5)     COMP-3.
       LINKAGE SECTION.
       01  LK-IO.
           05  LK-STEP      PIC S9(5)     COMP-3.
           05  LK-OUT-VAL   PIC S9(5)     COMP-3.
           05  LK-OUT-UNIN  PIC S9(5)     COMP-3.
       PROCEDURE DIVISION USING LK-IO.
           ADD LK-STEP TO WS-ACC-VAL
           ADD LK-STEP TO WS-ACC-UNIN
           MOVE WS-ACC-VAL TO LK-OUT-VAL
           MOVE WS-ACC-UNIN TO LK-OUT-UNIN
           GOBACK.
```

```cobol
      * === #10: T3INIT.cbl (Positive; IS INITIAL, LK-IO = 9B) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. T3INIT IS INITIAL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-ACC-VAL       PIC S9(5)     COMP-3 VALUE +10.
       01  WS-ACC-UNIN      PIC S9(5)     COMP-3.
       LINKAGE SECTION.
       01  LK-IO.
           05  LK-STEP      PIC S9(5)     COMP-3.
           05  LK-OUT-VAL   PIC S9(5)     COMP-3.
           05  LK-OUT-UNIN  PIC S9(5)     COMP-3.
       PROCEDURE DIVISION USING LK-IO.
           ADD LK-STEP TO WS-ACC-VAL
           ADD LK-STEP TO WS-ACC-UNIN
           MOVE WS-ACC-VAL TO LK-OUT-VAL
           MOVE WS-ACC-UNIN TO LK-OUT-UNIN
           GOBACK.
```

```cobol
      * === #11: T3STICKY.cbl (Positive; 2x 01 params: 3B+3B) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. T3STICKY.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-A             PIC S9(5)     COMP-3.
       01  LK-B             PIC S9(5)     COMP-3.
       PROCEDURE DIVISION USING LK-A LK-B.
           MOVE LK-A TO LK-B
           GOBACK.
```

```cobol
      * === #12: T3DISP.cbl (Positive; Separate-Sign DISPLAY, 19B) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. T3DISP.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-IO.
           05  LK-IN-LEAD   PIC S9(4)V99 SIGN IS LEADING SEPARATE.
           05  LK-OUT-TRAIL PIC S9(3)V99 SIGN IS TRAILING SEPARATE.
           05  LK-OUT-UNSG  PIC 9(4)V99.
       PROCEDURE DIVISION USING LK-IO.
           IF LK-IN-LEAD < 0
               COMPUTE LK-OUT-TRAIL ROUNDED = LK-IN-LEAD / 2
               COMPUTE LK-OUT-UNSG = 0 - LK-IN-LEAD
           ELSE
               COMPUTE LK-OUT-TRAIL ROUNDED = LK-IN-LEAD / 3
               COMPUTE LK-OUT-UNSG = LK-IN-LEAD
           END-IF
           GOBACK.
```

### 3.2 Negative COBOL Fixtures (`#13–#18` — All 6 Complete Sources)

```cobol
      * === #13: T2STOP.cbl (Reject: Grammar [RETURN-CODE & STOP]) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. T2STOP.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-DUMMY         PIC 9.
       PROCEDURE DIVISION USING LK-DUMMY.
           MOVE 42 TO RETURN-CODE
           STOP RUN.
```

```cobol
      * === #14: T2CRASH.cbl (Reject: Grammar [CALL keyword]) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. T2CRASH.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-DUMMY         PIC 9.
       PROCEDURE DIVISION USING LK-DUMMY.
           CALL "crash_now"
           GOBACK.
```

```cobol
      * === #15: NEG_COL73.cbl (Reject: Preflight line 4, col 73) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. NEGCOL73.
       DATA DIVISION.                                                   X
       LINKAGE SECTION.
       01  LK-X             PIC 9 COMP-3.
       PROCEDURE DIVISION USING LK-X.
           GOBACK.
```
*(Line 4 byte count: 7 spaces + `DATA DIVISION.` [14B] + 51 spaces = 72B, followed by `'X'` at exact 1-based column `73`.)*

```cobol
      * === #16: NEG_BADIND.cbl (Reject: Preflight line 6, col 7) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. NEGBADIN.
       DATA DIVISION.
       LINKAGE SECTION.
      -01  LK-X             PIC 9 COMP-3.
       PROCEDURE DIVISION USING LK-X.
           GOBACK.
```
*(Line 6 byte layout: 6 spaces in cols `1–6` followed by `'-'` at exact 1-based column `7`.)*

```cobol
      * === #17: NEG_PIC19.cbl (Reject: AST Semantic 10+9=19 > 18) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. NEGPIC19.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-IO.
           05  LK-AMOUNT    PIC S9(10)V9(9) COMP-3.
       PROCEDURE DIVISION USING LK-IO.
           GOBACK.
```

```cobol
      * === #18: NEG_UNTERM_SE.cbl (Reject: Grammar missing END-*) ===
       IDENTIFICATION DIVISION.
       PROGRAM-ID. NEGUNTSE.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-IO.
           05  LK-A         PIC S9(5)V99  COMP-3.
           05  LK-B         PIC S9(5)V99  COMP-3.
           05  LK-UNSG-SE   PIC 9(3)V99   COMP-3.
           05  LK-SIGN-TR   PIC S9(3)V99  COMP-3.
           05  LK-ERR-FLAG  PIC 9.
       PROCEDURE DIVISION USING LK-IO.
           COMPUTE LK-UNSG-SE = LK-A - LK-B
               ON SIZE ERROR
                   MOVE 1 TO LK-ERR-FLAG
           COMPUTE LK-SIGN-TR = LK-A - LK-B
           GOBACK.
```

### 3.3 Native C Fixtures (`#19–#20` — Both Complete Sources)

```c
/* === #19: crash_helper.c (statically linked into T2CRASH.so) === */
#include <signal.h>
#include <stddef.h>

int crash_now(void) {
    struct sigaction sa;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;
    sa.sa_handler = SIG_DFL;
    sigaction(SIGSEGV, &sa, NULL);
    *(volatile int *)0 = 1;
    return 0;
}
```

```c
/* === #20: EVILMOD.c (compiled to EVILMOD.so, loaded via L2) === */
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
#include <sys/ptrace.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

extern char **environ;

enum {
    DIAG_BUF_MIN   = 16384,
    OFF_STATUS     = 64,   CAP_STATUS     = 4096,
    OFF_UID_MAP    = 4160, CAP_UID_MAP    = 512,
    OFF_GID_MAP    = 4672, CAP_GID_MAP    = 512,
    OFF_ENV_NAMES  = 5184, CAP_ENV_NAMES  = 2048,
    OFF_MOUNTINFO  = 7232, CAP_MOUNTINFO  = 9152
};

struct __attribute__((packed)) evil_diag_hdr {
    uint32_t magic;          /* 0x4556494C ("EVIL") */
    uint8_t  mode;
    uint8_t  submode;
    uint16_t hdr_bytes;      /* 64 */
    int32_t  rc[4];          /* signed outcome per sub-probe (0 or >=0 ok, -1 fail) */
    int32_t  err[4];         /* captured errno per sub-probe (0 if rc >= 0) */
    uint32_t aux_u32;        /* st_mode in 'I', total env var count in 'D' */
    uint16_t status_len;
    uint16_t uid_map_len;
    uint16_t gid_map_len;
    uint16_t env_names_len;
    uint16_t mountinfo_len;
    uint8_t  eof_flags;      /* b0:status b1:uid b2:gid b3:env b4:mountinfo */
    uint8_t  reserved[9];    /* total = 64 bytes */
};

static void read_proc_slice(const char *path, uint8_t *dst, size_t cap,
                            uint16_t *out_len, uint8_t *eof_mask, uint8_t bit) {
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) { *out_len = 0; return; }
    size_t got = 0;
    while (got < cap) {
        ssize_t r = read(fd, dst + got, cap - got);
        if (r < 0) { if (errno == EINTR) continue; break; }
        if (r == 0) { *eof_mask |= (uint8_t)(1U << bit); close(fd); *out_len = (uint16_t)got; return; }
        got += (size_t)r;
    }
    char probe;
    ssize_t extra;
    do { extra = read(fd, &probe, 1); } while (extra < 0 && errno == EINTR);
    if (extra == 0) *eof_mask |= (uint8_t)(1U << bit);
    close(fd);
    *out_len = (uint16_t)got;
}

static void probe_open(const char *path, int flags, mode_t mode,
                       int32_t *out_rc, int32_t *out_err, int unlink_on_ok) {
    errno = 0;
    int fd = open(path, flags, mode);
    if (fd >= 0) {
        *out_rc = 0;
        *out_err = 0;
        close(fd);
        if (unlink_on_ok) unlink(path);
    } else {
        *out_rc = -1;
        *out_err = errno;
    }
}

int necro_plugin_entry(uint8_t **bufs, const uint32_t *lens, uint16_t argc) {
    if (argc < 1 || lens[0] < DIAG_BUF_MIN) return -1;
    uint8_t *b = bufs[0];
    uint8_t mode = b[0], sub = b[1];
    memset(b, 0, DIAG_BUF_MIN);
    struct evil_diag_hdr *h = (struct evil_diag_hdr *)b;
    h->magic = 0x4556494CU;
    h->mode = mode;
    h->submode = sub;
    h->hdr_bytes = sizeof(*h);

    if (mode == 'K') { /* 2F-L2: uncatchable native SIGSEGV */
        struct sigaction sa = {0};
        sa.sa_handler = SIG_DFL;
        sigaction(SIGSEGV, &sa, NULL);
        *(volatile int *)0 = 1;
    } else if (mode == 'C') { /* 4C-1: raw socket + connect */
        errno = 0;
        int s = (int)syscall(SYS_socket, AF_INET, SOCK_STREAM, 0);
        h->rc[0] = (s >= 0) ? 0 : -1;
        h->err[0] = (s >= 0) ? 0 : errno;
        if (s >= 0) {
            struct sockaddr_in sa = {.sin_family = AF_INET, .sin_port = htons(53)};
            inet_pton(AF_INET, "1.1.1.1", &sa.sin_addr);
            errno = 0;
            int c = connect(s, (struct sockaddr *)&sa, sizeof(sa));
            h->rc[1] = (c == 0) ? 0 : -1;
            h->err[1] = (c == 0) ? 0 : errno;
            close(s);
        }
    } else if (mode == 'I') { /* 4D-0 & 4D-2: full status, uid_map, gid_map + DAC */
        read_proc_slice("/proc/self/status", b + OFF_STATUS, CAP_STATUS,
                        &h->status_len, &h->eof_flags, 0);
        read_proc_slice("/proc/self/uid_map", b + OFF_UID_MAP, CAP_UID_MAP,
                        &h->uid_map_len, &h->eof_flags, 1);
        read_proc_slice("/proc/self/gid_map", b + OFF_GID_MAP, CAP_GID_MAP,
                        &h->uid_map_len ? &h->gid_map_len : &h->gid_map_len, &h->eof_flags, 2);
        struct stat st = {0};
        errno = 0;
        h->rc[0] = stat("/stage/root_only_secret.txt", &st);
        h->err[0] = (h->rc[0] == 0) ? 0 : errno;
        h->aux_u32 = (uint32_t)st.st_mode;
        probe_open("/stage/root_only_secret.txt", O_RDONLY, 0, &h->rc[1], &h->err[1], 0);
    } else if (mode == 'D') { /* 4D-1: absent host file + full env var name list */
        probe_open("/tmp/host_gateway_secret.txt", O_RDONLY, 0, &h->rc[0], &h->err[0], 0);
        uint32_t cnt = 0;
        size_t pos = 0;
        int fit = 1;
        for (char **e = environ; e && *e; ++e) {
            cnt++;
            size_t nlen = strcspn(*e, "=");
            if (pos + nlen + 1 <= CAP_ENV_NAMES) {
                memcpy(b + OFF_ENV_NAMES + pos, *e, nlen);
                b[OFF_ENV_NAMES + pos + nlen] = '\n';
                pos += nlen + 1;
            } else {
                fit = 0;
            }
        }
        h->aux_u32 = cnt;
        h->env_names_len = (uint16_t)pos;
        if (fit) h->eof_flags |= (1U << 3);
    } else if (mode == 'E') { /* 4E-0: mountinfo + EROFS vs $TMPDIR/ok RW */
        char ok_path[256];
        const char *td = getenv("TMPDIR");
        snprintf(ok_path, sizeof(ok_path), "%s/ok", (td && *td) ? td : "/missing");
        probe_open("/ro_probe/x", O_CREAT | O_WRONLY, 0600, &h->rc[0], &h->err[0], 1);
        probe_open("/usr/x", O_CREAT | O_WRONLY, 0600, &h->rc[1], &h->err[1], 1);
        probe_open("/stage/x", O_CREAT | O_WRONLY, 0600, &h->rc[2], &h->err[2], 1);
        probe_open(ok_path, O_CREAT | O_WRONLY | O_TRUNC, 0600, &h->rc[3], &h->err[3], 1);
        read_proc_slice("/proc/self/mountinfo", b + OFF_MOUNTINFO, CAP_MOUNTINFO,
                        &h->mountinfo_len, &h->eof_flags, 4);
    } else if (mode == 'F') { /* 4F-1..8: raw syscalls */
        long r = -1;
        char *const av[] = {"/bin/sh", NULL};
        struct clone_args ca = {0};
        errno = 0;
        switch (sub) {
            case 1: r = syscall(SYS_fork); if (r == 0) _exit(0); break;
            case 2: r = syscall(SYS_vfork); if (r == 0) _exit(0); break;
            case 3: r = syscall(SYS_clone, (unsigned long)SIGCHLD, 0UL, NULL, NULL, 0UL); if (r == 0) _exit(0); break;
            case 4: ca.exit_signal = SIGCHLD; r = syscall(SYS_clone3, &ca, sizeof(ca)); if (r == 0) _exit(0); break;
            case 5: r = syscall(SYS_execve, "/bin/sh", av, environ); break;
            case 6: r = syscall(SYS_execveat, AT_FDCWD, "/bin/sh", av, environ, 0); break;
            case 7: r = syscall(SYS_ptrace, PTRACE_TRACEME, 0, NULL, NULL); break;
            case 8: r = syscall(SYS_unshare, CLONE_NEWUSER); break;
        }
        h->rc[0] = (r >= 0) ? 0 : -1;
        h->err[0] = (r >= 0) ? 0 : errno;
    } else if (mode == 'L') { /* sub=0: spin-only; sub=1: fork 4 children + spin */
        sigset_t s;
        sigfillset(&s);
        sigprocmask(SIG_BLOCK, &s, NULL);
        if (sub == 1) {
            for (int i = 0; i < 4; i++) {
                if (fork() == 0) { for (;;) asm volatile(""); }
            }
        }
        for (;;) asm volatile("");
    }
    return 0;
}
```
