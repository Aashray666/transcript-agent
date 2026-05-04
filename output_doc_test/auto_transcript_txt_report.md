# Document Risk Extraction Report

**Document:** auto_transcript.txt
**Type:** Con Call Transcript
**Total Risks Extracted:** 2

## Summary Statistics

| Metric | Count |
|--------|-------|
| Chunks processed | 9 |
| Chunks with risks | 9 |
| Raw mentions | 18 |
| After deduplication | 2 |
| Critical severity | 0 |
| High severity | 2 |
| Medium severity | 0 |
| Low severity | 0 |
| Material weaknesses | 0 |
| Repeat findings | 0 |
| Quantified risks | 1 |

## Risk Register

| ID | Description | Category | Severity | Type | Sections | Flags |
|----|-------------|----------|----------|------|----------|-------|
| DOC_RISK_001 | EV transition execution risk | Strategic | HIGH | INHERENT | Sample ERM Engagement Call Transcript | FORWARD_LOOKING |
| DOC_RISK_002 | Supply chain concentration risk | Operational | HIGH | INHERENT | Sample ERM Engagement Call Transcript | QUANTIFIED, UNMITIGATED |

---

## Detailed Risk Descriptions

### DOC_RISK_001: EV transition execution risk

- **Category:** Strategic
- **Severity:** HIGH
- **Type:** INHERENT
- **Occurrence count:** 9 chunk(s)
- **Sections:** Sample ERM Engagement Call Transcript
- **Flags:** FORWARD_LOOKING

**Verbatim evidence:**
> we have committed heavily to electrification

---

### DOC_RISK_002: Supply chain concentration risk

- **Category:** Operational
- **Severity:** HIGH
- **Type:** INHERENT
- **Occurrence count:** 9 chunk(s)
- **Sections:** Sample ERM Engagement Call Transcript
- **Financial quantification:** 22% single-sourced components
- **Flags:** QUANTIFIED, UNMITIGATED

**Verbatim evidence:**
> 22% of components are single-sourced

---
