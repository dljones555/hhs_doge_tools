---
name: lookup-npi
description: Look up NPI(s) in the NPPES registry to get provider name, address, and taxonomy
argument-hint: <npi> [<npi2> ...] [--json]
allowed-tools: Bash(uv run python *)
---

Look up one or more NPIs in the NPPES registry. Run:

```
uv run python scripts/lookup_npi.py $ARGUMENTS
```

Supports multiple modes:
- Single NPI: `<NPI>`
- Multiple NPIs: `<NPI1> <NPI2>`
- From file: `--file data/npi_list.txt --limit 20`
- Top flagged: `--top-flagged data/suspects_real.csv --limit 20`
- JSON output: `--json`

Returns provider name, entity type, address, taxonomy, and enumeration date.

After displaying results, summarize the key findings. If the NPI is an organization, note that. If not found, note that A-prefix NPIs are likely state-assigned Medicaid IDs, not in NPPES.
