"""CLI entry point: extract Medicaid spending data for a city.

Usage:
    uv run python scripts/run_city_extract.py --city "Springfield" --state "IL"
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src to path so we can import the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hhs_doge_tools.address_match import find_colocated
from hhs_doge_tools.analysis import avg_paid_by_hcpcs, billing_volume_summary
from hhs_doge_tools.data_loader import load_city_subset
from hhs_doge_tools.npi_lookup import search_by_city


async def run(city: str, state: str) -> None:
    print(f"\n=== Medicaid Provider Spending: {city}, {state} ===\n")

    # Step 1: Look up all providers in the city via NPPES
    print("[1/4] Searching NPPES for providers...")
    providers = await search_by_city(city, state)
    print(f"  Found {len(providers)} providers")

    if not providers:
        print("  No providers found. Check city/state spelling.")
        return

    npi_list = [p.npi for p in providers]

    # Step 2: Filter HF dataset to this city's NPIs
    print("\n[2/4] Filtering HuggingFace dataset...")
    output_name = f"{city.lower().replace(' ', '_')}_{state.lower()}"
    df = load_city_subset(npi_list, output_name=output_name)

    # Step 3: Find co-located providers
    print("\n[3/4] Finding co-located providers...")
    colocated = find_colocated(providers)
    if colocated:
        print(f"  Found {len(colocated)} addresses with multiple providers:")
        for match in colocated[:10]:  # Show top 10
            print(
                f"    {match.normalized_address}, {match.city} "
                f"— {match.provider_count} providers"
            )
        if len(colocated) > 10:
            print(f"    ... and {len(colocated) - 10} more")
    else:
        print("  No co-located providers found.")

    # Step 4: Basic analysis
    print("\n[4/4] Running basic analysis...")

    if len(df) > 0:
        print("\n  Top billing providers:")
        volume = billing_volume_summary(df)
        print(volume.head(10))

        print("\n  Top HCPCS codes by average payment:")
        hcpcs_avg = avg_paid_by_hcpcs(df)
        print(hcpcs_avg.head(10))
    else:
        print("  No claims data found for these NPIs.")

    print(f"\n=== Done. Data saved in data/{output_name}.parquet ===")


def main():
    parser = argparse.ArgumentParser(
        description="Extract Medicaid provider spending data for a city"
    )
    parser.add_argument("--city", required=True, help="City name (e.g. Springfield)")
    parser.add_argument(
        "--state", required=True, help="Two-letter state code (e.g. IL)"
    )
    args = parser.parse_args()
    asyncio.run(run(args.city, args.state))


if __name__ == "__main__":
    main()
