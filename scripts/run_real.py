"""
run_real.py — Run fraud detection on real CMS data within 8GB RAM.

Filters the full 227M-row parquet to high-value HCPCS codes first,
then runs the capacity detector on the subset.

Usage:
    uv run python scripts/run_real.py
    uv run python scripts/run_real.py --data data/slices/home-health.parquet
    uv run python scripts/run_real.py --codes home-health
    uv run python scripts/run_real.py --top 50 --export flagged.csv
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from code_lists import resolve_codes, PRESETS
from simulate_capacity import run_capacity_analysis, apply_entity_type_enrichment, print_report
from lookup_npi import get_entity_types
import polars as pl

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FULL_FILE = DATA_DIR / "medicaid-provider-spending.parquet"
SUBSET_FILE = DATA_DIR / "subset_high_value.parquet"


def main():
    parser = argparse.ArgumentParser(description="Run fraud detection on CMS data")
    parser.add_argument("--data", type=str, default=None,
                        help="Path to pre-sliced parquet file (skips filtering)")
    parser.add_argument("--codes", type=str, default=None,
                        help="HCPCS preset or comma-separated codes (default: high-value)")
    parser.add_argument("--top", type=int, default=40,
                        help="Number of top entities to show (default: 40)")
    parser.add_argument("--export", type=str, default=None,
                        help="Export flagged results to CSV")
    parser.add_argument("--threshold", type=float, default=20.0,
                        help="Suspicion score threshold for export (default: 20)")
    args = parser.parse_args()

    if args.data:
        # Use pre-sliced data directly
        data_path = Path(args.data)
        if not data_path.exists():
            print(f"ERROR: {data_path} not found")
            return
        print(f"Using pre-sliced data: {data_path}")
        lf = pl.scan_parquet(data_path)
    else:
        # Filter from full dataset or use cached subset
        target_codes = resolve_codes(args.codes or "high-value")

        if args.codes is None and SUBSET_FILE.exists():
            print(f"Using cached subset: {SUBSET_FILE}")
            lf = pl.scan_parquet(SUBSET_FILE)
        elif FULL_FILE.exists():
            print(f"Filtering {FULL_FILE.name} to {len(target_codes)} HCPCS codes...")
            lf = pl.scan_parquet(FULL_FILE)
            df = lf.filter(pl.col("HCPCS_CODE").is_in(target_codes)).collect(streaming=True)
            print(f"Got {len(df):,} rows, {df['BILLING_PROVIDER_NPI_NUM'].n_unique():,} billing NPIs")

            # Cache if using default high-value codes
            if args.codes is None:
                df.write_parquet(SUBSET_FILE)
                print(f"Saved to {SUBSET_FILE}")

            lf = df.lazy()
        else:
            print(f"ERROR: {FULL_FILE} not found")
            return

    # Run detector
    summary = run_capacity_analysis(lf)

    # Enrich with entity types from NPPES
    try:
        flagged_npis = (
            summary.filter(pl.col("suspicion_score") > args.threshold)
            ["WORKER_NPI"].cast(pl.Utf8).to_list()
        )
        if flagged_npis:
            print(f"\nLooking up entity types for {len(flagged_npis)} flagged NPIs...")
            entity_map = asyncio.run(get_entity_types(flagged_npis))
            summary = apply_entity_type_enrichment(summary, entity_map)

            # Print breakdown
            types = list(entity_map.values())
            n_ind = types.count("1")
            n_org = types.count("2")
            n_unk = len(types) - n_ind - n_org
            print(f"  Entity types: {n_ind} individual, {n_org} organization, {n_unk} unknown")
    except Exception as e:
        print(f"WARNING: NPPES enrichment failed ({e}), proceeding without entity types",
              file=sys.stderr)

    print_report(summary, top_n=args.top)

    # Export
    export_path = args.export or str(DATA_DIR / "suspects_real.csv")
    flagged = summary.filter(pl.col("suspicion_score") > args.threshold)
    flagged.write_csv(export_path)
    print(f"\nExported {len(flagged)} flagged providers to {export_path}")


if __name__ == "__main__":
    main()
