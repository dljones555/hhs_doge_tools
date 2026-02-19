---
name: slice-dates
description: Slice the Medicaid spending dataset by date range
argument-hint: <start-date> <end-date> [--name <name>]
allowed-tools: Bash(uv run python *)
---

Slice the dataset by date range. Run:

```
uv run python scripts/slice_data.py --date-start $ARGUMENTS[0] --date-end $ARGUMENTS[1]
```

If a `--name` is provided in the arguments, pass it through. Otherwise derive a name from the date range (e.g. "fy2023" for 2023-01-01 to 2023-12-01).

Dates should be in YYYY-MM-DD or YYYY-MM-01 format (the dataset uses CLAIM_FROM_MONTH).

Can be combined with other filters. For example: `/slice-dates 2023-01-01 2023-12-01 --name fy2023`

Output goes to `data/slices/<name>.parquet`. After slicing, report the row count.
