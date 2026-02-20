# Reference Sources

## CMS Primary Sources

- **Physician Fee Schedule RVU Files** (time per procedure, work RVUs):
  https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files

- **CPT/HCPCS Code List (Physician Self-Referral)**:
  https://www.cms.gov/medicare/regulations-guidance/physician-self-referral/list-cpt-hcpcs-codes

- **HCPCS Level II Code Sets** (T-codes, S-codes — billing unit descriptions):
  https://www.hhs.gov/guidance/document/hcpcs-release-code-sets

- **PFS Lookup Tool** (search individual codes for RVUs and payment):
  https://www.cms.gov/medicare/physician-fee-schedule/search

## OIG Fraud References

- **OIG Investigative Advisory — Medicaid Personal Care Services**:
  https://oig.hhs.gov/reports-and-publications/portfolio/mpcs.asp

- **OIG Fraud & Abuse Laws**:
  https://oig.hhs.gov/compliance/physician-education/fraud-abuse-laws/

- **Medicare Fraud Strike Force**:
  https://oig.hhs.gov/fraud/strike-force/

## Whistleblower / False Claims Act

- **OIG Whistleblower Protection Info**:
  https://oig.hhs.gov/fraud/whistleblower/

## Local Reference Files

- `data/reference/rvu25d.zip` — CMS PFS Relative Value File (Oct 2025)
- `data/reference/rvu25c.zip` — CMS PFS Relative Value File (Jul 2025)

# Github Copilot in VS 2026 2/19/2026 GPT-4.1 review of code and approach

Here are further enhancements and new long-tail or outlier fraud pattern ideas for your tool:

Enhancements

Configurable Thresholds & Profiles:

Allow users to set thresholds (e.g., hours, code diversity) per specialty or region.
Support “profiles” for different provider types (e.g., PCP, home health, DME).
Temporal Pattern Analysis:

Detect abrupt billing starts/stops, gaps, or “handoffs” between NPIs at the same address.
Flag providers with highly regular billing (e.g., same amount every month).
Network & Relationship Analysis:

Identify clusters of NPIs sharing addresses, phone numbers, or owners.
Map referral or billing relationships to spot rings or shell entities.
Anomaly Scoring:

Add percentile-based or peer-group scoring (e.g., “top 0.1% for code X in state Y”).
Compare providers to local or specialty-specific norms.
Data Enrichment:

Integrate external watchlists, sanctions, or news feeds for cross-flagging.
Use NPPES taxonomy and enumeration date to flag “fresh” NPIs with high billing.
Explainability & Reporting:

Generate plain-language “why flagged” summaries for each suspect.
Export results with supporting evidence (e.g., code breakdown, time math).
Long-tail/Outlier Fraud Pattern Ideas

“Code Creep”: Gradual shift to higher-paying codes over time (upcoding trend).
“Ghost Clinics”: Providers with high billing but no physical address or phone match.
“Weekend Warriors”: Unusual volume on weekends/holidays for non-emergency codes.
“Beneficiary Overlap”: Multiple providers billing the same small set of patients.
“Geographic Impossibility”: Same provider billing in distant locations within short timeframes.
“New NPI, Old Pattern”: New NPIs that immediately start billing like a known suspect.
“Unusual Code Mix”: Providers billing rare or mismatched code combinations for their taxonomy.
“Billing for the Dead”: Claims for beneficiaries after their recorded date of death (if data available).
“Rapid Enumeration”: Multiple NPIs registered at the same address in a short period, all billing quickly.
These enhancements and patterns will help you catch more subtle, creative, and emerging fraud schemes—especially those missed by standard analytics. Let me know if you want implementation ideas for any of these!

