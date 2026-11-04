      * AUDTOTAL: totals audited amounts and feeds GL update
      * (COPY outside frozen grammar; data-flow via the scanner)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. AUDTOTAL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY AUDREC.
       01  WS-TOTAL        PIC S9(7)V99 COMP-3.
       01  WS-COUNT        PIC 9(3).
       PROCEDURE DIVISION.
           MOVE 1200 TO WS-COUNT
           COMPUTE WS-TOTAL ROUNDED = LK-AMT * WS-COUNT
           IF WS-TOTAL > 1000
               MOVE ZERO TO WS-COUNT
           END-IF
           CALL "GLUPDATE" USING WS-TOTAL
           GOBACK.
