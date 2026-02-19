# RSL — Rat Scurry Lighting

*Medicaid fraud detection tool targeting patterns nobody else is looking at.*

---

## What This Is

A set of simple Python scripts that take the publicly available CMS Medicaid Provider Spending dataset and find providers whose billing is **physically impossible**, not just statistically unusual.

The big shops build dashboards and heatmaps. The DOGE recruits build impressive pipelines. BI tools find the top spenders. All of that catches the obvious stuff that's probably already flagged.

**RSL finds the longtail:** the solo practitioner who'd need 26 hours in a day, the personal care aide billing for a family member every day for three years, the billing entity running six freshly-minted NPIs through an adult day care mill. These aren't statistical outliers — they're arithmetic impossibilities.

---

## Core Approach: Capacity Simulation

The CMS dataset is aggregated at **NPI x HCPCS code x Month**: total claims, unique beneficiaries, total paid. No individual claim records.

The insight: aggregated data is enough to prove impossibility.

For every provider in a given month, we:
1. Look up each HCPCS code they billed
2. Multiply claims x estimated minutes per procedure (sourced from CMS's own fee schedule)
3. Sum total implied work-hours for that month
4. Compare against physical capacity (22 work days x 14 hrs/day = 308 hrs, generous)

If the math says a provider needs 20+ hours/day of face-time to generate their claims, that's not a statistical argument — it's arithmetic. Hard to dispute in a whistleblower filing.

---

## Fraud Patterns Detected

### 1. Impossible Hours (capacity simulation)
Provider's total billed procedures exceed human working capacity in a month. A solo doc billing 99214 (30 min each) 800 times in January needs 400 hours — 18 hrs/day, 22 days straight.

**Data needed:** Spending dataset + CMS RVU time estimates
**Status:** Built and tested

### 2. Cookie-Cutter Billing
Provider bills only 2-3 HCPCS codes for hundreds of patients. A real practice has a diverse code profile reflecting varied patient needs. An assembly-line fraud shop bills 99213 + 99214 for everyone.

**Signal:** Low code diversity (<=3 distinct codes) + high patient volume (50+ unique beneficiaries/month)
**Status:** Built and tested

### 3. Family & Friends Care Fraud
Personal care aide (T1019, T1020, S5125) billing max hours for 1-2 beneficiaries, every month, for years. Often the "provider" and "patient" are family or associates at the same residential address.

**Signal:** <=3 beneficiaries + 12+ consecutive months of billing + personal care HCPCS codes
**Status:** Built and tested

### 4. TPA / Billing Entity Rings
One billing NPI submitting claims for many servicing NPIs — the management company / TPA pattern. Especially suspicious when the servicing NPIs are newly enumerated and billing adult day care or HCBS codes.

**Signal:** Billing NPI with 4+ distinct servicing NPIs
**Status:** Built and tested

### 5. Rats Scurry (temporal discontinuity)
One NPI's billing drops sharply, then a different NPI at the same or nearby address picks up the same HCPCS codes. The provider didn't stop — they moved to a new identity.

**Signal:** Correlated billing cliff at NPI-A with billing spike at NPI-B, shared codes, proximate addresses
**Status:** Test data generator includes this pattern; dedicated detector script planned

### 6. Patient Cramming
Provider whose unique beneficiary count spikes far beyond local Medicaid enrollment growth. Associated with pop-up clinics, enrollment-assist orgs, and free screening events that funnel new enrollees to a specific billing provider.

**Signal:** Beneficiary growth rate vs. geographic enrollment baseline; cookie-cutter code mix on the crammed patients
**Status:** Planned

### 7. Flash Clinic → Adult Day Care Pipeline
Pop-up clinic enrolls vulnerable populations (homeless, recent immigrants), gets them classified under disability categories, then a related entity bills ongoing adult day care / HCBS. The enrollment entity and billing entity are connected through shared ownership (state SOS data).

**Signal:** Billing/servicing NPI split + adult day care codes + new entities + shared officers in business registrations
**Status:** Planned

---

## Data Sources

| Source | What | URL |
|--------|------|-----|
| CMS Medicaid Provider Spending* | NPI x HCPCS x Month aggregated claims | https://opendata.hhs.gov/datasets/medicaid-provider-spending/ |
| CMS PFS Relative Value Files* | Work RVUs, procedure descriptions, time estimates | https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files |
| CMS CPT/HCPCS Code List | Designated health service categories (Stark Law) | https://www.cms.gov/medicare/regulations-guidance/physician-self-referral/list-cpt-hcpcs-codes |
| HCPCS Level II Code Sets | T-code and S-code descriptions with billing units | https://www.hhs.gov/guidance/document/hcpcs-release-code-sets |
| NPPES NPI Registry | Provider name, address, specialty, enumeration date | https://npiregistry.cms.hhs.gov/api/ |
| OIG LEIE | Excluded individuals/entities (already caught) | https://oig.hhs.gov/exclusions/ |
| State SOS Business Registrations | Entity officers, agents, registration dates | Varies by state |

\* *In active use in project*

---

## What's Built

```
scripts/
  build_time_lookup.py     — Parses CMS RVU file into HCPCS->minutes JSON (7,370 codes)
  generate_test_data.py    — Synthetic spending data with 5 planted fraud types
  load.py                  — Parquet/CSV loader with filter helpers
  simulate_capacity.py     — The detector: impossible hours, cookie-cutter,
                             family care, TPA patterns. Scores and ranks.
tests/
  test_simulate_capacity.py — 20 tests: flag detection, scoring, edge cases
data/
  reference/
    rvu25c.zip             — CMS PFS RVU file (Jul 2025)
    hcpcs_minutes.json     — Generated lookup: HCPCS code -> minutes + source citation
notes.md                   — Primary source URLs for reference data
```

---

## What's Next

1. **Run against real CA data** — download spending dataset, filter to California, run detector
2. **`profile_npi.py`** — drill into a flagged NPI: full billing history, NPPES info, timeline
3. **`rats_scurry.py`** — temporal discontinuity detection (paired NPI cliff/spike)
4. **`associate_finder.py`** — surname + address matching across NPIs (friends & family network)
5. **LLM integration** — entity name normalization, address canonicalization, narrative scoring of flagged providers

---

## Why "Longtail"

The standard fraud analytics space is crowded. Everyone's building the same dashboards finding the same top-10 spenders. RSL targets patterns that require a hypothesis — not "who bills the most" but "whose billing is physically impossible" or "who changed behavior when enforcement showed up nearby." These are harder to find, harder to dispute, and more valuable as whistleblower findings.

---

## Whistleblower Context

Findings from this tool are intended to support qui tam filings under the False Claims Act. Every detection is grounded in:
- **Arithmetic, not statistics** — "this person needs 26 hours in a day" vs. "this person is 2 standard deviations above average"
- **CMS's own data** — time estimates from the Physician Fee Schedule, billing data from CMS open data
- **Citable sources** — every HCPCS time estimate traces back to a specific CMS document

Reference:
- OIG Fraud & Abuse Laws: https://oig.hhs.gov/compliance/physician-education/fraud-abuse-laws/
- OIG Whistleblower Protection: https://oig.hhs.gov/fraud/whistleblower/
- OIG Investigative Advisory on Medicaid PCS: https://oig.hhs.gov/reports-and-publications/portfolio/mpcs.asp
