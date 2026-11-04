      * AUDPOST: posts audited amounts (COPY outside frozen grammar;
      * semantic participation via the copybook-aware logical model)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. AUDPOST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY AUDREC.
       PROCEDURE DIVISION.
           MOVE 123456 TO LK-AMT
           MOVE 1.2345 TO LK-RATE-EX
           MOVE 12345 TO LK-ID
           GOBACK.
