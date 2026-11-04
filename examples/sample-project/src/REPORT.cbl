      * REPORT: user info reporting (COPY outside the frozen grammar)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. REPORT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY USRINFO.
       LINKAGE SECTION.
       01  LK-IO.
           05  LK-AMT       PIC S9(5)V99  COMP-3.
       PROCEDURE DIVISION USING LK-IO.
           GOBACK.
