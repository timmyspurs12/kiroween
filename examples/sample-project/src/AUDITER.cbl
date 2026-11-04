      * AUDITER: audits an account record (COPY outside frozen grammar)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. AUDITER.
       DATA DIVISION.
       LINKAGE SECTION.
       COPY AUDREC.
       PROCEDURE DIVISION USING LK-REC.
           GOBACK.
