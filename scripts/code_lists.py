"""
code_lists.py — HCPCS code presets and resolver for slicing the dataset.

Usage:
    from code_lists import resolve_codes

    codes = resolve_codes("home-health")        # preset name
    codes = resolve_codes("99213,99214,T1019")  # raw comma-separated
    codes = resolve_codes("high-value")         # the 26-code set from run_real.py
"""

PRESETS: dict[str, list[str]] = {
    "high-value": [
        # E&M office visits
        "99211", "99212", "99213", "99214", "99215",
        # New patient
        "99202", "99203", "99204", "99205",
        # Personal care / home care
        "T1019", "T1020", "T1021",
        "S5125", "S5130", "S5170",
        # Adult day care
        "T2021", "T2020", "S5100", "S5101", "S5102",
        # Screening / preventive
        "99381", "99385", "99391", "99395", "99397",
    ],
    "home-health": ["T1019", "T1020", "T1021", "S5125", "S5130", "S5170"],
    "day-care": ["T2020", "T2021", "S5100", "S5101", "S5102"],
    "em-office": [
        "99211", "99212", "99213", "99214", "99215",
        "99202", "99203", "99204", "99205",
    ],
    "screening": ["99381", "99385", "99391", "99395", "99397"],
}


def resolve_codes(spec: str) -> list[str]:
    """Resolve a preset name or comma-separated code list to a list of HCPCS codes.

    Args:
        spec: Either a preset name (e.g. "home-health") or comma-separated codes
              (e.g. "99213,99214,T1019").

    Returns:
        List of HCPCS code strings.

    Raises:
        ValueError: If spec is empty or matches no preset and contains no valid codes.
    """
    spec = spec.strip()
    if not spec:
        raise ValueError("Empty code spec")

    # Check presets first
    if spec.lower() in PRESETS:
        return PRESETS[spec.lower()]

    # Parse as comma-separated codes
    codes = [c.strip().upper() for c in spec.split(",") if c.strip()]
    if not codes:
        raise ValueError(f"No codes found in: {spec!r}")
    return codes


def list_presets() -> str:
    """Return a formatted string listing all available presets."""
    lines = []
    for name, codes in PRESETS.items():
        lines.append(f"  {name:<14} {len(codes)} codes: {', '.join(codes[:6])}{'...' if len(codes) > 6 else ''}")
    return "\n".join(lines)
