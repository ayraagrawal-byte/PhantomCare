# Step 3 - Core Data Contracts

Date: 2026-11-13

## Purpose

PhantomCare's application layers share immutable, strict Pydantic contracts. The pipeline preserves raw source values, the indicator engine attaches evidence to every scored result, and the API and agent consume the same validated representation.

## Contracts

- `EvidenceRecord`: dataset, stable record identifier, timestamp, selected source fields, and notes
- `Address`: raw and normalized forms, building key, suite, coordinates, confidence, and warnings
- `Hospice`: enrollment identity, provider identifiers, address, and supporting records
- `Owner`: masked display identity, owner type, optional address, and supporting records
- `Ownership`: hospice-owner relationship, percentage, date, and supporting records
- `Building`: building facts, hospice count, coordinates, and supporting records
- `IndicatorResult`: value, bounded score contribution, evidence, and limitations
- `ReviewPriorityScore`: versioned, explainable components whose sum must equal the total
- `CaseFile` and `CaseFinding`: evidence-backed investigation output with a non-accusatory disclaimer
- `TraceEvent`: observable workflow activity without hidden model reasoning

## Enforced invariants

- Unknown fields are rejected instead of silently discarded.
- Models are immutable after validation.
- Individual owners must be masked in application-facing contracts.
- Scored indicators must carry at least one evidence record.
- Review-priority totals must equal their component contributions.
- NPI, coordinates, percentages, confidence values, and scores have bounded validation.
- Source, case, and trace timestamps must include a timezone and serialize in ISO 8601 form.

## Deferred decisions

Database table definitions and migrations remain separate from API contracts. CMS column mapping will be defined by the ingestion milestone after real source-file schemas are inspected.

