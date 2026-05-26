"""
lookup_npi.py — Batch NPPES registry lookup for NPIs.

Looks up one or more NPIs via the NPPES API and displays provider details.
Reuses the existing npi_lookup.py async client with caching.

Usage:
    uv run python scripts/lookup_npi.py <NPI>
    uv run python scripts/lookup_npi.py <NPI1> <NPI2>
    uv run python scripts/lookup_npi.py --file data/npi_list.txt
    uv run python scripts/lookup_npi.py --top-flagged data/suspects_real.csv --limit 20
    uv run python scripts/lookup_npi.py <NPI> --json
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add src to path for the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from hhs_doge_tools.npi_lookup import lookup_npi


async def lookup_many(npis: list[str]) -> list[dict]:
    """Look up multiple NPIs and return results."""
    results = []
    for i, npi in enumerate(npis):
        npi = npi.strip()
        if not npi:
            continue
        provider = await lookup_npi(npi)
        if provider:
            results.append(provider.model_dump())
        else:
            results.append({"npi": npi, "error": "Not found in NPPES"})
        if (i + 1) % 10 == 0:
            print(f"  Looked up {i + 1}/{len(npis)}...", file=sys.stderr)
    return results


async def get_entity_types(npis: list[str]) -> dict[str, str]:
    """Look up entity types for a list of NPIs.

    Returns {npi: "1"|"2"|"unknown"} where "1"=individual, "2"=organization.
    """
    results = await lookup_many(npis)
    entity_map = {}
    for p in results:
        npi = str(p.get("npi", ""))
        if "error" in p:
            entity_map[npi] = "unknown"
        else:
            entity_map[npi] = p.get("entity_type", "unknown") or "unknown"
    return entity_map


def format_provider(p: dict) -> str:
    """Format a single provider record for display."""
    if "error" in p:
        return f"  {p['npi']}: {p['error']}"

    name = p.get("org_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
    entity = "Org" if p.get("entity_type") == "2" else "Individual"
    addr = f"{p.get('city', '')}, {p.get('state', '')} {p.get('zip5', '')}"
    taxonomy = p.get("taxonomy_desc", "") or p.get("taxonomy_code", "")

    lines = [
        f"  NPI: {p['npi']}",
        f"  Name: {name}",
        f"  Type: {entity}",
        f"  Address: {p.get('address_line1', '')}",
        f"           {addr}",
        f"  Taxonomy: {taxonomy}",
        f"  Enumeration date: {p.get('enumeration_date', 'N/A')}",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Look up NPIs in the NPPES registry")
    parser.add_argument("npis", nargs="*", help="NPI(s) to look up")
    parser.add_argument("--file", type=str, default=None,
                        help="File with NPIs (one per line)")
    parser.add_argument("--top-flagged", type=str, default=None,
                        help="CSV file with WORKER_NPI column — look up top flagged NPIs")
    parser.add_argument("--limit", type=int, default=10,
                        help="Max NPIs to look up from --file or --top-flagged (default: 10)")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON instead of formatted text")
    args = parser.parse_args()

    npis: list[str] = []

    if args.npis:
        npis.extend(args.npis)

    if args.file:
        p = Path(args.file)
        if not p.exists():
            print(f"ERROR: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        npis.extend(line.strip() for line in p.read_text().splitlines() if line.strip())

    if args.top_flagged:
        import polars as pl
        p = Path(args.top_flagged)
        if not p.exists():
            print(f"ERROR: File not found: {args.top_flagged}", file=sys.stderr)
            sys.exit(1)
        df = pl.read_csv(p)
        npi_col = "WORKER_NPI" if "WORKER_NPI" in df.columns else df.columns[0]
        top = df.head(args.limit)[npi_col].cast(pl.Utf8).to_list()
        npis.extend(top)

    if not npis:
        parser.error("Provide NPIs as arguments, or use --file / --top-flagged")

    # Deduplicate while preserving order
    seen = set()
    unique_npis = []
    for npi in npis:
        if npi not in seen:
            seen.add(npi)
            unique_npis.append(npi)
    npis = unique_npis[:args.limit] if (args.file or args.top_flagged) else unique_npis

    print(f"Looking up {len(npis)} NPI(s)...", file=sys.stderr)
    results = asyncio.run(lookup_many(npis))

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        for i, p in enumerate(results):
            if i > 0:
                print("-" * 50)
            print(format_provider(p))


if __name__ == "__main__":
    main()
