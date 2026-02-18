"""Co-located provider finder — groups providers sharing the same street address."""

import re
from collections import defaultdict

from .models import AddressMatch, Provider

# Common abbreviation normalization map
_ABBREVS = {
    r"\bST\b": "STREET",
    r"\bSTR\b": "STREET",
    r"\bAVE?\b": "AVENUE",
    r"\bBLVD\b": "BOULEVARD",
    r"\bDR\b": "DRIVE",
    r"\bLN\b": "LANE",
    r"\bRD\b": "ROAD",
    r"\bCT\b": "COURT",
    r"\bPL\b": "PLACE",
    r"\bPKWY\b": "PARKWAY",
    r"\bCIR\b": "CIRCLE",
    r"\bHWY\b": "HIGHWAY",
    r"\bN\b": "NORTH",
    r"\bS\b": "SOUTH",
    r"\bE\b": "EAST",
    r"\bW\b": "WEST",
}

# Patterns to strip suite/unit/apt identifiers
_SUITE_PATTERN = re.compile(
    r"\b(STE|SUITE|UNIT|APT|APARTMENT|RM|ROOM|FL|FLOOR|#)\s*[\w-]*",
    re.IGNORECASE,
)


def normalize_address(address: str) -> str:
    """Normalize a street address for comparison.

    - Uppercase
    - Strip suite/apt/unit/room numbers
    - Normalize abbreviations (ST -> STREET, etc.)
    - Collapse whitespace
    """
    addr = address.upper().strip()

    # Remove suite / unit identifiers
    addr = _SUITE_PATTERN.sub("", addr)

    # Normalize abbreviations
    for pattern, replacement in _ABBREVS.items():
        addr = re.sub(pattern, replacement, addr)

    # Remove punctuation except hyphens in numbers
    addr = re.sub(r"[.,]", "", addr)

    # Collapse whitespace
    addr = re.sub(r"\s+", " ", addr).strip()

    return addr


def find_colocated(
    providers: list[Provider], *, min_providers: int = 2
) -> list[AddressMatch]:
    """Group providers by normalized address and return groups with multiple providers.

    Args:
        providers: List of Provider models to analyze.
        min_providers: Minimum number of distinct providers at an address to include.

    Returns:
        List of AddressMatch groups, sorted by provider count descending.
    """
    groups: dict[str, list[Provider]] = defaultdict(list)

    for p in providers:
        if not p.address_line1:
            continue
        key = normalize_address(p.address_line1)
        groups[key].append(p)

    matches = []
    for norm_addr, group in groups.items():
        # Deduplicate by NPI
        seen_npis: set[str] = set()
        unique: list[Provider] = []
        for p in group:
            if p.npi not in seen_npis:
                seen_npis.add(p.npi)
                unique.append(p)

        if len(unique) >= min_providers:
            # Use the first provider's location info for the group
            first = unique[0]
            matches.append(
                AddressMatch(
                    normalized_address=norm_addr,
                    city=first.city,
                    state=first.state,
                    zip5=first.zip5,
                    provider_npis=[p.npi for p in unique],
                    provider_count=len(unique),
                )
            )

    matches.sort(key=lambda m: m.provider_count, reverse=True)
    return matches
