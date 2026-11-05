      * EVALFIX: unsupported decision structure demonstration.
      * EVALUATE is outside the supported decision model (frozen-grammar
      * boundary): this program is recorded unsupported, never interpreted,
      * and yields no rule candidates.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. EVALFIX.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-MODE        PIC 9.
       01  WS-RESULT      PIC 9(3).
       PROCEDURE DIVISION.
           MOVE 1 TO WS-MODE
           EVALUATE WS-MODE
               WHEN 1
                   MOVE 10 TO WS-RESULT
               WHEN OTHER
                   MOVE 99 TO WS-RESULT
           END-EVALUATE
           GOBACK.
