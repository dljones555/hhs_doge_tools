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

## Future Enhancements
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
