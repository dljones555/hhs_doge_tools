"""
simulate_capacity.py — Flag providers billing more than is physically possible.

For each provider+month, sums up implied work hours across all their HCPCS codes
using CMS time estimates. Flags anyone exceeding human capacity.

Also detects:
  - Cookie-cutter billing (low code diversity vs high patient volume)
  - Family/personal care patterns (very few beneficiaries, daily billing)
  - Billing vs servicing splits (TPA patterns)

Usage:
    uv run python scripts/simulate_capacity.py                          # uses test data
    uv run python scripts/simulate_capacity.py --data data/real.parquet # real data
    uv run python scripts/simulate_capacity.py --top 50                 # show top 50
    uv run python scripts/simulate_capacity.py --export suspects.csv    # save results
"""

import argparse
import json
from pathlib import Path
import polars as pl

# ── Time lookup: loaded from CMS-sourced JSON, with fallback heuristics ──
# Built by build_time_lookup.py from:
#   - CMS PFS RVU25C (Jul 2025) — Work RVUs + description-extracted times
#   - CMS CY2025 PFS Final Rule — E&M visit times
#   - HCPCS Level II code descriptions — T/S code billing units
# Run `uv run python scripts/build_time_lookup.py` to regenerate.
REF_DIR = Path(__file__).resolve().parent.parent / "data" / "reference"
_LOOKUP_PATH = REF_DIR / "hcpcs_minutes.json"
HCPCS_MINUTES: dict[str, float] = {}

if _LOOKUP_PATH.exists():
    with open(_LOOKUP_PATH) as _f:
        _raw = json.load(_f)
        HCPCS_MINUTES = {k: v["minutes"] if isinstance(v, dict) else v for k, v in _raw.items()}
    print(f"Loaded {len(HCPCS_MINUTES)} HCPCS time estimates from {_LOOKUP_PATH.name}")
else:
    print(f"WARNING: {_LOOKUP_PATH} not found. Run build_time_lookup.py first.")
    print("Falling back to built-in estimates for common codes only.")
    HCPCS_MINUTES = {
        "99211": 5, "99212": 10, "99213": 20, "99214": 30, "99215": 40,
        "99202": 15, "99203": 30, "99204": 45, "99205": 60,
        "T1019": 15, "T1020": 480, "T2021": 480, "T2020": 480,
        "S5125": 15, "S5130": 60, "S5170": 30,
        "S5100": 480, "S5101": 240, "S5102": 60,
    }

# Working assumptions
WORK_DAYS_PER_MONTH = 22
MAX_HOURS_PER_DAY = 14       # generous — nobody works 14hr clinical days sustainably
MAX_MINUTES_PER_MONTH = WORK_DAYS_PER_MONTH * MAX_HOURS_PER_DAY * 60  # 18,480 min

# Thresholds
IMPOSSIBILITY_RATIO = 1.0     # flag at 100%+ of max capacity
HIGH_SUSPICION_RATIO = 0.70   # flag at 70%+ for further review
COOKIE_CUTTER_MAX_CODES = 3   # ≤3 distinct codes with 50+ patients = suspicious
FAMILY_CARE_MAX_BENES = 3     # ≤3 beneficiaries with daily billing = family pattern


def estimate_minutes(code: str) -> float:
    """Estimate face-time minutes for a HCPCS code."""
    if code in HCPCS_MINUTES:
        return HCPCS_MINUTES[code]

    # Heuristic by code range
    if code.startswith("992"):
        return 20  # generic E&M
    if code.startswith("99"):
        return 15
    if code.startswith(("T1", "T2", "S5")):
        return 60  # home/community services default
    if code[0].isdigit():
        # surgical/procedural CPT codes
        val = int(code[:3]) if code[:3].isdigit() else 0
        if 10000 <= int(code) <= 69999:
            return 30  # surgical range
        return 15  # default
    if code[0].isalpha():
        return 20  # HCPCS level II default

    return 15  # fallback


def run_capacity_analysis(lf: pl.LazyFrame) -> pl.DataFrame:
    """
    For each billing NPI + month, compute total implied work minutes.
    Returns a scored DataFrame sorted by impossibility.
    """
    # Build a time-lookup DataFrame for joining (stays lazy-compatible)
    codes_df = lf.select("HCPCS_CODE").unique().collect()
    code_list = codes_df["HCPCS_CODE"].to_list()
    time_map = {c: estimate_minutes(str(c)) for c in code_list}
    time_df = pl.DataFrame({
        "HCPCS_CODE": list(time_map.keys()),
        "est_minutes_per_claim": [float(v) for v in time_map.values()],
    }).lazy()

    # Join time estimates and compute total_minutes — all lazy, no collect
    enriched = (
        lf.select([
            "BILLING_PROVIDER_NPI_NUM",
            "SERVICING_PROVIDER_NPI_NUM",
            "HCPCS_CODE",
            "CLAIM_FROM_MONTH",
            "TOTAL_UNIQUE_BENEFICIARIES",
            "TOTAL_CLAIMS",
            "TOTAL_PAID",
        ])
        .join(time_df, on="HCPCS_CODE", how="left")
        .with_columns(
            pl.col("est_minutes_per_claim").fill_null(15.0),
        )
        .with_columns(
            (pl.col("TOTAL_CLAIMS") * pl.col("est_minutes_per_claim")).alias("total_minutes")
        )
    )

    # ── Per-NPI per-month capacity analysis (lazy groupby) ──
    # Note: TOTAL_UNIQUE_BENEFICIARIES can overlap across codes, so use max not sum
    monthly = enriched.group_by(["BILLING_PROVIDER_NPI_NUM", "CLAIM_FROM_MONTH"]).agg([
        pl.col("total_minutes").sum().alias("month_total_minutes"),
        pl.col("TOTAL_CLAIMS").sum().alias("month_total_claims"),
        pl.col("TOTAL_UNIQUE_BENEFICIARIES").max().alias("month_max_benes"),
        pl.col("TOTAL_UNIQUE_BENEFICIARIES").sum().alias("month_sum_benes"),
        pl.col("TOTAL_PAID").sum().alias("month_total_paid"),
        pl.col("HCPCS_CODE").n_unique().alias("month_distinct_codes"),
        pl.col("SERVICING_PROVIDER_NPI_NUM").n_unique().alias("distinct_servicing_npis"),
    ])

    monthly = monthly.with_columns([
        (pl.col("month_total_minutes") / MAX_MINUTES_PER_MONTH).alias("capacity_ratio"),
        (pl.col("month_total_minutes") / WORK_DAYS_PER_MONTH / 60).alias("implied_hours_per_day"),
    ])

    # ── Per-NPI summary (across all months) — collect here ──
    print("Running aggregation (this may take a few minutes on large datasets)...")
    try:
        monthly = monthly.collect(engine="streaming")
    except Exception:
        monthly = monthly.collect(streaming=True)

    summary = monthly.group_by("BILLING_PROVIDER_NPI_NUM").agg([
        pl.col("capacity_ratio").max().alias("peak_capacity_ratio"),
        pl.col("capacity_ratio").mean().alias("avg_capacity_ratio"),
        pl.col("implied_hours_per_day").max().alias("peak_hours_per_day"),
        pl.col("month_total_claims").sum().alias("total_claims_all_time"),
        pl.col("month_max_benes").max().alias("peak_benes_per_month"),
        pl.col("month_total_paid").sum().alias("total_paid_all_time"),
        pl.col("month_distinct_codes").max().alias("max_distinct_codes"),
        pl.col("month_distinct_codes").mean().alias("avg_distinct_codes"),
        pl.col("CLAIM_FROM_MONTH").n_unique().alias("active_months"),
        pl.col("distinct_servicing_npis").max().alias("max_servicing_npis"),
    ])

    # ── Flag types ──
    summary = summary.with_columns([
        # Physical impossibility
        (pl.col("peak_capacity_ratio") >= IMPOSSIBILITY_RATIO).alias("flag_impossible_hours"),
        (pl.col("peak_capacity_ratio") >= HIGH_SUSPICION_RATIO).alias("flag_high_capacity"),

        # Cookie-cutter: few codes, lots of patients
        (
            (pl.col("avg_distinct_codes") <= COOKIE_CUTTER_MAX_CODES)
            & (pl.col("peak_benes_per_month") >= 50)
        ).alias("flag_cookie_cutter"),

        # Family/personal care: very few beneficiaries, consistent billing
        (
            (pl.col("peak_benes_per_month") <= FAMILY_CARE_MAX_BENES)
            & (pl.col("active_months") >= 12)
        ).alias("flag_family_care"),

        # TPA pattern: billing NPI has multiple servicing NPIs
        (pl.col("max_servicing_npis") > 3).alias("flag_tpa_pattern"),
    ])

    # Composite suspicion score (simple weighted sum)
    summary = summary.with_columns(
        (
            pl.col("flag_impossible_hours").cast(pl.Float64) * 40
            + pl.col("flag_high_capacity").cast(pl.Float64) * 20
            + pl.col("flag_cookie_cutter").cast(pl.Float64) * 25
            + pl.col("flag_family_care").cast(pl.Float64) * 20
            + pl.col("flag_tpa_pattern").cast(pl.Float64) * 15
            + (pl.col("peak_capacity_ratio").clip(0, 5) * 10)  # continuous score boost
        ).alias("suspicion_score")
    )

    return summary.sort("suspicion_score", descending=True)


def print_report(summary: pl.DataFrame, top_n: int = 25):
    """Print a readable report of flagged providers."""
    flagged = summary.filter(pl.col("suspicion_score") > 20)

    print("=" * 90)
    print(f"  CAPACITY SIMULATION REPORT — {len(flagged)} flagged of {len(summary)} providers")
    print("=" * 90)

    impossible = summary.filter(pl.col("flag_impossible_hours"))
    high_cap = summary.filter(pl.col("flag_high_capacity") & ~pl.col("flag_impossible_hours"))
    cookie = summary.filter(pl.col("flag_cookie_cutter"))
    family = summary.filter(pl.col("flag_family_care"))
    tpa = summary.filter(pl.col("flag_tpa_pattern"))

    print(f"\n  IMPOSSIBLE HOURS (>{MAX_HOURS_PER_DAY}hr/day peak):  {len(impossible)}")
    print(f"  HIGH CAPACITY (>{HIGH_SUSPICION_RATIO*100:.0f}% utilization):    {len(high_cap)}")
    print(f"  COOKIE-CUTTER (<={COOKIE_CUTTER_MAX_CODES} codes, 50+ patients):  {len(cookie)}")
    print(f"  FAMILY CARE PATTERN (<={FAMILY_CARE_MAX_BENES} benes, 12+ months): {len(family)}")
    print(f"  TPA/BILLING SPLIT (4+ servicing NPIs):    {len(tpa)}")

    print(f"\n  TOP {min(top_n, len(flagged))} SUSPECTS:")
    print("-" * 90)
    print(f"  {'NPI':<14} {'Score':>6} {'Peak hrs/day':>13} {'Peak benes':>11} "
          f"{'Codes':>6} {'Months':>7} {'Total Paid':>12}  Flags")
    print("-" * 90)

    for row in flagged.head(top_n).iter_rows(named=True):
        flags = []
        if row["flag_impossible_hours"]: flags.append("IMPOSSIBLE")
        if row["flag_cookie_cutter"]: flags.append("COOKIE")
        if row["flag_family_care"]: flags.append("FAMILY")
        if row["flag_tpa_pattern"]: flags.append("TPA")
        if not flags and row["flag_high_capacity"]: flags.append("HIGH-CAP")

        print(f"  {row['BILLING_PROVIDER_NPI_NUM']:<14} "
              f"{row['suspicion_score']:>6.1f} "
              f"{row['peak_hours_per_day']:>13.1f} "
              f"{row['peak_benes_per_month']:>11} "
              f"{row['max_distinct_codes']:>6} "
              f"{row['active_months']:>7} "
              f"${row['total_paid_all_time']:>11,.0f}  "
              f"{', '.join(flags)}")

    print("-" * 90)


def main():
    parser = argparse.ArgumentParser(description="Capacity simulation fraud detector")
    parser.add_argument("--data", type=str, default=None, help="Path to parquet/csv file")
    parser.add_argument("--top", type=int, default=25, help="Number of top suspects to show")
    parser.add_argument("--export", type=str, default=None, help="Export results to CSV")
    args = parser.parse_args()

    # Import load.py from same directory
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from load import load_spending

    data_path = args.data
    if data_path is None:
        # Default to test data
        test_path = Path(__file__).parent.parent / "data" / "test_spending.parquet"
        if test_path.exists():
            data_path = str(test_path)

    lf = load_spending(data_path)
    summary = run_capacity_analysis(lf)
    print_report(summary, top_n=args.top)

    if args.export:
        flagged = summary.filter(pl.col("suspicion_score") > 20)
        flagged.write_csv(args.export)
        print(f"\nExported {len(flagged)} flagged providers to {args.export}")


if __name__ == "__main__":
    main()
