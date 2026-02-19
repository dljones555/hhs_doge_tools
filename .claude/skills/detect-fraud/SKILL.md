---
name: detect-fraud
description: Run capacity simulation fraud detection on a data slice or the full subset
argument-hint: [<data-path>] [--top <N>] [--export <path>]
allowed-tools: Bash(uv run python *)
---

Run the capacity simulation fraud detector. This identifies providers billing more hours than physically possible, cookie-cutter billing patterns, family care patterns, and TPA splits.

If a data path argument is provided, run on that slice:
```
uv run python scripts/run_real.py --data $ARGUMENTS
```

If no argument is provided, run on the default high-value subset:
```
uv run python scripts/run_real.py
```

Additional flags can be passed through:
- `--top N` — show top N entities (default: 40)
- `--export path.csv` — export flagged results to CSV
- `--codes preset` — filter by HCPCS preset instead of using cached subset
- `--threshold N` — suspicion score cutoff (default: 20)

After detection completes, summarize the results and suggest using `/profile-npi` to investigate specific flagged NPIs.

IMPORTANT: Set PYTHONIOENCODING=utf-8 before running on Windows to avoid encoding errors with Polars output.
