      * DECISIONS: decision-path demonstration (COPY outside frozen
      * grammar; scanned decision structure)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DECISIONS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY AUDREC.
       01  WS-FLAG        PIC X.
       01  WS-ADJ         PIC S9(15)V99 COMP-3.
       PROCEDURE DIVISION.
           MOVE 1200 TO LK-ID
           COMPUTE WS-ADJ ROUNDED = LK-AMT * 2
           IF WS-ADJ > 100
               MOVE 1 TO LK-ID
               IF WS-FLAG = "Y"
                   MOVE ZERO TO LK-ID
               END-IF
               MOVE SPACE TO WS-FLAG
               MOVE ZERO TO WS-ADJ
               CALL "GLUPDATE" USING WS-ADJ
           ELSE
               MOVE 2 TO LK-ID
           END-IF
           MOVE 9 TO LK-ID
           GOBACK.
