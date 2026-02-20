"""NPPES NPI Registry API client with pagination, rate limiting, and local caching."""

import asyncio
import json
from pathlib import Path

import httpx

from .config import (
    NPI_CACHE_DIR,
    NPPES_API_BASE,
    NPPES_API_VERSION,
    NPPES_MAX_PER_PAGE,
    NPPES_MAX_RESULTS,
    NPPES_RATE_LIMIT_DELAY,
)
from .models import Provider


def _parse_provider(result: dict) -> Provider:
    """Parse a single NPPES API result dict into a Provider model."""
    basic = result.get("basic", {})
    addresses = result.get("addresses", [])
    taxonomies = result.get("taxonomies", [])

    # Use the first "location" address (type = "DOM" / mailing = "LOCATION")
    # Fall back to first address if no location-type found.
    addr = {}
    for a in addresses:
        if a.get("address_purpose", "").upper() == "LOCATION":
            addr = a
            break
    if not addr and addresses:
        addr = addresses[0]

    tax = taxonomies[0] if taxonomies else {}

    entity_type = str(result.get("enumeration_type", ""))
    # NPI-1 = individual, NPI-2 = organization
    if "NPI-1" in entity_type:
        et = "1"
    elif "NPI-2" in entity_type:
        et = "2"
    else:
        et = entity_type

    return Provider(
        npi=str(result.get("number", "")),
        first_name=basic.get("first_name", ""),
        last_name=basic.get("last_name", ""),
        org_name=basic.get("organization_name", ""),
        address_line1=addr.get("address_1", ""),
        address_line2=addr.get("address_2", ""),
        city=addr.get("city", ""),
        state=addr.get("state", ""),
        zip5=addr.get("postal_code", "")[:5] if addr.get("postal_code") else "",
        taxonomy_code=tax.get("code") or "",
        taxonomy_desc=tax.get("desc") or "",
        enumeration_date=basic.get("enumeration_date", ""),
        entity_type=et,
    )


def _cache_path(key: str) -> Path:
    """Return the cache file path for a given lookup key."""
    NPI_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = key.replace(" ", "_").replace(",", "").lower()
    return NPI_CACHE_DIR / f"{safe}.json"


def _load_cache(key: str) -> list[dict] | None:
    path = _cache_path(key)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _save_cache(key: str, results: list[dict]) -> None:
    path = _cache_path(key)
    path.write_text(json.dumps(results, default=str), encoding="utf-8")


async def search_by_city(
    city: str, state: str, *, entity_type: str = ""
) -> list[Provider]:
    """Search NPPES for all providers in a city/state. Paginates up to API limit.

    Args:
        city: City name (e.g. "Springfield")
        state: Two-letter state code (e.g. "IL")
        entity_type: Optional "1" (individual) or "2" (organization)

    Returns:
        List of Provider models.
    """
    cache_key = f"city_{city}_{state}_{entity_type}"
    cached = _load_cache(cache_key)
    if cached is not None:
        return [_parse_provider(r) for r in cached]

    all_results: list[dict] = []
    skip = 0

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params: dict = {
                "version": NPPES_API_VERSION,
                "city": city,
                "state": state,
                "limit": NPPES_MAX_PER_PAGE,
                "skip": skip,
            }
            if entity_type:
                params["enumeration_type"] = (
                    "NPI-1" if entity_type == "1" else "NPI-2"
                )

            resp = await client.get(NPPES_API_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            if not results:
                break

            all_results.extend(results)
            skip += len(results)

            # NPPES caps at 1200 results per query
            if skip >= NPPES_MAX_RESULTS or len(results) < NPPES_MAX_PER_PAGE:
                break

            await asyncio.sleep(NPPES_RATE_LIMIT_DELAY)

    _save_cache(cache_key, all_results)
    return [_parse_provider(r) for r in all_results]


async def search_by_zip(zip5: str, *, entity_type: str = "") -> list[Provider]:
    """Search NPPES by ZIP code. Useful for large cities that exceed 1200-result cap."""
    cache_key = f"zip_{zip5}_{entity_type}"
    cached = _load_cache(cache_key)
    if cached is not None:
        return [_parse_provider(r) for r in cached]

    all_results: list[dict] = []
    skip = 0

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params: dict = {
                "version": NPPES_API_VERSION,
                "postal_code": zip5,
                "limit": NPPES_MAX_PER_PAGE,
                "skip": skip,
            }
            if entity_type:
                params["enumeration_type"] = (
                    "NPI-1" if entity_type == "1" else "NPI-2"
                )

            resp = await client.get(NPPES_API_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            if not results:
                break

            all_results.extend(results)
            skip += len(results)

            if skip >= NPPES_MAX_RESULTS or len(results) < NPPES_MAX_PER_PAGE:
                break

            await asyncio.sleep(NPPES_RATE_LIMIT_DELAY)

    _save_cache(cache_key, all_results)
    return [_parse_provider(r) for r in all_results]


async def lookup_npi(npi: str) -> Provider | None:
    """Look up a single NPI and return Provider, or None if not found."""
    cache_key = f"npi_{npi}"
    cached = _load_cache(cache_key)
    if cached is not None and cached:
        return _parse_provider(cached[0])

    async with httpx.AsyncClient(timeout=30) as client:
        params = {"version": NPPES_API_VERSION, "number": npi}
        resp = await client.get(NPPES_API_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", [])
    if not results:
        return None

    _save_cache(cache_key, results)
    return _parse_provider(results[0])
