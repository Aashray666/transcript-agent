# Likelihood Assessment Framework

## How ERM Consultants Actually Determine Likelihood

Likelihood scoring in ERM is NOT a single judgment call. It's a composite assessment derived from multiple evidence streams. Here's how real consultants arrive at a number:

### The 4 Evidence Pillars for Likelihood

```
LIKELIHOOD SCORE = f(Historical Frequency, External Environment, Control Maturity, Expert Judgment)
```

**Pillar 1: Historical Frequency (Weight: ~30%)**
- Has this risk materialized before for this company? How often?
- Has it materialized for peers in the same sector? How often?
- What's the base rate for this type of event in the industry?
- Source: Client interview (Q5), questionnaire, industry loss databases

**Pillar 2: External Environment / Exposure (Weight: ~30%)**
- What external conditions increase or decrease the probability?
- Regulatory trajectory (tightening = higher likelihood for compliance risks)
- Market conditions (volatility = higher likelihood for financial risks)
- Geopolitical climate (tension = higher likelihood for supply chain/trade risks)
- Technology evolution pace (fast = higher likelihood for obsolescence risks)
- Source: Market Research Agent, news intelligence, sector reports

**Pillar 3: Control Maturity (Weight: ~25%)**
- Does the company have controls in place for this risk?
- Have those controls been tested?
- Are there known gaps the client acknowledged?
- A risk with strong, tested controls has lower likelihood than one with weak/untested controls
- Source: Client interview (Q16, Q17), questionnaire

**Pillar 4: Expert / Sector Judgment (Weight: ~15%)**
- Given the sector, company size, and operating model, what's the baseline expectation?
- Some risks are structurally more likely in certain sectors (e.g., recall risk in automotive is higher than in software)
- Adjustments for company-specific factors (geography, maturity, complexity)
- Source: Sector knowledge, risk registry base rates

### How This Maps to Agents

| Pillar | Primary Agent | Secondary Agent |
|--------|--------------|-----------------|
| Historical Frequency | Evidence Retriever (transcript Q5, past events) | Knowledge Summarizer (questionnaire incident history) |
| External Environment | Market Research Agent | Evidence Retriever (client's own view from Q4, Q18) |
| Control Maturity | Knowledge Summarizer (questionnaire Q16/Q17 data) | Evidence Retriever (transcript Q16, Q17) |
| Expert / Sector Judgment | Scoring Agent (built-in sector knowledge) | Market Research Agent (peer benchmarks) |

### The Scoring Agent's Likelihood Reasoning Chain

For each risk, the Scoring Agent must:

1. **Check historical frequency:** "Has this happened before? How recently? How often?"
   → Map to frequency band in the table below

2. **Assess external environment:** "Is the external environment making this more or less likely?"
   → Adjust up or down by 1 level if strong signal

3. **Evaluate control maturity:** "Does the client have controls? Are they tested?"
   → Adjust down by 1 if strong tested controls, up by 1 if acknowledged gaps

4. **Apply sector judgment:** "For an automotive manufacturer of this size and geography, is this baseline likelihood reasonable?"
   → Final sanity check

5. **Produce final score with explicit reasoning for each pillar**

---

## Likelihood Assessment Table — Automotive Sector

### 5-Level Scale

| Score | Level | Definition | Frequency Indicator | Probability (12-month horizon) |
|-------|-------|-----------|---------------------|-------------------------------|
| 1 | Rare | Exceptional circumstances only. No history of occurrence at the company or close peers. External environment does not suggest elevated probability. | Has not occurred in 10+ years in the company or comparable peers | <5% chance of occurring in the next 12 months |
| 2 | Unlikely | Could occur but not expected. May have occurred once historically at the company or occasionally at peers. Some external factors present but not acute. | Occurred once in the last 5-10 years at the company, or occasionally at sector peers | 5-20% chance of occurring in the next 12 months |
| 3 | Possible | Reasonable possibility. Has occurred before at the company or regularly at peers. External environment contains active drivers. Controls exist but may have gaps. | Occurred in the last 2-5 years at the company, or regularly at sector peers | 20-50% chance of occurring in the next 12 months |
| 4 | Likely | Expected to occur. Has occurred recently or multiple times. External environment is actively driving this risk. Controls are insufficient or untested. | Occurred in the last 1-2 years, or multiple times historically. Active external drivers present. | 50-80% chance of occurring in the next 12 months |
| 5 | Almost Certain | Expected to occur imminently or is already materializing. Strong historical precedent, acute external drivers, and weak or absent controls. | Currently materializing, or has occurred multiple times recently. External environment is acute. | >80% chance of occurring in the next 12 months |

### Automotive-Specific Likelihood Calibration Guide

These are sector-specific anchors to help the Scoring Agent calibrate likelihood for common automotive risk types:

| Risk Category | Typical Baseline Likelihood | Rationale |
|--------------|---------------------------|-----------|
| Product safety / recall | 4 (Likely) | Automotive recalls are frequent industry-wide. Major OEMs typically have 5-15 recall events per year. |
| Supply chain disruption | 4 (Likely) | Post-pandemic, post-semiconductor-crisis, supply chain events are frequent and expected. |
| Regulatory compliance (emissions) | 3-4 (Possible to Likely) | Regulatory tightening is active and ongoing. Compliance windows are defined and approaching. |
| Cyber attack (IT/OT) | 3 (Possible) | Automotive sector is increasingly targeted. Connected vehicles expand attack surface. |
| Currency / commodity volatility | 4 (Likely) | Structural exposure for global manufacturers. Volatility is the norm, not the exception. |
| EV transition execution | 3-4 (Possible to Likely) | Industry-wide challenge. Most OEMs are behind their own timelines. |
| Geopolitical / trade policy | 3 (Possible) | Elevated but episodic. Current US-China-EU tensions make this higher than historical baseline. |
| Workforce / labour relations | 3 (Possible) | Structural in unionized manufacturing. Transformation periods elevate this. |
| Technology obsolescence | 3 (Possible) | Pace of change is high but not immediate for most systems. |
| Natural disaster / climate | 2 (Unlikely) | Location-dependent. Most automotive plants are in low-risk geographies. |

### Adjustment Rules

| Condition | Adjustment |
|-----------|-----------|
| Client explicitly stated "this has happened to us" (Q5) | +1 to baseline (min score 3) |
| Client stated "we are underprepared" (Q15) | +1 to baseline |
| Client stated "controls are strong and tested" (Q16/Q17) | -1 from baseline |
| Client stated "controls exist but untested" (Q17) | No adjustment (baseline holds) |
| Client stated "no controls" or "gap" (Q16) | +1 to baseline |
| Market Research Agent signals "INCREASING" trend | +1 to baseline |
| Market Research Agent signals "DECREASING" trend | -1 from baseline |
| Risk flagged as CASCADE_SIGNAL with high-likelihood upstream risk | +1 to baseline (cascade effect) |
| Maximum score after all adjustments | 5 |
| Minimum score after all adjustments | 1 |

---

## Inherent Risk Score Calculation

```
Inherent Risk Score = Impact Score × Likelihood Score
```

| Score Range | Rating | Color | Action Required |
|-------------|--------|-------|-----------------|
| 1-4 | Low | Green | Monitor. Review annually. |
| 5-9 | Medium | Yellow | Active monitoring. Review quarterly. Ensure controls are documented. |
| 10-15 | High | Orange | Priority attention. Review monthly. Strengthen controls. Board awareness. |
| 16-25 | Critical | Red | Immediate action. Dedicated risk owner. Board reporting. Escalation protocol. |
