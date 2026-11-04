      * EMPREC: employee record handling (COPY outside the frozen grammar)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. EMPREC.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY EMPREC.
       LINKAGE SECTION.
       01  LK-IO.
           05  LK-AMT       PIC S9(5)V99  COMP-3.
       PROCEDURE DIVISION USING LK-IO.
           GOBACK.
