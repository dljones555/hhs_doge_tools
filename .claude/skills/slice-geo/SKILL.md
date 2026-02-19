---
name: slice-geo
description: Slice the Medicaid spending dataset by geographic area (state, city)
argument-hint: --state <ST> [--city <city>]
allowed-tools: Bash(uv run python *), Read
---

Slice the dataset by geographic location. This requires a two-step process because the CMS dataset has no state column:

1. **Look up NPIs by location** using the NPPES API:
   ```
   uv run python scripts/lookup_npi.py --json  # (not directly — use npi_lookup.py)
   ```

2. **Filter the dataset** to those NPIs:
   ```
   uv run python scripts/slice_data.py --npi <comma-separated-npis> --name <geo-name>
   ```

For state-level slicing, note that the NPPES API caps at 1200 results per query, so full state coverage requires ZIP-by-ZIP iteration. Warn the user about this limitation and suggest using specific cities or ZIP codes for more targeted results.

Parse the arguments to determine state and optional city. Use the `hhs_doge_tools.npi_lookup` module (search_by_city or search_by_zip) to get NPI lists, then pass them to slice_data.py.
