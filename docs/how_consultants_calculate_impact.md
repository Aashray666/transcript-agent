# How ERM Consultants Actually Calculate Impact

## The Short Answer

Impact scoring is NOT a gut feeling. It's a structured mapping exercise where the consultant takes what the client described and maps it to pre-defined, quantitative thresholds in an impact assessment table. The table is the anchor — without it, every consultant would score differently.

---

## The Process (Step by Step)

### Step 1: Identify the Primary Impact Dimension

Every risk affects the business through one or more dimensions. The consultant's first job is to determine WHICH dimension is the primary channel of impact.

The 7 standard dimensions (as in our table):

| Dimension | When It's Primary |
|-----------|------------------|
| Financial & Growth | The risk directly hits revenue, margins, costs, or capital |
| Operating | The risk disrupts production, supply chain, or day-to-day operations |
| Customer & Market | The risk affects customer relationships, market position, or demand |
| Regulatory & Compliance | The risk triggers regulatory action, fines, or compliance failure |
| Technology & Information | The risk affects IT/OT systems, data, or digital infrastructure |
| People, Health & Safety | The risk affects workforce, safety, or labour relations |
| Reputation & Ethics | The risk damages brand, trust, or stakeholder relationships |

**Key insight:** Most risks touch multiple dimensions. A product recall is simultaneously an Operating impact (production halt), a Financial impact (recall costs), a Regulatory impact (notification obligations), and a Reputation impact (media coverage). The consultant scores the PRIMARY dimension — the one where the impact is most severe.

**How the agent should do this:** The Scoring Agent receives the risk description + evidence + client context. It evaluates all 7 dimensions and selects the one where the impact would be highest. It must justify why that dimension is primary.

---

### Step 2: Select the Most Relevant Sub-Dimension and Metric

Within each dimension, there are sub-dimensions with specific, measurable metrics. The consultant picks the metric that most closely matches the risk scenario.

Example for "Supply Chain Risk":
- Primary dimension: **Operating Impact**
- Sub-dimension: **Supply Chain**
- Metric: **Critical Supplier Disruption** (measured in Days)

Example for "Regulatory Risk due to Emissions":
- Primary dimension: **Regulatory & Compliance Impact**
- Sub-dimension: **Environmental Compliance**
- Metric: **Emissions / Waste Permit Violations** (measured by Severity)

**Key insight:** Sometimes the right metric isn't obvious. "EV Transition Risk" could map to Financial (Revenue Decline), Operating (Production Continuity), or Customer & Market (Market Share Loss). The consultant picks the metric where the WORST-CASE impact is highest — this is inherent risk scoring, so you assume the risk fully materializes.

---

### Step 3: Estimate the Magnitude Using Available Evidence

This is where the actual scoring happens. The consultant takes all available evidence and estimates WHERE on the metric scale the impact would fall if the risk materialized.

**Evidence sources (in order of reliability):**

1. **Client's own quantification** (highest reliability)
   - "The financial hit was over 400 million euros" → directly maps to a % of revenue
   - "18% of our subscriber base for six hours" → directly maps to production downtime

2. **Client's qualitative language** (medium reliability — requires interpretation)
   - "significant" → typically maps to Moderate-High (3-4)
   - "manageable" → typically maps to Low-Moderate (2-3)
   - "existential" → maps to Severe/Catastrophic (5)
   - "minor" → maps to No Impact-Low (1-2)

3. **Questionnaire data** (medium reliability — factual but may be outdated)
   - Revenue figures → allows converting absolute numbers to percentages
   - Plant count → allows assessing operational concentration
   - Workforce numbers → allows assessing people impact scale

4. **Industry benchmarks** (lower reliability — generic, not client-specific)
   - Average recall cost in automotive: 0.5-2% of revenue
   - Average cyber incident cost: varies wildly
   - Used only when client-specific data is unavailable

**The mapping logic:**

```
IF client said "400M euros lost" AND client revenue is 78.4B EUR:
    → 400M / 78,400M = 0.51% of revenue
    → Maps to "No Impact" (<1%) on Revenue Decline metric
    → BUT maps to "4-12 hours" on Production Downtime (6 weeks = severe)
    → PRIMARY impact is Operating, not Financial
    → Score: 5 (Severe) on Production Downtime
```

This is why the dimension selection matters — the same event can be a 1 on one metric and a 5 on another.

---

### Step 4: Apply the Table Criteria

The consultant looks at the specific thresholds in the table and places the estimated magnitude into the correct band.

Example: "Critical Supplier Disruption" for VelocityAuto's semiconductor shortage:
- Duration: 6 weeks (42 days)
- Table thresholds: <1 day (No Impact) | 1-3 days (Low) | 3-7 days (Moderate) | 7-14 days (High) | >14 days (Severe)
- 42 days → clearly >14 days → **Score: 5 (Severe/Catastrophic)**

Example: "Market Share Loss" for VelocityAuto in China:
- China market share: dropped from 5.4% to 3.1% = 2.3 percentage points lost
- Table thresholds: <1% (No Impact) | 1-2% (Low) | 2-5% (Moderate) | 5-10% (High) | >10% (Severe)
- 2.3% → falls in 2-5% band → **Score: 3 (Moderate)**

**Key insight:** The consultant ALWAYS cites the specific threshold that justifies the score. "I scored this as 4 because the table defines High as 7-14 days of supplier disruption, and the client experienced 3 weeks." This is the grounding mechanism that prevents hallucination.

---

### Step 5: Consider Secondary Impacts (But Don't Double-Count)

After scoring the primary impact, the consultant notes secondary impacts but does NOT add them to the score. They're recorded for context and cascade analysis.

Example: Product recall (ADAS software defect)
- **Primary:** Regulatory & Compliance → Product Safety Non-Compliance → 180,000 vehicles → Score 5
- **Secondary:** Financial (recall cost provision) → noted but not scored separately
- **Secondary:** Reputation (media coverage) → noted but not scored separately
- **Secondary:** Customer & Market (customer confidence) → noted but not scored separately

The secondary impacts may be scored as SEPARATE risks if they appear independently in the risk universe (e.g., "Reputational Risk" as its own entry).

---

### Step 6: Calibrate Against Other Risks

Before finalizing, the consultant checks that the impact score is consistent with other scored risks:

- If "Cyber Risk" gets Impact 5, then "External Cyber Attack" (a subset) should not get Impact 5 too — it should be equal or lower
- If "Supply Chain Disruption" gets Impact 5 based on a 6-week event, then "Logistics Disruption" (typically shorter) should get Impact 3-4
- Risks in the same dimension should have a logical ordering

---

## What Makes This Hard for an LLM (And How to Fix It)

### Problem 1: Qualitative-to-Quantitative Translation
The client says "significant" — what number is that? 

**Fix:** The scoring prompt includes explicit mapping rules:
- "minor/small/manageable" → Score 1-2
- "significant/material/concerning" → Score 3-4
- "severe/catastrophic/existential/critical" → Score 4-5
- When in doubt, use the questionnaire data to convert to actual numbers

### Problem 2: Dimension Selection Bias
LLMs tend to pick Financial impact for everything because it's the most "obvious."

**Fix:** The scoring prompt requires the agent to evaluate ALL 7 dimensions and explicitly state why the chosen one is primary. Include: "Consider which dimension would cause the MOST SEVERE consequence if this risk fully materialized."

### Problem 3: Anchoring to First Score
After scoring the first few risks, the LLM anchors and gives similar scores to everything.

**Fix:** Each risk is scored with its own full context package. The prompt includes: "Score this risk independently based on its own evidence. Do not anchor to previous scores." The Consistency Checker catches drift after all scoring is complete.

### Problem 4: Missing Data
Sometimes there's no evidence to estimate magnitude. The client didn't quantify the impact.

**Fix:** When evidence is insufficient:
1. Use questionnaire data to estimate (e.g., revenue figures to calculate percentages)
2. Use sector benchmarks as a fallback
3. If still insufficient, score at the MEDIAN (3) and flag for human review with reason "Insufficient evidence for precise scoring"

---

## The Agent's Impact Scoring Chain (Summary)

```
1. Read risk description + evidence + client context
2. Evaluate all 7 impact dimensions
3. Select PRIMARY dimension (justify why)
4. Select most relevant sub-dimension and metric
5. Estimate magnitude using:
   a. Client's own quantification (if available)
   b. Client's qualitative language (mapped to scale)
   c. Questionnaire data (for conversion to %)
   d. Sector benchmarks (fallback only)
6. Map magnitude to table threshold → Score (1-5)
7. Cite the specific table criteria matched
8. Note secondary impacts (don't score)
9. Check consistency with related risks
10. Output: Score + Dimension + Metric + Justification + Table Criteria
```

---

## Real-World Example: Scoring "Tariffs and Trade Policy" for VelocityAuto

**Step 1 — Dimension:** Financial & Growth (cost structure hit) vs. Operating (supply chain disruption). The 25% tariff directly hits cost of goods sold → Financial is primary.

**Step 2 — Metric:** "Raw Material & Energy Cost Inflation" measured as % cost increase. Alternatively "Pricing Pressure / Inability to Pass Costs" measured as % margin erosion.

**Step 3 — Evidence:**
- Client said: "25% tariffs on auto imports have directly hit our cost structure"
- Client said: "almost no short-term flexibility in our supply chain to absorb another shock"
- Questionnaire: Cost structure has 30% currency mismatch, EBITDA margin already declining (11.8% → 9.2%)
- 25% tariff on imported components affecting ~30% of cost base → effective cost increase of ~7.5%

**Step 4 — Table mapping:**
- Raw Material & Energy Cost Inflation: <2% (No Impact) | 2-5% (Low) | 5-10% (Moderate) | 10-20% (High) | >20% (Severe)
- 7.5% cost increase → falls in 5-10% band → **Score: 3 (Moderate)**
- BUT: EBITDA margin erosion from 11.8% to 9.2% = 2.6 percentage points
- Margins metric: <1% (No Impact) | 1-3% (Low) | 3-6% (Moderate) | 6-10% (High) | >10% (Severe)
- 2.6% → falls in 1-3% band → **Score: 2 (Low)**

**Step 5 — Resolution:** The cost increase metric gives Score 3, the margin metric gives Score 2. Take the HIGHER of the two for the primary dimension → **Impact Score: 3 (Moderate)**

**Step 6 — Secondary impacts:** Operating (supply chain replanning), Customer & Market (potential price increases to customers), Regulatory (trade compliance obligations). Noted but not scored here.

**Final output:**
```
Impact Score: 3 (Moderate)
Dimension: Financial & Growth Impact
Sub-Dimension: Cost Structure
Metric: Raw Material & Energy Cost Inflation
Justification: 25% tariff on auto imports affecting approximately 30% of cost base 
  results in ~7.5% effective cost increase. Table criteria for Moderate: 5-10%.
Table Criteria Matched: "5-10% cost increase"
```
