# Agents & Module Responsibilities

## Data Pipeline Flow
```
NPPES API  →  NPI Lookup  →  HF Dataset Filter  →  Analysis
(providers)   (npi_lookup)    (data_loader)         (analysis + address_match)
```

## Module Agents

### npi_lookup.py — Provider Discovery
- Queries NPPES registry for providers by city/state, ZIP, or individual NPI
- Handles pagination (200 per page, up to 1200 results per query)
- Rate limits requests (0.5s delay between pages)
- Caches raw API responses as JSON files in data/npi_cache/
- Returns list of Provider models

### data_loader.py — Dataset Access
- Connects to HuggingFace HHS-Official/medicaid-provider-spending dataset
- 33 parquet shards, ~227M rows, ~6GB total
- Filters dataset to specific NPI list and caches result locally
- **CURRENT ISSUE**: HF rate limiting without auth token — needs fix to download shards via API URLs instead of hf:// protocol

### address_match.py — Co-location Detection
- Normalizes street addresses (abbreviations, suite removal, whitespace)
- Groups providers sharing the same physical address
- Flags locations with multiple providers (potential fraud signal)

### analysis.py — Billing Analysis
- avg_paid_by_hcpcs: average payment per procedure code
- find_outliers: z-score based outlier detection (providers billing above mean + 2*std)
- billing_volume_summary: per-provider totals, averages, unique codes

### cli.py — Orchestrator
- Ties all modules together in a 4-step pipeline:
  1. NPPES provider lookup
  2. HF dataset filtering
  3. Co-located provider detection
  4. Basic billing analysis
