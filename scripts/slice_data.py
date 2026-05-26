"""
slice_data.py — Unified data slicer for the Medicaid provider spending dataset.

Produces named parquet slices in data/slices/ that can be piped into
detect-fraud, profile-npi, and other analysis tools.

Filters are composable: combine --codes, --npi, --npi-file, --date-start/--date-end.

Usage:
    uv run python scripts/slice_data.py --codes home-health --name home-health
    uv run python scripts/slice_data.py --codes "99213,99214" --name custom-em
    uv run python scripts/slice_data.py --npi <NPI> --name single-npi
    uv run python scripts/slice_data.py --npi-file suspects.txt --name suspects
    uv run python scripts/slice_data.py --date-start 2023-01-01 --date-end 2023-12-01 --name fy2023
    uv run python scripts/slice_data.py --codes high-value --date-start 2023-01-01 --name hv-2023
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from code_lists import list_presets, resolve_codes
from load import load_spending, filter_hcpcs, filter_npis, filter_npis_from_file, filter_date_range

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SLICES_DIR = DATA_DIR / "slices"


def main():
    parser = argparse.ArgumentParser(
        description="Slice the Medicaid spending dataset by HCPCS codes, NPIs, or date range.",
        epilog="Filters are composable: combine --codes with --date-start/--date-end, etc.",
    )
    parser.add_argument("--codes", type=str, default=None,
                        help="HCPCS preset name or comma-separated codes (e.g. 'home-health' or '99213,99214')")
    parser.add_argument("--npi", type=str, default=None,
                        help="Comma-separated NPI(s) to filter to")
    parser.add_argument("--npi-file", type=str, default=None,
                        help="Path to file with NPIs (one per line)")
    parser.add_argument("--date-start", type=str, default=None,
                        help="Start date filter (YYYY-MM-DD or YYYY-MM-01)")
    parser.add_argument("--date-end", type=str, default=None,
                        help="End date filter (YYYY-MM-DD or YYYY-MM-01)")
    # output - why not > data/slices/? Because we want to be able to run this from anywhere, and it's easier to manage the path in code than ask users to cd into the right directory.
    parser.add_argument("--name", type=str, default=None,
                        help="Name for the output slice (becomes data/slices/<name>.parquet)")
    
    # input - allow override for testing, but default to auto-detecting the latest data file in data/
 
    parser.add_argument("--data", type=str, default=None,
                        help="Source data file (default: auto-detect from data/)")
    # presets are in code_lists.py, but allow users to list them from the CLI. 
    # this file gets built. note this file is versioned by medicaid implying codes and minutes may change over time - this is outstanding question
    # if we want to version code lists by date or just update them as we learn more. for now, we'll just update the code lists and users can check the git history if they want to see changes over time.
    # building a HCPCS code list is a bit of work, so we want to be able to reuse it across analyses and share it with the team. putting it in a separate file also keeps this script focused on slicing logic.
    parser.add_argument("--list-presets", action="store_true",
                        help="List available HCPCS code presets and exit")
    args = parser.parse_args()

    if args.list_presets:
        print("Available HCPCS presets:")
        print(list_presets())
        return

    # Require at least one filter and a name
    if not any([args.codes, args.npi, args.npi_file, args.date_start]):
        parser.error("At least one filter required: --codes, --npi, --npi-file, or --date-start")
    if not args.name:
        parser.error("--name is required when slicing data")

    # Load source data
    lf = load_spending(args.data)

    # Apply filters (composable)
    if args.codes:
        codes = resolve_codes(args.codes)
        print(f"Filtering to {len(codes)} HCPCS codes: {', '.join(codes[:10])}{'...' if len(codes) > 10 else ''}")
        lf = filter_hcpcs(lf, codes)

    if args.npi:
        npis = [n.strip() for n in args.npi.split(",") if n.strip()]
        print(f"Filtering to {len(npis)} NPI(s)")
        lf = filter_npis(lf, npis)

    if args.npi_file:
        print(f"Filtering to NPIs from {args.npi_file}")
        lf = filter_npis_from_file(lf, args.npi_file)

    if args.date_start or args.date_end:
        start = args.date_start or "2000-01-01"
        end = args.date_end or "2099-12-31"
        print(f"Filtering dates: {start} to {end}")
        lf = filter_date_range(lf, start, end)

    # Collect and save
    SLICES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SLICES_DIR / f"{args.name}.parquet"

    print("Collecting data...")
    try:
        df = lf.collect(engine="streaming")
    except Exception:
        df = lf.collect(streaming=True)

    df.write_parquet(out_path)
    print(f"Saved {len(df):,} rows to {out_path}")
    print(f"Columns: {df.columns}")

    if len(df) > 0:
        billing_npis = df["BILLING_PROVIDER_NPI_NUM"].n_unique()
        servicing_npis = df["SERVICING_PROVIDER_NPI_NUM"].drop_nulls().n_unique()
        total_paid = df["TOTAL_PAID"].sum()
        print(f"Billing NPIs: {billing_npis:,}, Servicing NPIs: {servicing_npis:,}")
        print(f"Total paid: ${total_paid:,.2f}")
    else:
        print("WARNING: Slice is empty — check your filters")


if __name__ == "__main__":
    main()
