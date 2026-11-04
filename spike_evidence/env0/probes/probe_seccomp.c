/* Env-0 capability probe: CONFIG_SECCOMP_FILTER operational check.
   Loads a minimal cBPF filter (default ALLOW, getpid -> EPERM) after
   PR_SET_NO_NEW_PRIVS, verifies Seccomp:2 in /proc/self/status, and
   demonstrates enforcement by expecting getpid() to fail with EPERM.
   Filter program uses fully designated initializers (Rev5 §2.1.5). */
#define _GNU_SOURCE
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/seccomp.h>

static int seccomp(unsigned int op, unsigned int flags, void *args) {
    return (int)syscall(SYS_seccomp, op, flags, args);
}

int main(void) {
    enum {
        /* jt/jf are relative to the NEXT instruction:
           [0]LD arch [1]JEQ arch (jf->4=>6 KILL) [2]LD nr [3]JEQ getpid
           (jf->1=>5 ALLOW) [4]ERRNO(EPERM) [5]ALLOW [6]KILL_PROCESS        */
        JT_ALLOW_FROM_ARCH = 0,
        JF_KILL_ARCH       = 4,  /* from idx1 next=2: 2+4 = 6 = KILL_PROCESS */
        JT_NR_MATCH        = 0,
        JF_NR_ALLOW        = 1   /* from idx3 next=4: 4+1 = 5 = ALLOW        */
    };
    struct sock_filter prog[] = {
        {.code = (unsigned short)(BPF_LD | BPF_W | BPF_ABS), .jt = 0,
         .jf = 0, .k = offsetof(struct seccomp_data, arch)},
        {.code = (unsigned short)(BPF_JMP | BPF_JEQ | BPF_K), .jt = JT_ALLOW_FROM_ARCH,
         .jf = JF_KILL_ARCH, .k = AUDIT_ARCH_X86_64},
        {.code = (unsigned short)(BPF_LD | BPF_W | BPF_ABS), .jt = 0,
         .jf = 0, .k = offsetof(struct seccomp_data, nr)},
        {.code = (unsigned short)(BPF_JMP | BPF_JEQ | BPF_K), .jt = JT_NR_MATCH,
         .jf = JF_NR_ALLOW, .k = (unsigned int)__NR_getpid},
        {.code = (unsigned short)(BPF_RET | BPF_K), .jt = 0, .jf = 0,
         .k = SECCOMP_RET_ERRNO | (EPERM & SECCOMP_RET_DATA)},
        {.code = (unsigned short)(BPF_RET | BPF_K), .jt = 0, .jf = 0,
         .k = SECCOMP_RET_ALLOW},
        {.code = (unsigned short)(BPF_RET | BPF_K), .jt = 0, .jf = 0,
         .k = SECCOMP_RET_KILL_PROCESS},
    };
    struct sock_fprog fprog = {
        .len = (unsigned short)(sizeof(prog) / sizeof(prog[0])),
        .filter = prog
    };

    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) {
        fprintf(stderr, "PROBE-FAIL: PR_SET_NO_NEW_PRIVS errno=%d\n", errno);
        return 20;
    }
    if (seccomp(SECCOMP_SET_MODE_FILTER, 0, &fprog) != 0 &&
        prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &fprog) != 0) {
        fprintf(stderr, "PROBE-FAIL: filter load errno=%d\n", errno);
        return 21;
    }
    FILE *f = fopen("/proc/self/status", "r");
    char line[256]; int seccomp_mode = -1, filters = -1;
    while (f && fgets(line, sizeof(line), f)) {
        if (strncmp(line, "Seccomp:", 8) == 0) seccomp_mode = atoi(line + 8);
        if (strncmp(line, "Seccomp_filters:", 16) == 0) filters = atoi(line + 16);
    }
    if (f) fclose(f);
    long r = syscall(__NR_getpid);
    int getpid_blocked = (r == -1 && errno == EPERM);
    printf("PROBE-OK seccomp_mode=%d filters=%d getpid_blocked=%s\n",
           seccomp_mode, filters, getpid_blocked ? "yes(EPERM)" : "NO");
    return (seccomp_mode == 2 && filters >= 1 && getpid_blocked) ? 0 : 22;
}
