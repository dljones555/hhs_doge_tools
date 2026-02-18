# HHS DOGE Tools

## Project Overview
Medicaid provider spending fraud analysis tool. Pulls provider data from NPPES registry, cross-references with HHS Medicaid spending dataset on HuggingFace, identifies co-located providers and billing outliers.

## Tech Stack
- **Python 3.12+** with **uv** package manager
- **Polars** for data processing (lazy scan of parquet files)
- **Pydantic** for data models
- **httpx** for async HTTP (NPPES API)
- **hatchling** build system, src layout

## Project Structure
```
src/hhs_doge_tools/
  config.py        — paths, API config, constants
  models.py        — Pydantic: Provider, Claim, AddressMatch
  npi_lookup.py    — async NPPES API client (pagination, rate limiting, JSON cache)
  data_loader.py   — HuggingFace parquet dataset loading & NPI filtering
  address_match.py — street address normalization, co-located provider detection
  analysis.py      — billing analysis (avg by HCPCS, outlier detection, volume summary)
  cli.py           — city-extract CLI entry point
scripts/
  run_city_extract.py — standalone script (mirrors cli.py)
data/              — local cache dir (gitignored)
  npi_cache/       — JSON cache of NPPES API responses
```

## Commands
```bash
# Run the CLI
uv run city-extract --city "Costa Mesa" --state "CA"

# Or via script
uv run python scripts/run_city_extract.py --city "Costa Mesa" --state "CA"

# Install deps
uv sync
```

## Key APIs
- **NPPES**: https://npiregistry.cms.hhs.gov/api/ (v2.1, 200/page, 1200 cap per query)
- **HF Dataset**: HHS-Official/medicaid-provider-spending (~227M rows, 33 parquet shards)

## Conventions
- Column discovery is dynamic (case-insensitive search for npi/paid/hcpcs columns)
- NPPES responses cached as JSON in data/npi_cache/
- Filtered datasets cached as parquet in data/
- All data files are gitignored
