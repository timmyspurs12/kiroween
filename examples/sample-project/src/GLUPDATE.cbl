      * GLUPDATE: posts a batch total (subset-clean program)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. GLUPDATE.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-IO.
           05  LK-AMT       PIC S9(5)V99  COMP-3.
           05  LK-RATE      PIC SV999     COMP-3.
           05  LK-POSTED    PIC S9(5)V99  COMP-3.
       PROCEDURE DIVISION USING LK-IO.
           COMPUTE LK-POSTED = LK-AMT * LK-RATE
           GOBACK.
