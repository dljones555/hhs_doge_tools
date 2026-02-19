---
name: slice-npi
description: Slice the Medicaid spending dataset by NPI number(s) or NPI file
argument-hint: <npi-list-or-file> [--name <name>]
allowed-tools: Bash(uv run python *)
---

Slice the dataset by NPI(s). Parse the arguments to determine the right flags:

- Single or comma-separated NPIs: `uv run python scripts/slice_data.py --npi $ARGUMENTS`
- File path: `uv run python scripts/slice_data.py --npi-file <path> --name <name>`

If no `--name` is provided, derive one from the NPI or file name.

Output goes to `data/slices/<name>.parquet`. After slicing, report the row count and suggest `/detect-fraud` or `/profile-npi` as next steps.
