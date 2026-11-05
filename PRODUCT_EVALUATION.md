# NecroSpec product evaluation (M11)

## What the product demonstrably does today

NecroSpec is a local, evidence-first COBOL analysis workstation for a deliberately frozen subset of fixed-format source. Its Python engine offers a single-file analysis API/CLI and a project analysis path. The current project envelope (schema v8) inventories files, analyzes indexed programs, retains skipped/rejected inputs, scans and resolves COPY/CALL relationships, records logical data and supported statement flow, surfaces structural decision/rule candidates, and derives planning-readiness states and work packages from M1–M9 records.

The checked-in sample is 18 files (12 programs, 6 copybooks). Its current M10 output is `investigation_required` for all 12 programs, with 28 work packages. Existing source-backed examples include a precision-loss risk, ambiguous/missing/dynamic dependencies, incomplete CALL USING evidence, and unsupported EVALUATE. The controlled state cases in `examples/illustrative-readiness/` are synthetic/controlled; they are not customer applications or validation evidence.

## Target users and problems (product hypotheses, not validated research)

Likely users to evaluate include COBOL maintainers, migration engineers, technical architects, and consultancy teams assessing inherited application portfolios. Their hypothesized problems are incomplete inventory, difficult-to-follow dependencies and data movement, hard-to-audit unsupported syntax, and migration planning that loses the link between a summary claim and source evidence. These are target hypotheses; no interviews or demand research are claimed here.

## Why evidence traceability could matter commercially (hypothesis)

A repeatable source location, existing diagnostic classification, declaration/operation context, and explicit limitation can make findings reviewable by engineers and easier to turn into bounded investigation tasks. This may reduce time spent reconstructing why an assessment reached a conclusion and may support defensible handoffs. The product has not measured time savings, reduced defects, or commercial value; those benefits require customer validation.

## Unsupported or unproven today

- Complete COBOL language, dialect, compiler, preprocessor, COPY REPLACING, control-flow or runtime coverage.
- Compilation, execution, data-value simulation, program equivalence, automated translation, or migration-safety certification.
- Verified business-rule extraction: rule candidates are source structure, not domain-approved requirements.
- External build/configuration discovery, dynamic target resolution beyond recorded static evidence, authoritative interface contracts, database/job/scheduler/environment analysis, or runtime dependency behavior.
- Automatic impact completeness for syntax or files outside the ingested and supported evidence.
- Customer-tested usability, accessibility, performance at enterprise scale, security certification, or validated economics.

The Rev6.4.2 grammar/specification and all historical evidence remain frozen. Unsupported inputs are reported rather than silently upgraded into understood source.

## What a consultancy would need before adopting it

Pilot with representative, permissioned portfolios and agreed supported-scope boundaries; compare findings against senior COBOL review; quantify false positives, false negatives and review time; validate source ingestion across encodings, fixed/free formats, dialects, COPY search paths and build conventions; define how analysts curate evidence and export work packages; agree ownership, reproducibility and versioning of assessments; and establish support and data-handling terms. No customer pilot or validation has occurred in this work.

## What an enterprise would need before deployment

Security/threat assessment, dependency and software-bill-of-materials review, access control and auditability, data residency and retention controls, deployment/upgrade model, operational monitoring, backup/recovery, performance and scale testing, accessibility review, support/SLA ownership, and a governance process for unsupported constructs and human-verified planning decisions. Current evidence is a local application and API smoke/regression checks, not production-readiness certification.

## Most important open product questions

1. Which COBOL dialects, source formats and build environments dominate the intended first user segment?
2. Which evidence exports and repository/CI integrations are needed for real investigation handoffs?
3. What level of false-positive/false-negative tolerance is acceptable for each finding category?
4. Should assessment provenance include immutable source revision identifiers and reviewer dispositions?
5. How should users manage large, multi-root COPY search paths and externally resolved dependencies?
6. What deployment/data governance model is required by target organizations?
7. Which users would pay for the product, which workflow would it replace, and what measurable outcome would justify adoption?

These are questions for discovery, not conclusions. No customer interviews, testimonials, market research, pricing tests, demand claims, or willingness-to-pay evidence are represented as facts.
