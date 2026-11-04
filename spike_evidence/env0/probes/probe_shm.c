/* Env-0 capability probe: SysV shared memory operational check (private segment). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ipc.h>
#include <sys/shm.h>

int main(void) {
    int shmid = shmget(IPC_PRIVATE, 4096, IPC_CREAT | 0600);
    if (shmid < 0) { fprintf(stderr, "PROBE-FAIL shmget\n"); return 30; }
    void *a = shmat(shmid, NULL, 0);
    if (a == (void *)-1) { fprintf(stderr, "PROBE-FAIL shmat\n"); return 31; }
    memset(a, 0x5A, 8);
    int ok = ((unsigned char *)a)[0] == 0x5A;
    if (shmdt(a) != 0) { fprintf(stderr, "PROBE-FAIL shmdt\n"); return 32; }
    if (shmctl(shmid, IPC_RMID, NULL) != 0) { fprintf(stderr, "PROBE-FAIL IPC_RMID\n"); return 33; }
    printf("PROBE-OK shmget=%d roundtrip=%s\n", shmid, ok ? "yes" : "NO");
    return ok ? 0 : 34;
}
