# Plan & Tasks

## Immediate Fix
- [ ] **Fix HuggingFace data loading** — rate limited without HF_TOKEN
  - Old approach: `hf://` protocol via Polars scan (broken, rate limited)
  - New approach: download parquet shards via HF API URLs with httpx, cache locally in data/hf_parquet/, then scan local files
  - The API endpoint works: `https://huggingface.co/api/datasets/HHS-Official/medicaid-provider-spending/parquet` returns 33 shard URLs
  - Download with delays between files to avoid rate limit
  - Once downloaded, shards are cached and never re-downloaded

## Pending Tasks
- [ ] Rewrite data_loader.py to use direct HTTP download instead of hf:// protocol
- [ ] Test full pipeline: `city-extract --city "Costa Mesa" --state "CA"`
- [ ] Handle NPPES 1200-result cap for large cities (split by ZIP code)
- [ ] Git commit all current work (src/ layout, scripts/, config changes)

## Backlog
- [ ] **Filter out government/state agency NPIs from flagged entities** — NPI-2 orgs with taxonomy codes like `251K00000X` (Public Health or Welfare) and `251S00000X` (Community/Behavioral Health) are state-run IDD/MH programs billing at scale. They dominate the top of the list (e.g. TN DIDD, AL DMHMR) but are false positives. Options: (a) NPPES lookup on top entities to check org type, (b) pre-filter by taxonomy, (c) flag separately as "government entity" in the report.
- [ ] **`scripts/lookup_npi.py`** — Batch NPPES lookup script. Takes one or more NPIs, hits the NPPES API, returns formatted org name / individual name / address / taxonomy / enumeration date. Supports batch mode for enriching entity lists (e.g. pipe in top 100 flagged NPIs, get back a table).
- [ ] **`scripts/search_dataset.py`** — Ad-hoc NPI search against full or subset parquet. "Is this NPI in our data? What codes did they bill? How much were they paid?" Quick triage tool before running full profile.
- [ ] **Dog food against known MN fraud cases** — Known indicted MN entities (Star Autism Center, Guardian Home Health, Ultimate Home Health, Promise Health Services) were NOT found in the CMS spending dataset. They may bill under HCPCS codes outside our target list or use different billing channels. Need to: (a) search full dataset with broader code coverage, (b) search by individual NPI (e.g. Mohamed Omarxeyd 1215316575), (c) determine if the dataset covers the right time period and programs.
- [ ] Add `--zip` flag to CLI for ZIP-code-based extraction
- [ ] Export co-located providers to CSV/Excel for review
- [ ] Add outlier report output (flag specific NPIs + procedure codes)
- [ ] Support HF_TOKEN env var for authenticated access when available
- [ ] Add progress bars for large downloads
- [ ] Tests

## What Works Today
- NPPES API lookup: fully functional, caches responses ✓
- Address normalization & co-location detection ✓
- Billing analysis queries (avg, outlier, volume) ✓
- CLI wiring ✓
- HF dataset schema detection ✓

## Known Issues
- HF rate limit: IP 209.0.232.82 currently rate-limited (will expire)
- NPPES caps at 1200 results per city query — Costa Mesa likely has more providers
- main.py deleted but not committed
- No git commit yet for the full src/ restructure
