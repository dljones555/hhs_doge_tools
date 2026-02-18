"""Console script entry point for city-extract."""

import argparse
import asyncio

from .address_match import find_colocated
from .analysis import avg_paid_by_hcpcs, billing_volume_summary
from .data_loader import load_city_subset
from .npi_lookup import search_by_city


async def _run(city: str, state: str) -> None:
    print(f"\n=== Medicaid Provider Spending: {city}, {state} ===\n")

    # Step 1: NPPES lookup
    print("[1/4] Searching NPPES for providers...")
    providers = await search_by_city(city, state)
    print(f"  Found {len(providers)} providers")

    if not providers:
        print("  No providers found. Check city/state spelling.")
        return

    npi_list = [p.npi for p in providers]

    # Step 2: Filter HF dataset
    print("\n[2/4] Filtering HuggingFace dataset...")
    output_name = f"{city.lower().replace(' ', '_')}_{state.lower()}"
    df = load_city_subset(npi_list, output_name=output_name)

    # Step 3: Co-located providers
    print("\n[3/4] Finding co-located providers...")
    colocated = find_colocated(providers)
    if colocated:
        print(f"  Found {len(colocated)} addresses with multiple providers:")
        for match in colocated[:10]:
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
    parser.add_argument("--city", required=True, help="City name")
    parser.add_argument("--state", required=True, help="Two-letter state code")
    args = parser.parse_args()
    asyncio.run(_run(args.city, args.state))
