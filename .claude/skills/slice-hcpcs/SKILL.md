---
name: slice-hcpcs
description: Slice the Medicaid spending dataset by HCPCS codes or preset groups
argument-hint: <preset-or-codes> [--name <name>]
allowed-tools: Bash(uv run python *)
---

Slice the dataset by HCPCS codes. Run:

```
uv run python scripts/slice_data.py --codes $ARGUMENTS
```

If no `--name` is provided in the arguments, derive a name from the preset or codes.

## Available presets

- `high-value` — 26 codes: E&M, personal care, day care, screening
- `home-health` — T1019, T1020, T1021, S5125, S5130, S5170
- `day-care` — T2020, T2021, S5100, S5101, S5102
- `em-office` — 99211-99215, 99202-99205
- `screening` — 99381, 99385, 99391, 99395, 99397

You can also pass raw comma-separated codes: `99213,99214,T1019`

Output goes to `data/slices/<name>.parquet`. After slicing, report the row count and suggest next steps like `/detect-fraud` on the slice.
