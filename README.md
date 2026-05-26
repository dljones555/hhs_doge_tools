# HHS DOGE Tools

A Python toolkit for Medicaid provider spending analysis, fraud scenario simulation, and local parquet slicing.
This repository is released into the public domain under CC0 1.0.
This repo is a proof-of-concept for exploratory analysis rather than a production-grade investigation platform. It includes prompt generated inline HCPCS groups, zip code patterns, and other heuristic filters that are useful for experimentation but not ideal for deployment.

This project contains only code and documentation. No actual dataset files, patient records, or analytical summaries are included in this repository.

The work grew from a very large HHS Medicaid billing dataset that was made public for citizen review. The source dataset is available from the HHS DOGE group and the HHS Open Data platform.

https://opendata.hhs.gov/

Streaming access to the dataset was unreliable, so the project focuses on slicing the dataset locally using parquet by geography (city, county, ZIP) and then analyzing aggregated provider billing patterns.

## What it does

- Loads and filters the HHS Medicaid spending dataset by NPI, city, county, and ZIP
- Looks up providers from the NPPES registry with async API access and cached JSON
- Detects potentially suspicious provider relationships and co-located addresses
- Analyzes billing clusters by HCPCS code, month, claims, beneficiaries, and paid totals
- Supports fraud scenario simulation with synthetic test data
- Provides promptable "skills" for English-driven data prep, scenario runs, summaries, and reports

## Skills and English prompts

This project is built to support analyst-style prompts and workflow commands, such as:

- slice the dataset by geography, date range, NPIs, or HCPCS groups
- run capacity-based fraud detection on a specific slice
- look up an NPI in NPPES and inspect provider address/taxonomy details
- profile a flagged provider with capacity and billing-code analysis
- summarize suspicious clusters and suggest next investigation steps

The `.claude/skills` definitions map these capabilities to command patterns that make the repo easy to use as an analyst toolkit.

## Data model

The dataset is aggregated and month-based rather than patient-level. Key fields include:

- `BILLING_PROVIDER_NPI_NUM`
- `SERVICING_PROVIDER_NPI_NUM`
- `HCPCS_CODE`
- `CLAIM_FROM_MONTH`
- `TOTAL_UNIQUE_BENEFICIARIES`
- `TOTAL_CLAIMS`
- `TOTAL_PAID`

That means there are no individual service dates or patient records; analysis works from monthly totals and capacity assumptions.

## Fraud reasoning

The approach is built around observable anomalies in aggregated billing data:

- A provider should only be able to serve a limited number of beneficiaries in a month
- Sudden spikes in claims, paid totals, or unusual code clusters can signal abuse
- Provider relationships such as billing vs servicing NPI splits and address co-location are important
- Simulated scenarios help compare normal versus suspicious patterns
- This matches real-world HHS/CMS fraud task force logic: impossible volume plus provider/servicer address and billing splits often prompt physical validation

## Project contents

- `src/hhs_doge_tools/` — core modules for config, NPI lookup, data loading, address matching, and analysis
- `scripts/` — helper scripts including test data generation and city extract runners
- `data/` — local caches, slices, and NPI lookup responses (ignored by git)
- `CLAUDE.md` — project overview and module responsibilities

## Usage

Install dependencies and run a city extract or analysis script:

```bash
uv sync
uv run city-extract --city "Monowi" --state "NE"
uv run python scripts/run_city_extract.py --city "Monowi" --state "NE"
```

There are also synthetic data generators for planted fraud scenarios in `scripts/generate_test_data.py`.

## License

This repository is dedicated to the public domain under CC0 1.0 Universal.

## Notes

- Hugging Face streaming access was not reliable for this dataset, so the repo uses local parquet slicing instead
- The dataset is highly aggregated; detection is based on totals and limits rather than patient-level event logs
- The repo contains proof-of-concept heuristics, including hard-coded HCPCS code groups and ZIP/NPI filters, so it is intended for exploration and concept validation only
- The system is designed to be viable for month-based anomaly detection and to highlight issues around billing codes and provider relationships
- Reviews and findings are exploratory; they are subject to fact, due process, and qui tam considerations, and should be validated by the right investigators before any conclusion is drawn
- The repo is portfolio-ready: it demonstrates NPI/HCPCS API integration, local parquet slicing, synthetic fraud scenario simulation, and analyst-facing prompt workflows

## Why it matters

This project makes a large Medicaid spending dataset tractable by slicing it locally, modeling plausible fraud patterns, and turning the analysis into a set of promptable skills for exploration and reporting.
