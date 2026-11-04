      * PAYROLL: drives the GL update (CALL outside the frozen grammar)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-PGM           PIC X(8).
       LINKAGE SECTION.
       01  LK-IO.
           05  LK-AMT       PIC S9(5)V99  COMP-3.
       PROCEDURE DIVISION USING LK-IO.
           CALL "GLUPDATE" USING LK-IO
           MOVE "DYNBILL" TO WS-PGM
           CALL WS-PGM
           GOBACK.
