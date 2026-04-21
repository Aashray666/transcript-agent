# Risk Scoring Audit Report — VelocityAuto Group

**Total Risks Scored:** 16
**Distribution:** Critical=6, High=7, Medium=3, Low=0
**Average Confidence:** MEDIUM

## Risk Matrix Summary

| Rank | Risk ID | Description | Impact | Likelihood | Inherent | Rating | Confidence |
|------|---------|-------------|--------|------------|----------|--------|------------|
| 1 | RISK_003 | Supply chain risk | 5 (Severe/Catastrophic) | 4 (Likely) | 20 | Critical | MEDIUM |
| 2 | RISK_013 | Logistics and port infrastructure disruption risk | 5 (Severe/Catastrophic) | 4 (Likely) | 20 | Critical | HIGH |
| 3 | RISK_014 | Cyber and technology risk | 5 (Severe/Catastrophic) | 4 (Likely) | 20 | Critical | HIGH |
| 4 | RISK_001 | EV transition risk | 4 (High) | 4 (Likely) | 16 | Critical | MEDIUM |
| 5 | RISK_002 | Tariffs and trade policy | 4 (High) | 4 (Likely) | 16 | Critical | MEDIUM |
| 6 | RISK_017 | Operational risk | 4 (High) | 4 (Likely) | 16 | Critical | MEDIUM |
| 7 | RISK_009 | Product safety and recall risk | 5 (Severe/Catastrophic) | 3 (Possible) | 15 | High | MEDIUM |
| 8 | RISK_004 | Software and technology risk | 4 (High) | 3 (Possible) | 12 | High | MEDIUM |
| 9 | RISK_005 | Dealer network disruption | 4 (High) | 3 (Possible) | 12 | High | MEDIUM |
| 10 | RISK_008 | Geopolitical risk | 4 (High) | 3 (Possible) | 12 | High | MEDIUM |
| 11 | RISK_010 | Financial risk | 4 (High) | 3 (Possible) | 12 | High | MEDIUM |
| 12 | RISK_012 | Raw material dependency | 4 (High) | 3 (Possible) | 12 | High | MEDIUM |
| 13 | RISK_016 | Competition and market risk | 4 (High) | 3 (Possible) | 12 | High | MEDIUM |
| 14 | RISK_006 | Workforce transformation | 2 (Low) | 4 (Likely) | 8 | Medium | MEDIUM |
| 15 | RISK_007 | Regulatory compliance | 4 (High) | 2 (Unlikely) | 8 | Medium | MEDIUM |
| 16 | RISK_011 | Labour and industrial relations | 2 (Low) | 4 (Likely) | 8 | Medium | MEDIUM |

---

## Detailed Risk Scoring Justifications

### RISK_003: Supply chain risk

**Inherent Risk Score: 20 (Critical)**

#### Impact: 5/5 (Severe/Catastrophic)
- **Dimension:** Operating Impact
- **Sub-Dimension:** Critical Supplier Disruption
- **Metric:** Days
- **Table Criteria Matched:** >14 days = Severe/Catastrophic (5)
- **Justification:** The risk of supply chain disruption, particularly with battery cells, could lead to a significant production downtime. The client has mentioned that 'a battery supplier disruption due to geopolitical event' could impact their vehicle programs immediately. Given the client's high dependence on a small number of Asian cell manufacturers and the geopolitical dimension of this concentration, the potential disruption could last more than 14 days, which according to the table, corresponds to a Severe/Catastrophic impact.

#### Likelihood: 4/5 (Likely)
- **Evidence Basis:** BOTH
- **Table Criteria Matched:** Occurred in the last 1-2 years, or multiple times historically. Active external drivers present.
- **Justification:** The likelihood assessment is based on the composite likelihood score of 4/5 provided by the Likelihood Intelligence Agent. The client's history of supply chain disruptions, such as the semiconductor shortage in 2023, and the current geopolitical tensions support this likelihood score.

#### Supporting Evidence
- **Evidence Summary:** The client's supply chain concentration risk, particularly with battery cells, poses a significant threat to their operations. The evidence from the client interview and external market intelligence supports the likelihood and potential impact of such a disruption.
- **Client Context Used:** The client's revenue split, top suppliers, and business continuity plans were considered in the assessment.
- **Scoring Confidence:** MEDIUM

#### Market Intelligence (EXTERNAL_INTELLIGENCE)
- **Signal:** INCREASING
- **Data Freshness:** 2026-04
- **Recent Peer Incidents:**
  - Disruption hitting Europe's auto factories due to supply shortages
  - Iran conflict could trigger chip, battery shortages for carmakers in Europe
- **Market Trends:**
  - Europe's battery supply chain is shifting to a 'marathon' phase with a need for rapid build-up of local capabilities
  - Consolidation phase in the European battery market with Asian companies leading in cell production capacity
  - Lithium demand boom in 2026 approaching a transformative inflection point with an extraordinary demand surge
  - Supply chain issues in the automotive industry in 2026 due to causes like unexpected snapback in consumer demand
- **Sources (10):**
  - https://www.automotivelogistics.media/ev-and-battery/europes-battery-supply-chain-shifts-to-marathon-phase/2635289
  - https://www.ess-news.com/2026/03/09/battery-atlas-2026-launches-with-comprehensive-map-of-europes-cell-pack-and-battery-manufacturers/
  - https://www.mckinsey.com/features/mckinsey-center-for-future-mobility/our-insights/the-hidden-trends-in-battery-supply-and-demand-a-regional-analysis
  - https://www.autonews.com/manufacturing/automakers/ane-europe-iran-war-automaker-risk-0320/
  - https://www.woodmac.com/news/opinion/ev-and-battery-supply-chain-2026-outlook/
- **Search Queries Used:** European automotive battery cell supply chain risks 2026; lithium ion battery raw material shortages 2025 2026; automotive OEM supply chain disruption Europe 2026

#### Consistency Notes
The score is consistent with the previously scored risks, such as RISK_001 and RISK_002, which also have a high impact and likelihood due to the client's exposure to supply chain disruptions and geopolitical risks.

#### Cascade Relationships
- Upstream: RISK_001, RISK_002
- Downstream: RISK_004, RISK_006

---

### RISK_013: Logistics and port infrastructure disruption risk

**Inherent Risk Score: 20 (Critical)**

#### Impact: 5/5 (Severe/Catastrophic)
- **Dimension:** Operating Impact
- **Sub-Dimension:** Logistics
- **Metric:** Inbound / Outbound Logistics Disruption (Days)
- **Table Criteria Matched:** 5-10 days = High
- **Justification:** The client's reliance on specific port infrastructure and rail connections for just-in-time delivery, combined with the history of logistics disruptions such as the Red Sea shipping rerouting in 2024, which resulted in EUR 30M in expedited air freight costs, indicates a high potential for significant logistics disruption. The evidence suggests that the client's supply chain is not adequately tested for multi-node simultaneous disruptions, increasing the risk of prolonged logistics disruptions.

#### Likelihood: 4/5 (Likely)
- **Evidence Basis:** BOTH
- **Table Criteria Matched:** Occurred in the last 1-2 years, or multiple times historically. Active external drivers present.
- **Justification:** The composite likelihood score of 4/5, based on historical frequency, control effectiveness, external environment, sector base rate, and client-specific exposure, indicates a likely occurrence of logistics and port infrastructure disruption. The client's experience with logistics disruption in 2024 and the current external environment of European port congestion and labor action support this likelihood.

#### Supporting Evidence
- **Evidence Summary:** The client's logistics and port infrastructure disruption risk is supported by strong evidence, including the client's history of logistics disruptions, the current external environment, and the lack of comprehensive testing of the client's supply chain.
- **Client Context Used:** The client's reliance on specific port infrastructure, hybrid production model, and history of logistics disruptions.
- **Scoring Confidence:** HIGH

#### Market Intelligence (EXTERNAL_INTELLIGENCE)
- **Signal:** INCREASING
- **Data Freshness:** 2026-04
- **Recent Peer Incidents:**
  - European port congestion led to Maersk removing Rotterdam from its TA5 transatlantic rotation in June 2025
  - Snow and ice disruptions in European ports in early 2026 drove up freight rates
  - Semiconductor shortage impacted automotive manufacturing, with companies like Peugeot using analogue speedometers instead of digital displays
- **Regulatory Developments:**
  - New U.S. tariffs on OEM and aftermarket auto manufacturing, which may impact international supply chains
- **Market Trends:**
  - Escalating disruptions in European ports due to labor action, inland access issues, and alliance transition spillovers
  - Growing demand for automotive semiconductors, leading to shortages and production delays
  - Automotive logistics market projected to grow from $317.29 billion in 2024 to $437.80 billion by 2029
- **Sources (10):**
  - https://blogs.tradlinx.com/how-bad-is-european-port-congestion-really-in-late-2025/
  - https://blogs.tradlinx.com/european-port-crisis-2025-a-comprehensive-operational-breakdown/
  - https://container-mag.com/2026/01/11/european-port-disruptions-freight-rate-surges-2026/
  - https://www.searates.com/blog/post/shipping-crisis-in-european-ports-in-summer-2025-navigate-delays-and-optimize-logistics-costs
  - https://blog.thecooperativelogisticsnetwork.com/2025/07/17/port-congestion-in-europe-2025/
- **Search Queries Used:** European port infrastructure disruption 2025 2026; Automotive semiconductor shortage Europe 2025 2026; Global logistics disruption impact on automotive OEMs 2026

#### Consistency Notes
This risk is consistent with previously scored risks, such as RISK_003 (Supply chain risk) and RISK_008 (Geopolitical risk), which also have high likelihood and impact scores.

#### Cascade Relationships
- Upstream: RISK_003, RISK_008
- Downstream: RISK_005, RISK_014

---

### RISK_014: Cyber and technology risk

**Inherent Risk Score: 20 (Critical)**

#### Impact: 5/5 (Severe/Catastrophic)
- **Dimension:** Technology & Information Impact
- **Sub-Dimension:** Cyber Security
- **Metric:** Industrial Cyber Incident Severity (% of lines affected)
- **Table Criteria Matched:** >50% of lines affected
- **Justification:** The client has experienced a ransomware incident at one of their tier-one suppliers last year, and they have approximately 2.8 million connected vehicles on the road. The cyber posture of their supply chain is genuinely opaque, and they have never tested the connected vehicle response scenario or a manufacturing OT incident. This suggests a high likelihood of a severe cyber incident.

#### Likelihood: 4/5 (Likely)
- **Evidence Basis:** BOTH
- **Table Criteria Matched:** Occurred in the last 1-2 years, or multiple times historically. Active external drivers present.
- **Justification:** The client has experienced a ransomware incident at one of their tier-one suppliers last year, and they have a partially tested cyber incident response plan. The external environment contains active drivers, such as regulatory mandates and trends in connected vehicles.

#### Supporting Evidence
- **Evidence Summary:** The client has experienced a ransomware incident, has a partially tested cyber incident response plan, and has approximately 2.8 million connected vehicles on the road. The cyber posture of their supply chain is genuinely opaque.
- **Client Context Used:** Client questionnaire, interview transcript
- **Scoring Confidence:** HIGH

#### Market Intelligence (EXTERNAL_INTELLIGENCE)
- **Signal:** INCREASING
- **Data Freshness:** 2026-04
- **Regulatory Developments:**
  - 2019/2144 mandates stringent cybersecurity requirements for new vehicles, including secure software updates and risk-based security measures
- **Market Trends:**
  - 70% of drivers say they might consider buying older, less connected vehicles to lower their cybersecurity risk
  - Growing challenges for increasingly connected vehicles, including how to future-proof vehicle and software architectures
- **Sources (10):**
  - https://www.linkedin.com/pulse/france-inbound-manufacturing-automobile-oem-market-3nroc
  - https://www.youtube.com/watch?v=VuWwC3OkYjs
  - https://www.theautochannel.com/news/2021/02/05/956474-automotive-oem-cyber-security-layout-report-2020-focus-european-and.html
  - https://autovista24.autovistagroup.com/news/the-automotive-update-contrasting-fortunes-for-europes-major-new-car-markets/
  - https://vk.com/video-226890944_456239122
- **Search Queries Used:** Automotive OEM cybersecurity incidents Europe 2025 2026; Connected vehicle software update risks 2025 2026; Semiconductor shortage impact automotive manufacturing 2026

#### Consistency Notes
This risk is consistent with previously scored risks, such as RISK_003 and RISK_004, which also have high impact and likelihood scores.

#### Cascade Relationships
- Upstream: RISK_003, RISK_004
- Downstream: RISK_009, RISK_013

---

### RISK_001: EV transition risk

**Inherent Risk Score: 16 (Critical)**

#### Impact: 4/5 (High)
- **Dimension:** Financial & Growth Impact
- **Sub-Dimension:** Revenue Decline (% of total revenue)
- **Metric:** Revenue Decline (%)
- **Table Criteria Matched:** 6-12% revenue decline
- **Justification:** The client has mentioned a significant slowdown in consumer adoption in their core markets, which could lead to a revenue decline. Given the client's annual revenue trend is declining (EUR 82.1B, EUR 80.6B, EUR 78.4B), a further decline due to slowed EV adoption could be significant. The EV transition investment of EUR 8.2B over 2024-2028 and the strategic priority to accelerate EV platform launch indicate a high exposure to this risk.

#### Likelihood: 4/5 (Likely)
- **Evidence Basis:** BOTH
- **Table Criteria Matched:** Occurred in the last 1-2 years, or multiple times historically. Active external drivers present.
- **Justification:** The likelihood intelligence agent has computed a 5-factor composite score of 4/5. The client's current situation with slowed consumer adoption and internal conversations about adjusting their EV transition roadmap supports this likelihood score.

#### Supporting Evidence
- **Evidence Summary:** The client has invested heavily in EV transition and faces a significant slowdown in consumer adoption, which could lead to revenue decline and impact their strategic priorities.
- **Client Context Used:** EV transition investment, annual revenue trend, strategic priority to accelerate EV platform launch
- **Scoring Confidence:** MEDIUM

#### Market Intelligence (EXTERNAL_INTELLIGENCE)
- **Signal:** INCREASING
- **Data Freshness:** 2026-04
- **Regulatory Developments:**
  - European emission standards Euro 7 to come into force in 2026
  - Revision of the car CO2 regulation
- **Market Trends:**
  - Growing demand for EVs in Europe
  - Expansion of charging infrastructure
  - Increasing importance of software in the automotive industry
- **Sources (10):**
  - https://obdeleven.com/automotive-trends-and-stats
  - https://autovista24.autovistagroup.com/news/will-european-ev-registrations-surge-in-2025/
  - https://autovista24.autovistagroup.com/news/europe-2026-automotive-forecast/
  - https://futuretransport-news.com/move-2025-europes-ev-adoption-boom/
  - https://dealerbox.net/5-automotive-trends-you-cant-miss-in-2026/
- **Search Queries Used:** European automotive EV adoption trends 2025 2026; EU automotive electrification regulation compliance 2026; Global lithium battery supply chain risks 2025

#### Consistency Notes
This risk score is consistent with the likelihood of the client facing challenges in their EV transition due to market conditions.

#### Cascade Relationships
- Upstream: RISK_002, RISK_003
- Downstream: RISK_004, RISK_006

---

### RISK_002: Tariffs and trade policy

**Inherent Risk Score: 16 (Critical)**

#### Impact: 4/5 (High)
- **Dimension:** Financial & Growth Impact
- **Sub-Dimension:** Cost Structure
- **Metric:** Raw Material & Energy Cost Inflation (% cost increase)
- **Table Criteria Matched:** 10-20% cost increase = High (4)
- **Justification:** The client stated that the 25% tariffs on auto imports have directly hit their cost structure. Given the annual revenue of EUR 78.4 billion and the mention of significant North American exposure, a 25% tariff would likely result in a substantial cost increase, potentially exceeding 10% of their cost structure.

#### Likelihood: 4/5 (Likely)
- **Evidence Basis:** BOTH
- **Table Criteria Matched:** Occurred recently, active external drivers, weak controls = Likely (4)
- **Justification:** The likelihood intelligence agent has computed a 5-factor composite score of 4/5, indicating that the risk is likely to occur. The client has already experienced the impact of tariffs, and there are active external drivers such as the USMCA review in 2026.

#### Supporting Evidence
- **Evidence Summary:** The client has significant North American exposure and has already been impacted by the 25% tariffs on auto imports. There are active external drivers such as the USMCA review in 2026, which could further exacerbate the risk.
- **Client Context Used:** Annual revenue of EUR 78.4 billion, significant North American exposure, and EBITDA margin of 9.2%.
- **Scoring Confidence:** MEDIUM

#### Market Intelligence (EXTERNAL_INTELLIGENCE)
- **Signal:** INCREASING
- **Data Freshness:** 2026-04
- **Recent Peer Incidents:**
  - U.S. Government to Refund $20 Billion in Tariffs Following Supreme Court Ruling
  - Nissan promised to keep new car prices stable in the earlier part of the year, but costs are expected to rise in late 2025 or early 2026
  - Volkswagen will not raise new car prices amid consumer concerns over tariff impacts
- **Regulatory Developments:**
  - US tariffs on the automotive industry
  - Section 232 tariffs on vehicles and parts will remain
  - USMCA review in 2026
- **Market Trends:**
  - Impact of US tariffs on European automotive sector could be significant
  - German and Italian automotive exports could fall by 7.1% and 6.6% due to tariffs
  - Mexican auto industry remains strong with USMCA compliance, export growth, and resilient sales
- **Sources (10):**
  - https://www.automotivelogistics.media/supply-chain/tariff-analysis-deep-dive-the-most-important-changes-for-the-auto-industry/663875
  - https://digitaldealer.com/news/us-tariff-tracker-impact-automaker-response/164521/
  - https://www.rabobank.com/knowledge/d011480100-assessing-the-impact-of-us-tariffs-on-the-european-automotive-sector
  - https://www.jpmorgan.com/insights/global-research/autos/auto-tariffs
  - https://www.oxfordeconomics.com/resource/driving-into-uncertainty-how-trumps-tariffs-could-derail-europes-automotive-powerhouse/
- **Search Queries Used:** US auto tariffs impact on European OEMs 2026; Automotive trade policy updates USA Mexico 2025 2026; EU US automotive tariff effects on supply chain 2026

#### Consistency Notes
This risk is consistent with RISK_001, which also has a high impact and likelihood score.

#### Cascade Relationships
- Upstream: RISK_001, RISK_003
- Downstream: RISK_006, RISK_008

---

### RISK_017: Operational risk

**Inherent Risk Score: 16 (Critical)**

#### Impact: 4/5 (High)
- **Dimension:** Regulatory & Compliance Impact
- **Sub-Dimension:** Product Safety Non-Compliance
- **Metric:** % of products
- **Table Criteria Matched:** 5-10% = High
- **Justification:** The client has mentioned 'warranty and recall provisions — these are financial liabilities that can crystallize quickly and at scale if a product quality issue emerges, as we experienced with the ADAS recall'. This indicates a history of product safety issues, and with the emergence of data privacy regulations affecting connected vehicles, there is a potential for increased regulatory scrutiny. The client's annual revenue is EUR 78.4 billion, and a product recall could potentially impact a significant portion of this revenue.

#### Likelihood: 4/5 (Likely)
- **Evidence Basis:** BOTH
- **Table Criteria Matched:** Occurred recently, active external drivers, weak controls
- **Justification:** The likelihood intelligence agent has computed a 5-factor composite score of 4/5, indicating a likely occurrence. The client has experienced an ADAS recall in the past, and the external environment is driving this risk with emerging data privacy regulations and tightening regulatory requirements.

#### Supporting Evidence
- **Evidence Summary:** The client has a history of product safety issues, and emerging data privacy regulations may increase regulatory scrutiny. The client's annual revenue is significant, and a product recall could potentially impact a large portion of this revenue.
- **Client Context Used:** Annual revenue, history of product safety issues, emergence of data privacy regulations
- **Scoring Confidence:** MEDIUM

#### Market Intelligence (EXTERNAL_INTELLIGENCE)
- **Signal:** INCREASING
- **Data Freshness:** 2026-04
- **Regulatory Developments:**
  - California Privacy Protection Agency (CPPA) enforcement division reviewing data privacy practices of connected vehicle manufacturers
  - EU reviewing broader automotive policies, including potential ban on new combustion-engine vehicle sales
- **Market Trends:**
  - Growing demand for Automotive OEM Telematics, with expected market size of USD 80 billion by 2033
  - Increasing focus on data privacy and security in connected vehicles
- **Sources (10):**
  - https://thinglabs.io/data-privacy-and-your+connected-car-everything-you-need-to-know
  - https://fpf.org/blog/privacy-and-the-connected-vehicle-a-global-event/
  - https://www.fleetpoint.org/autonomous-vehicles/connected-vehicles/connected-cars-safety-gained-or-safety-lost/
  - https://www.techdirt.com/tag/vehicles/
  - https://www.technologyforyou.org/connected-cars-safety-gained-or-safety-lost/
- **Search Queries Used:** connected vehicle data privacy regulations Europe 2025 2026; automotive OEM cybersecurity incidents Germany UK 2025; EU automotive warranty recall provisions 2026 operational risk

#### Consistency Notes
This risk is consistent with previously scored risks, such as RISK_009: Product safety and recall risk, which also had a high impact and likelihood score.

#### Cascade Relationships
- Upstream: RISK_007: Regulatory compliance, RISK_009: Product safety and recall risk
- Downstream: RISK_010: Financial risk, RISK_012: Raw material dependency

---

### RISK_009: Product safety and recall risk

**Inherent Risk Score: 15 (High)**

#### Impact: 5/5 (Severe/Catastrophic)
- **Dimension:** Regulatory & Compliance Impact
- **Sub-Dimension:** Product Safety
- **Metric:** Product Safety Non-Compliance (% of products)
- **Table Criteria Matched:** Product Safety Non-Compliance (% of products): 5-Severe/Catastrophic: >10% / recall
- **Justification:** The risk of product safety and recall has a significant impact on the company's regulatory and compliance standing. The evidence shows that the company had a product recall in 2024 due to a software defect in an ADAS feature across approximately 180,000 vehicles, resulting in a substantial recall cost and reputational damage. Given the company's exposure to product safety risk with 62% of their vehicles being ICE vehicles and 14% being Electric/hybrid vehicles, the potential for non-compliance is high.

#### Likelihood: 3/5 (Possible)
- **Evidence Basis:** BOTH
- **Table Criteria Matched:** Likelihood 3: Possible, some history at peers, partial controls exist
- **Justification:** The likelihood assessment is based on the composite likelihood score of 3/5, which takes into account the historical frequency of the risk, control effectiveness, external environment, sector base rate, and client-specific exposure. The client's ERM framework and crisis management plan are in place, but the external environment and sector base rate suggest a moderate likelihood of the risk occurring.

#### Supporting Evidence
- **Evidence Summary:** The evidence summary includes the client's statement on product safety and recall risk, the company's history of product recall in 2024, and the external market intelligence on European automotive product recall activity.
- **Client Context Used:** The client context used includes the company's financial exposure, EBITDA margin, net debt/EBITDA ratio, and controls in place.
- **Scoring Confidence:** MEDIUM

#### Market Intelligence (EXTERNAL_INTELLIGENCE)
- **Signal:** INCREASING
- **Data Freshness:** 2026-04
- **Recent Peer Incidents:**
  - European automotive product recall activity reached an all-time high in 2025 with 900 events across EU and UK markets, up 34.5% from the previous record
  - 15,608 recalls were recorded in 2025, surpassing the previous record of 14,484 events set in 2024
- **Regulatory Developments:**
  - New Vehicle General Safety Regulation 2 (GSR2) sets rules for EU car safety features
  - Euro 7 emissions standards to come into force for new light vehicles on 29 November 2026
  - European Commission's postponement of Euro 7 proposal details
- **Market Trends:**
  - European product recall activity increased for the seventh consecutive year in 2025
  - Automotive recall risk is not easing, with 2025 delivering a clear message of increased recall risk
  - Growing demand for Advanced Driver Assistance Systems (ADAS) and autonomous technology in the European market
- **Sources (10):**
  - https://car-recalls.eu/
  - https://www.sedgwick.com/press-release/european-recall-activity-reaches-new-highs-amid-regulatory-reform-and-market-complexity/
  - https://www.claimsjournal.com/news/national/2026/03/05/336030.htm
  - https://www.rqa-group.com/new-release-rqa-groups-product-recall-report-2025/
  - https://www.tmhcc.com/en/news-and-articles/thought-leadership/automotive-recall-risk-in-2025-why-the-trend-isnt-slowing-down
- **Search Queries Used:** European automotive product safety recalls 2025 2026; EU Euro 7 emissions compliance challenges 2026; Automotive ADAS software safety risks Europe 2025

#### Consistency Notes
The consistency notes show that the risk rating is consistent with related risks such as RISK_003 (Supply chain risk) and RISK_007 (Regulatory compliance).

#### Cascade Relationships
- Upstream: RISK_003, RISK_014
- Downstream: RISK_001, RISK_005

---

### RISK_004: Software and technology risk

**Inherent Risk Score: 12 (High)**

#### Impact: 4/5 (High)
- **Dimension:** Technology & Information Impact
- **Sub-Dimension:** Cyber Security
- **Metric:** Industrial Cyber Incident Severity (% of lines affected)
- **Table Criteria Matched:** 25-50% of lines affected
- **Justification:** The client's lagging software development capability, cybersecurity exposure in connected vehicles, and the increasing trend of ransomware attacks on automotive and smart mobility indicate a high impact on technology and information. The evidence suggests that the client is accumulating liability exposure that cannot be fully quantified yet, and the capital commitment to address technology risk is large.

#### Likelihood: 3/5 (Possible)
- **Evidence Basis:** BOTH
- **Table Criteria Matched:** Has occurred before at the company or regularly at peers
- **Justification:** The likelihood intelligence agent has computed a 5-factor composite score of 3/5, indicating a possible likelihood. The client's dedicated Global Cybersecurity team and annual cybersecurity spend of EUR 142M suggest some level of control effectiveness, but the external environment presents active drivers, such as increasing ransomware attacks and regulatory changes.

#### Supporting Evidence
- **Evidence Summary:** The client's software and technology risk is driven by lagging software development capability, cybersecurity exposure, and increasing reliance on software-defined vehicles. The external environment presents active drivers, such as ransomware attacks and regulatory changes.
- **Client Context Used:** Client Questionnaire Context, External Market Intelligence
- **Scoring Confidence:** MEDIUM

#### Market Intelligence (EXTERNAL_INTELLIGENCE)
- **Signal:** INCREASING
- **Data Freshness:** 2026-04
- **Recent Peer Incidents:**
  - Ransomware attacks on automotive and smart mobility more than doubled in 2025
  - Automotive cyber incidents are increasingly escalating beyond individual systems and teams to impact entire organizations
- **Regulatory Developments:**
  - EU Auto Cybersecurity Regulations 2026: NIS2, DORA & Compliance Guide
  - EU Compliance 2026: What Automakers and Importers Must Know
  - Cyber Resilience Act: Impact on the Automotive Industry
  - EU: Adoption of cybersecurity rules for L-category vehicles
- **Market Trends:**
  - The automotive industry is changing faster than ever, with smarter factories, connected vehicles, digital supply chains, and software-driven everything
  - Connected vehicles are shifting from peripheral to primary targets in cybercriminal business models
  - Italy Automotive Software Development And Engineering Services Market is expected to grow from USD 15.2 billion in 2024 to USD 39 billion in 2033
- **Sources (10):**
  - https://www.automotivetestingtechnologyinternational.com/news/test-facilities/toyota-motor-europe-opens-digital-hub-in-wroclaw.html
  - https://www.linkedin.com/pulse/italy-automotive-software-development-engineering-cfjre
  - https://www.th-deg.de/ase-m-en
  - https://andersenlab.com/
  - https://hackernoon.com/10-best-automobile-software-development-companies-worldwide-204434dg
- **Search Queries Used:** automotive software development capability Europe 2025 2026; connected vehicle cybersecurity incidents automotive OEM 2026; EU automotive cybersecurity regulations compliance 2025 2026

#### Consistency Notes
The score is consistent with related risks, such as RISK_001 (EV transition risk) and RISK_003 (supply chain risk), which also have high impact and likelihood scores.

#### Cascade Relationships
- Upstream: RISK_001, RISK_003
- Downstream: RISK_005, RISK_007

---

### RISK_005: Dealer network disruption

**Inherent Risk Score: 12 (High)**

#### Impact: 4/5 (High)
- **Dimension:** Financial & Growth Impact
- **Sub-Dimension:** Revenue Decline
- **Metric:** Revenue Decline (%)
- **Table Criteria Matched:** 6-12% = High
- **Justification:** The shift to direct-to-consumer models by some competitors, particularly EV-native brands, is creating pressure on the traditional dealer model. The client's significant investment in their traditional dealer network and their declining market share in Europe and China make them more exposed to this risk. According to the client's revenue figures, a potential loss of 6% of their total revenue (EUR 78.4 billion) due to dealer network disruption would be a significant impact.

#### Likelihood: 3/5 (Possible)
- **Evidence Basis:** BOTH
- **Table Criteria Matched:** Has occurred before at peers, external environment contains active drivers
- **Justification:** The likelihood intelligence agent has computed a 5-factor composite score of 3/5. The external environment contains active drivers such as the growing demand for electric vehicles and the trend of direct-to-consumer sales disrupting traditional dealership models. However, the client has had difficult conversations with dealer groups about the future of the relationship, indicating some level of preparedness.

#### Supporting Evidence
- **Evidence Summary:** The client's traditional dealer model is under pressure from the shift to direct-to-consumer models by some competitors, particularly EV-native brands. The client has significant investment in their traditional dealer network and is experiencing declining market share in Europe and China.
- **Client Context Used:** Client questionnaire context: Revenue figures, market share trends, and dealer concentration
- **Scoring Confidence:** MEDIUM

#### Market Intelligence (EXTERNAL_INTELLIGENCE)
- **Signal:** INCREASING
- **Data Freshness:** 2026-04
- **Recent Peer Incidents:**
  - Auto production disrupted by chip shortages
- **Regulatory Developments:**
  - New Mandate for Dealer Security in 2026
- **Market Trends:**
  - Growing demand for electric vehicles
  - Direct-to-consumer sales disrupting traditional dealership models
  - EV sales soaring in Europe
- **Sources (10):**
  - https://www.fixedopsmarketing.com/mercedes-benz-oem-mandates-justin-shanken/
  - https://securityboulevard.com/2024/02/top-cyber-threats-automotive-dealerships-should-look-out-for/
  - https://www.corporatevision-news.com/issues/automotive-awards-2025/
  - https://www.automotiveworld.com/news/bev-sales-soar-in-europe-q1-2026-as-pump-price-shock-persists/
  - https://linkedinbusiness.xyz/auto-production-disrupted-by-chip-shortages.html
- **Search Queries Used:** European automotive dealer network disruption 2025 2026; EV native brands disrupting traditional dealer models 2026; Automotive OEM direct-to-consumer sales trends Europe 2025

#### Consistency Notes
This risk is related to RISK_004 (Software and technology risk) and RISK_013, but the impact dimension differs. The likelihood score is consistent with the composite score from the likelihood intelligence agent.

#### Cascade Relationships
- Upstream: RISK_004
- Downstream: RISK_013

---

### RISK_008: Geopolitical risk

**Inherent Risk Score: 12 (High)**

#### Impact: 4/5 (High)
- **Dimension:** Financial & Growth Impact
- **Sub-Dimension:** Revenue Decline (%)
- **Metric:** Revenue Decline (%)
- **Table Criteria Matched:** 6-12% revenue decline
- **Justification:** The client mentions that the China JV situation could deteriorate rapidly if US-China trade relations escalate further, and the company has significant capital tied up in that structure. An exit or forced restructuring would be very costly. Given the annual revenue of EUR 78.4 billion and the potential loss of a significant joint venture, a revenue decline of 6-12% is plausible, which aligns with the 'High' level.

#### Likelihood: 3/5 (Possible)
- **Evidence Basis:** BOTH
- **Table Criteria Matched:** Has occurred before at peers, external environment contains active drivers
- **Justification:** The likelihood intelligence agent has computed a 5-factor composite score of 3/5. The client has mentioned governance restructuring of the China JV as a control, but there is no indication that these controls have been tested under real conditions. External market intelligence indicates increasing competition from Chinese automakers and potential retaliatory measures by Beijing, which supports the 'Possible' level.

#### Supporting Evidence
- **Evidence Summary:** The client has a significant joint venture in China, which has been one of its most profitable operations historically. However, the market in China has deteriorated sharply, with local EV brands taking enormous market share. The geopolitical dimension between China and Western markets adds uncertainty to the long-term viability of the JV structure.
- **Client Context Used:** Company_JV_in_China, China_Market_Share_Loss, Annual_Revenue_Trend, Exposure_to_China_Market
- **Scoring Confidence:** MEDIUM

#### Market Intelligence (EXTERNAL_INTELLIGENCE)
- **Signal:** INCREASING
- **Data Freshness:** 2026-04
- **Recent Peer Incidents:**
  - Chinese automakers entering the global top 10
  - Leapmotor more than doubling its sales in 2025
- **Regulatory Developments:**
  - China's plan for a more competitive EV market by 2025 and reaching global standards by 2035
  - EU trade relations with China and potential retaliatory measures by Beijing against European firms and products
- **Market Trends:**
  - China's increasing market share in the global automotive market, reaching 35.6% in 2025
  - Growing exports of Chinese-made ICE vehicles challenging traditional automotive production in emerging markets
  - Electric vehicle sales in China increasing by 11.4% in 2025
- **Sources (10):**
  - https://carnewschina.com/2026/02/05/china-accounted-for-35-6-of-the-global-automotive-market-in-2025-a-new-record-high/
  - https://www.mordorintelligence.com/industry-reports/chinese-automotive-market
  - https://www.focus2move.com/chinese-auto-market/
  - https://carnewschina.com/2026/02/26/three-chinese-automakers-enter-global-top-10-as-2025-sales-rankings-finalized/
  - https://www.all-about-industries.com/trends-in-chinas-auto-industry-in-2026-a-ff5ec9071356ceb7a1001a95992f7077/
- **Search Queries Used:** China automotive market share trends 2025 2026; Geopolitical risk impact on EU-China automotive trade 2026; China EV market competition and foreign investment risks 2025

#### Consistency Notes
The score is consistent with related risks, such as RISK_001 (EV transition risk) and RISK_002 (Tariffs and trade policy), which also have a high impact and likelihood score.

#### Cascade Relationships
- Upstream: RISK_001, RISK_002
- Downstream: RISK_003, RISK_006

---

### RISK_010: Financial risk

**Inherent Risk Score: 12 (High)**

#### Impact: 4/5 (High)
- **Dimension:** Financial & Growth Impact
- **Sub-Dimension:** Revenue Decline (% of total revenue)
- **Metric:** Revenue Decline
- **Table Criteria Matched:** 6-12% = High
- **Justification:** The client's annual revenue is EUR 78.4 billion, and a significant shift in major currency pairs could hit their reported margins directly. With a cost base currency mismatch of approximately 30%, the risk of revenue decline is substantial. Considering the evidence of 'cyclicality' and 'automotive demand is fundamentally tied to economic conditions, consumer confidence, and credit availability', a moderate to high revenue decline is possible.

#### Likelihood: 3/5 (Possible)
- **Evidence Basis:** BOTH
- **Table Criteria Matched:** Has occurred in the last 2-5 years at the company, or regularly at sector peers
- **Justification:** The likelihood intelligence agent has computed a 5-factor composite score of 3/5. The client has hedging programs but they don't fully cover beyond 12-18 months, indicating some level of control but with significant gaps. External market intelligence indicates trends such as high financing costs, challenging production environments, and tightening emissions regulations, which could drive this risk.

#### Supporting Evidence
- **Evidence Summary:** The client's financial risk is driven by cyclicality, currency exposure, and commodity prices. The evidence suggests a moderate to high revenue decline is possible, with a likelihood of occurrence rated as possible.
- **Client Context Used:** Annual revenue, revenue trend, EBITDA margin, net debt to EBITDA ratio, and top 5 currencies by revenue exposure
- **Scoring Confidence:** MEDIUM

#### Market Intelligence (EXTERNAL_INTELLIGENCE)
- **Signal:** INCREASING
- **Data Freshness:** 2026-04
- **Regulatory Developments:**
  - European Commission's plans to scrap the strict 2035 deadline for banning new combustion engines
- **Market Trends:**
  - high financing costs and prices continuing to weigh on affordability in the European automotive industry
  - challenging production environment in major global auto markets
  - tightening emissions regulations in Europe
- **Sources (10):**
  - https://www.transportenvironment.org/articles/europes-automotive-industry-at-a-crossroads
  - https://arxiv.org/html/2501.01781v2
  - https://oldfieldpartners.com/publications/investing-in-the-european-automotive-industry-in-an-age-of-disruption/
  - https://storemaxpapis.com/article/global-chip-crisis-how-europe-s-auto-industry-is-affected
  - https://protopapaswines.com/article/europe-s-auto-industry-future-electric-despite-eu-climbdown
- **Search Queries Used:** European automotive industry financial risk 2025 2026; Currency fluctuation impact on automotive manufacturing 2026; Automotive sector debt refinancing trends Europe 2025 2026

#### Consistency Notes
The score is consistent with related risks such as RISK_001 (EV transition risk) and RISK_008 (Geopolitical risk), which also have high inherent risk scores.

#### Cascade Relationships
- Upstream: RISK_017
- Downstream: RISK_001, RISK_008

---

### RISK_012: Raw material dependency

**Inherent Risk Score: 12 (High)**

#### Impact: 4/5 (High)
- **Dimension:** Financial & Growth Impact
- **Sub-Dimension:** Cost Structure
- **Metric:** Raw Material & Energy Cost Inflation (% cost increase)
- **Table Criteria Matched:** 10-20% cost increase = High (4)
- **Justification:** The client's annual revenue is EUR 78.4 billion, and they have a high dependency on raw materials such as steel, aluminum, and battery raw materials. The evidence suggests that the client is exposed to commodity price volatility, which could lead to a significant increase in raw material costs. The client's EBITDA margin is 9.2%, which indicates a moderate level of financial resilience. However, the potential cost increase due to raw material price volatility could erode this margin, leading to a high impact on the client's financial growth.

#### Likelihood: 3/5 (Possible)
- **Evidence Basis:** BOTH
- **Table Criteria Matched:** Occurred in the last 2-5 years at the company, or regularly at sector peers = Possible (3)
- **Justification:** The likelihood intelligence agent has computed a 5-factor composite score of 3/5. The client has experienced a similar risk in the past (the 2023 semiconductor shortage), and there are active external drivers such as supply chain disruptions and fluctuations in raw material prices. However, the client has some controls in place, such as hedging programs, which reduces the likelihood of this risk materializing.

#### Supporting Evidence
- **Evidence Summary:** The client is exposed to commodity price volatility due to their high dependency on raw materials, and they have experienced a similar risk in the past. The client has some controls in place, but the likelihood of this risk materializing is still possible.
- **Client Context Used:** Annual revenue, EBITDA margin, and spend on raw materials
- **Scoring Confidence:** MEDIUM

#### Market Intelligence (EXTERNAL_INTELLIGENCE)
- **Signal:** INCREASING
- **Data Freshness:** 2026-04
- **Regulatory Developments:**
  - European Chips Act to support Europe's semiconductor ecosystem
- **Market Trends:**
  - supply chain disruptions, fluctuations in raw material prices, semiconductor shortage, increasing demand for electric vehicles and lithium-ion batteries
- **Sources (10):**
  - https://www.datainsightsmarket.com/reports/europe-automotive-semiconductor-market-20721
  - https://bisi.org.uk/reports/supply-chain-vulnerabilities-in-europes-semiconductor-industry-amid-the-iran-conflict
  - https://halvernresearch.com/papers/global-semiconductor-supply-chain-2026/
  - https://www.moodys.com/web/en/us/insights/corporations/semiconductors-in-2026-why-supply-chains-are-a-major-bottleneck.html
  - https://www.clepa.eu/insights-updates/position-papers/reinforcing-europes-automotive-semiconductor-supply-chain/
- **Search Queries Used:** European automotive semiconductor supply chain risks 2026; Global lithium battery raw material shortages 2025; EU automotive industry commodity price volatility 2026

#### Consistency Notes
This risk is consistent with previously scored risks such as RISK_003 (Supply chain risk) and RISK_008 (Geopolitical risk), which also have a high impact and possible likelihood.

#### Cascade Relationships
- Upstream: RISK_003, RISK_008
- Downstream: RISK_001, RISK_002

---

### RISK_016: Competition and market risk

**Inherent Risk Score: 12 (High)**

#### Impact: 4/5 (High)
- **Dimension:** Customer & Market Impact
- **Sub-Dimension:** Market Share Loss
- **Metric:** Market Share Loss (% points)
- **Table Criteria Matched:** 5-10% = High
- **Justification:** The client is facing significant competition from Chinese EV manufacturers, particularly BYD, which is vertically integrated and has a different cost structure. The client's EV platform launch is behind schedule, and they are struggling to keep up with the changing market dynamics. The evidence suggests that the client could lose up to 10% of their market share, which would have a significant impact on their revenue and growth.

#### Likelihood: 3/5 (Possible)
- **Evidence Basis:** BOTH
- **Table Criteria Matched:** Has occurred before at the company or regularly at peers
- **Justification:** The likelihood assessment is based on the client's current situation, including their behind-schedule EV platform launch and the increasing competition from Chinese EV manufacturers. The client has acknowledged the threat from these competitors and is trying to catch up, but the likelihood of them succeeding is uncertain.

#### Supporting Evidence
- **Evidence Summary:** The client is facing significant competition from Chinese EV manufacturers, and their EV platform launch is behind schedule. The client has acknowledged the threat from these competitors and is trying to catch up.
- **Client Context Used:** Annual revenue: EUR 78.4 billion, Revenue trend: declining, EBITDA margin: 9.2%, EBITDA trend: declining
- **Scoring Confidence:** MEDIUM

#### Market Intelligence (EXTERNAL_INTELLIGENCE)
- **Signal:** INCREASING
- **Data Freshness:** 2026-04
- **Recent Peer Incidents:**
  - The Netherlands became the first European country to approve Tesla’s Full Self-Driving (Supervised) software on 10 April 2026
- **Regulatory Developments:**
  - EU Emission Rules 2026 will reshape electric cars in Europe, impact prices, charging, car brands, and the future of petrol vehicles
  - New rules for measuring electric vehicle charging and hydrogen refilling stations entered into force in the EU on 9 April 2026
  - The amended Measuring Instruments Directive ensures accurate and reliable measurements for electric vehicle charging and hydrogen refilling stations
- **Market Trends:**
  - Production of new cars is expected to start growing again in Europe, with 2.4% growth in 2026
  - The European automotive market saw a 0.9% increase in new car sales in 2024, with 14.17 million units sold
  - Electric vehicle adoption and digital transformation are key trends shaping the UK and European automotive industries in 2026
- **Sources (10):**
  - https://www.acea.auto/publication/the-automobile-industry-pocket-guide-2025-2026/
  - https://www.oxfordeconomics.com/resource/europe-automotive-sector-industry-outlook-2026-and-beyond/
  - https://www.coxautoinc.eu/news-insights/automotive-industry-trends-2026/
  - https://www.kearney.com/industry/automotive/article/kearney-strategic-automotive-radar-q3-2025
  - https://www.focus2move.com/european-car-market/
- **Search Queries Used:** EU automotive market competition trends 2025 2026; European electric vehicle regulatory updates 2026; Automotive OEM software validation challenges Europe 2025

#### Consistency Notes
The score is consistent with previously scored risks, such as RISK_003 and RISK_004, which also relate to the client's competitive position and market share.

#### Cascade Relationships
- Upstream: RISK_003, RISK_004
- Downstream: RISK_005, RISK_006

---

### RISK_006: Workforce transformation

**Inherent Risk Score: 8 (Medium)**

#### Impact: 2/5 (Low)
- **Dimension:** People, Health & Safety Impact
- **Sub-Dimension:** Labour Relations
- **Metric:** Industrial Action / Strikes (Days)
- **Table Criteria Matched:** 5-10 days = High
- **Justification:** The risk of workforce transformation is expected to cause significant labour relations friction, with a high likelihood of industrial action. The client has already experienced a 2-day warning strike in Germany and a 1-day work stoppage in the UK. With 68% of the workforce unionized overall and 82% in Germany, the potential for further industrial action is high.

#### Likelihood: 4/5 (Likely)
- **Evidence Basis:** BOTH
- **Table Criteria Matched:** Occurred in the last 1-2 years, or multiple times historically. Active external drivers present.
- **Justification:** The likelihood intelligence agent has computed a 5-factor composite score of 4/5, indicating a high likelihood of this risk occurring. The client's history of industrial action, the high percentage of unionized workforce, and the external environment of slow-build risks all contribute to this likelihood.

#### Supporting Evidence
- **Evidence Summary:** The client's workforce transformation is expected to cause significant labour relations friction, with a high likelihood of industrial action. The client has already experienced strikes and has a high percentage of unionized workforce.
- **Client Context Used:** Workforce transformation, unionized workforce percentage, industrial action history
- **Scoring Confidence:** MEDIUM

#### Market Intelligence (EXTERNAL_INTELLIGENCE)
- **Signal:** INCREASING
- **Data Freshness:** 2026-04
- **Recent Peer Incidents:**
  - UK automotive jobs at risk without urgent ZEV mandate reforms
  - Unite leader calls for greater support for automotive industry
  - UK Car Industry Seeks Changes to EU’s ‘Made in Europe’ Agenda
  - NAECI Pay Negotiations 2026 & Resulting Offer
- **Regulatory Developments:**
  - Changes to trade union law under the Employment Rights Act 2025 (ERA 2025)
  - Proposed law that will discriminate against British automobile manufacturers and undermine €80 billion ($94 billion) of annual trade
- **Market Trends:**
  - Electric vehicles and software-defined platforms introducing a new layer of technical complexity across the automotive value chain
  - Rapid rise of EV production offers opportunities for reskilling and transitioning to high-demand roles in battery manufacturing, software development, and charging infrastructure maintenance
  - Seven in ten executives expect AI agents taking independent action by the end of 2026
- **Sources (10):**
  - https://taggd.in/blogs/automotive-workforce-transformation/
  - https://www.linkedin.com/pulse/workforce-transformation-trends-2026-why-we-forget-pocstar-ph-d--drh4f
  - https://htn.co.uk/2025/02/19/panel-discussion-successful-nhs-workforce-transformation-key-factors-for-success-overcoming-challenges-ensuring-sustainable-workforce-transformation-and-securing-buy-in/
  - https://www.weforum.org/publications/the-future-of-jobs-report-2025/
  - https://www.workforceaustralia.gov.au/
- **Search Queries Used:** German automotive workforce transformation challenges 2025 2026; UK union negotiations automotive industry 2025 2026; European automotive OEM EV transition labour relations 2026

#### Consistency Notes
This risk is consistent with previously scored risks, such as RISK_001 (EV transition risk) and RISK_003 (Supply chain risk), which also have high likelihood scores due to the client's history of industrial action and the external environment of slow-build risks.

#### Cascade Relationships
- Upstream: RISK_001, RISK_003
- Downstream: RISK_002, RISK_005

---

### RISK_007: Regulatory compliance

**Inherent Risk Score: 8 (Medium)**

#### Impact: 4/5 (High)
- **Dimension:** Regulatory & Compliance Impact
- **Sub-Dimension:** Sanctions
- **Metric:** Regulatory Fines / Penalties (% of annual revenue)
- **Table Criteria Matched:** 1-3% of annual revenue
- **Justification:** The client mentions that the cost of compliance per vehicle is significant and they are having to decide which models to carry forward and which to discontinue. The EU's 2035 ICE ban and the new emissions standards create a tight compliance window. Given the annual revenue of EUR 78.4B, a potential fine of up to 10% of global turnover for non-compliance with EU's Corporate regulations could result in a substantial financial impact.

#### Likelihood: 2/5 (Unlikely)
- **Evidence Basis:** BOTH
- **Table Criteria Matched:** No history of occurrence at the company or close peers
- **Justification:** The likelihood intelligence agent has computed a 5-factor composite score of 2/5. The client has a formal regulatory intelligence function within the Legal department, monitored monthly with quarterly board reporting, which suggests some level of control over regulatory compliance.

#### Supporting Evidence
- **Evidence Summary:** The client is facing regulatory compliance risks due to tightening emissions standards and potential fines for non-compliance.
- **Client Context Used:** The client's annual revenue, EBITDA margin, and net debt/EBITDA ratio were considered.
- **Scoring Confidence:** MEDIUM

#### Market Intelligence (EXTERNAL_INTELLIGENCE)
- **Signal:** INCREASING
- **Data Freshness:** 2026-04
- **Regulatory Developments:**
  - Euro 7 emission standards to be enforced in 2026, including non-exhaust emissions and cybersecurity requirements
  - United States vehicle emission standards updated in 2021 and 2025
  - EU's Corporate regulations with fines up to 10% of global turnover for non-compliance
- **Market Trends:**
  - Increased focus on decarbonising road transport to achieve climate neutrality by 2050
  - Transition from BS6 to BS7 emissions norms in India
- **Sources (10):**
  - https://en.wikipedia.org/wiki/European_emission_standards
  - https://vicone.com/blog/how-the-euro-7-emissions-regulation-redefines-compliance-for-the-automotive-industry
  - https://www.acea.auto/publication/acea-proposals-for-euro-7-and-euro-vii-emission-standards/
  - https://www.databreachtoday.com/new-european-emissions-regs-include-cybersecurity-rules-a-31019
  - https://www.news18.com/auto/be-ready-for-transition-from-bs6-to-bs7-emissions-norms-dont-wait-for-govt-push-nitin-gadkari-7849363.html
- **Search Queries Used:** Euro 7 emissions regulation automotive compliance 2026; US EPA rules automotive manufacturing emissions standards 2025; EU automotive regulatory compliance fines penalties 2026

#### Consistency Notes
The score is consistent with related risks, such as RISK_004 and RISK_011, which also have a medium risk rating.

#### Cascade Relationships
- Upstream: RISK_004, RISK_011
- Downstream: RISK_017

---

### RISK_011: Labour and industrial relations

**Inherent Risk Score: 8 (Medium)**

#### Impact: 2/5 (Low)
- **Dimension:** People, Health & Safety Impact
- **Sub-Dimension:** Labour Relations
- **Metric:** Industrial Action / Strikes (Days)
- **Table Criteria Matched:** Industrial Action / Strikes (Days): 1-No Impact: 0, 2-Low: <1, 3-Moderate: 1-5, 4-High: 5-10, 5-Severe/Catastrophic: >10
- **Justification:** The client operates with large, heavily unionised workforces in multiple countries, with 68% of their workforce unionized. There were 2 incidents of industrial action in the last 3 years, in Germany and the UK. The voluntary employee turnover rate is 8.2%, and there are active workforce restructuring programmes. Given the high unionization rate and history of industrial actions, the primary impact dimension is People, Health & Safety Impact, specifically Labour Relations.

#### Likelihood: 4/5 (Likely)
- **Evidence Basis:** BOTH
- **Table Criteria Matched:** Likelihood 4: Occurred recently, active external drivers, weak controls
- **Justification:** The likelihood intelligence agent has computed a 5-factor composite score of 4/5. The client's history of industrial actions, high unionization rate, and active workforce restructuring programmes contribute to the likelihood of this risk.

#### Supporting Evidence
- **Evidence Summary:** The client's large, heavily unionised workforces in multiple countries, history of industrial actions, and active workforce restructuring programmes contribute to the high impact and likelihood of this risk.
- **Client Context Used:** Unionized workforce percentage, countries with unionized workforce, industrial action in the last 3 years, voluntary employee turnover rate, and active workforce restructuring programmes
- **Scoring Confidence:** MEDIUM

#### Market Intelligence (EXTERNAL_INTELLIGENCE)
- **Signal:** INCREASING
- **Data Freshness:** 2026-04
- **Recent Peer Incidents:**
  - Major Auto Workers Strike Halts Production at Ford and GM Plants
- **Regulatory Developments:**
  - EU Unveils New Industry Plans to Propel Auto
  - European Commission's ‘Strategic Dialogue on the Future of the Automotive Industry’
- **Market Trends:**
  - Labour market tightening in Hungary, with a shrinking workforce and increasing demand for guest workers
  - European automotive industry facing loss of competitiveness due to costs and regulations
  - Increasing focus on electric vehicle development and battery production
- **Sources (10):**
  - https://www.youtube.com/watch?v=RbCjxOeVDQM
  - https://worldpopulationreview.com/countries/germany
  - https://vk.com/video-226890944_456239122
  - https://shuvo24news.com/major-auto-workers-strike-halts-production/
  - https://www.wto.org/english/tratop_e/dispu_e/dispu_by_country_e.htm
- **Search Queries Used:** Germany UK automotive labour disputes 2025 2026; unionised workforce trends Hungary Mexico automotive 2026; European automotive industry industrial relations challenges 2025

#### Consistency Notes
This risk is consistent with previously scored risks, such as RISK_001 (EV transition risk) and RISK_003 (Supply chain risk), which also have high impact and likelihood scores.

#### Cascade Relationships
- Upstream: RISK_007
- Downstream: RISK_001, RISK_003

---

## Consistency Check Results

**Assessment:** 1 inconsistencies found (1 high severity). Manual review recommended for flagged risks.
**Score Distribution:** {'Low': 0, 'Medium': 3, 'High': 7, 'Critical': 6}

### Flags Raised

- **[HIGH] CASCADE_COHERENCE** — RISK_007: Upstream RISK_011 has Likelihood=4 but downstream RISK_007 has Likelihood=2. Expected ≥3 for cascade coherence.
  - Recommendation: Consider increasing RISK_007 likelihood to at least 3.
