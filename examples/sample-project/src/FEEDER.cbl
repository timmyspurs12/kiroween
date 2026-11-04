      * FEEDER: feeds the auditor (copybook-defined LINKAGE parameter)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. FEEDER.
       DATA DIVISION.
       LINKAGE SECTION.
       COPY AUDREC.
       PROCEDURE DIVISION USING LK-REC.
           CALL "AUDITER" USING LK-REC
           GOBACK.
