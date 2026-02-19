"""
run_real.py — Run fraud detection on real CMS data within 8GB RAM.

Filters the full 227M-row parquet to high-value HCPCS codes first,
then runs the capacity detector on the subset.

Usage:
    uv run python scripts/run_real.py
"""

import sys
from pathlib import Path
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
from simulate_capacity import run_capacity_analysis, print_report

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FULL_FILE = DATA_DIR / "medicaid-provider-spending.parquet"
SUBSET_FILE = DATA_DIR / "subset_high_value.parquet"

# Codes worth investigating: E&M, personal care, adult day care, home health
TARGET_CODES = [
    # E&M office visits (most common billing codes — capacity violations here are damning)
    "99211", "99212", "99213", "99214", "99215",
    # New patient
    "99202", "99203", "99204", "99205",
    # Personal care / home care (family fraud vector)
    "T1019", "T1020", "T1021",
    "S5125", "S5130", "S5170",
    # Adult day care (flash clinic pipeline)
    "T2021", "T2020", "S5100", "S5101", "S5102",
    # Screening / preventive (cramming signal)
    "99381", "99385", "99391", "99395", "99397",
]


def main():
    if not FULL_FILE.exists():
        print(f"ERROR: {FULL_FILE} not found")
        return

    # Step 1: filter to target codes
    if SUBSET_FILE.exists():
        print(f"Using cached subset: {SUBSET_FILE}")
        lf = pl.scan_parquet(SUBSET_FILE)
    else:
        print(f"Filtering {FULL_FILE.name} to {len(TARGET_CODES)} HCPCS codes...")
        lf = pl.scan_parquet(FULL_FILE)
        df = lf.filter(pl.col("HCPCS_CODE").is_in(TARGET_CODES)).collect(streaming=True)
        print(f"Got {len(df):,} rows, {df['BILLING_PROVIDER_NPI_NUM'].n_unique():,} billing NPIs")
        df.write_parquet(SUBSET_FILE)
        print(f"Saved to {SUBSET_FILE}")
        lf = pl.scan_parquet(SUBSET_FILE)

    # Step 2: run detector
    summary = run_capacity_analysis(lf)
    print_report(summary, top_n=40)

    # Step 3: export
    flagged = summary.filter(pl.col("suspicion_score") > 20)
    out = DATA_DIR / "suspects_real.csv"
    flagged.write_csv(out)
    print(f"\nExported {len(flagged)} flagged providers to {out}")


if __name__ == "__main__":
    main()
