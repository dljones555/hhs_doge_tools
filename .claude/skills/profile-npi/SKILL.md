---
name: profile-npi
description: Deep-dive profile of a specific NPI from the Medicaid spending data
argument-hint: <npi> [--data <path>]
allowed-tools: Bash(uv run python *)
---

Generate a detailed profile for a specific NPI. Run:

```
PYTHONIOENCODING=utf-8 uv run python scripts/profile_npi.py $ARGUMENTS
```

If no `--data` flag is provided, it defaults to `data/subset_high_value.parquet`.

The profile includes:
- Role (billing entity, servicing provider, or both)
- Claims by HCPCS code with time estimates
- Monthly capacity analysis (peak hours/day, capacity ratio)
- Flag assessment (impossible hours, cookie-cutter, family care, TPA)
- Peak month row-level detail
- Servicing NPI breakdown (if billing entity with multiple workers)

After displaying the profile, interpret the key findings — especially any capacity flags — and suggest whether this entity warrants further investigation.
