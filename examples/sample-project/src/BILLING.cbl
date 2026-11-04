      * BILLING: bills via GLUPDATE (arg count + size mismatch demo)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BILLING.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-BILL-AMT     PIC S9(5)V99 COMP-3.
       01  WS-CODE         PIC 9(3).
       PROCEDURE DIVISION.
           CALL "GLUPDATE" USING WS-BILL-AMT WS-CODE
           CALL "NOTINPROJ" USING WS-BILL-AMT
           GOBACK.
