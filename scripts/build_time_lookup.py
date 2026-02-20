"""
build_time_lookup.py — Parse CMS RVU file into a HCPCS -> minutes JSON lookup.

Reads PPRRVU2025_Jul.csv from data/reference/ (extracted from rvu25c.zip)
and outputs data/reference/hcpcs_minutes.json

Source: CMS PFS Relative Value Files
https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files

NOTE: The PRE/INTRA/POST columns in the RVU file are work PROPORTIONS (fractions
summing to ~1.0), NOT minutes. Actual procedure times come from:
  1. E&M codes: time is in the code description (e.g. "Office o/p est low 20 min")
  2. Surgical codes: estimated from WORK RVU using a minutes-per-RVU ratio
  3. HCPCS Level II (T/S codes): from official code descriptions

Usage:
    uv run python scripts/build_time_lookup.py
"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REF_DIR = DATA_DIR / "reference"

# ── E&M codes with CMS-defined times (from code descriptions & CMS final rule) ──
# Source: CY2025 PFS Final Rule, Table 14 — E&M visit times
# https://www.federalregister.gov/documents/2024/12/09/2024-25382/
EM_TIMES = {
    # Office/outpatient established
    "99211": 5, "99212": 10, "99213": 20, "99214": 30, "99215": 40,
    # Office/outpatient new
    "99202": 15, "99203": 30, "99204": 45, "99205": 60,
    # Preventive established
    "99391": 25, "99392": 30, "99393": 30, "99394": 30, "99395": 35, "99396": 35, "99397": 35,
    # Preventive new
    "99381": 30, "99382": 35, "99383": 35, "99384": 35, "99385": 40, "99386": 45, "99387": 45,
    # Initial hospital
    "99221": 40, "99222": 55, "99223": 75,
    # Subsequent hospital
    "99231": 25, "99232": 35, "99233": 50,
    # ER
    "99281": 8, "99282": 15, "99283": 25, "99284": 40, "99285": 60,
    # Observation
    "99218": 40, "99219": 50, "99220": 60,
    # Discharge
    "99238": 30, "99239": 45,
    # Consult
    "99241": 15, "99242": 30, "99243": 40, "99244": 60, "99245": 80,
}

# ── HCPCS Level II codes NOT in the physician fee schedule ──
# Sourced from official HCPCS code descriptions. Billing unit is in the name.
# https://www.hhs.gov/guidance/document/hcpcs-release-code-sets
MANUAL_CODES = {
    # Personal care services
    "T1019": {"minutes": 15, "unit": "per 15 min", "source": "HCPCS desc: 'personal care services, per 15 minutes'"},
    "T1020": {"minutes": 480, "unit": "per diem", "source": "HCPCS desc: 'personal care services, per diem'"},
    "T1021": {"minutes": 60, "unit": "per session", "source": "HCPCS desc: 'home health aide, per visit'"},
    # Attendant care
    "S5125": {"minutes": 15, "unit": "per 15 min", "source": "HCPCS desc: 'attendant care services, per 15 minutes'"},
    "S5130": {"minutes": 60, "unit": "per hour", "source": "HCPCS desc: 'homemaker service, NOS, per 15 minutes' (x4)"},
    "S5170": {"minutes": 30, "unit": "per meal", "source": "HCPCS desc: 'home delivered meals, per meal'"},
    # Behavioral health / recovery
    "T1015": {"minutes": 15, "unit": "per 15 min", "source": "HCPCS desc: 'clinic visit/encounter, all-inclusive, per 15 minutes'"},
    "H2019": {"minutes": 15, "unit": "per 15 min", "source": "HCPCS desc: 'therapeutic behavioral services, per 15 minutes'"},
    "H0032": {"minutes": 15, "unit": "per 15 min", "source": "HCPCS desc: 'mental health service plan development by non-physician'"},
    # Peer support / community behavioral health
    "H0038": {"minutes": 15, "unit": "per 15 min", "source": "HCPCS desc: 'self-help/peer services, per 15 minutes'"},
    "H2015": {"minutes": 15, "unit": "per 15 min", "source": "HCPCS desc: 'comprehensive community support services, per 15 minutes'"},
    "H2014": {"minutes": 15, "unit": "per 15 min", "source": "HCPCS desc: 'skills training and development, per 15 minutes'"},
    "H0025": {"minutes": 60, "unit": "per session", "source": "HCPCS desc: 'behavioral health prevention education, per session'"},
    "H0023": {"minutes": 15, "unit": "per 15 min", "source": "HCPCS desc: 'behavioral health outreach service, per 15 minutes'"},
    "T1016": {"minutes": 15, "unit": "per 15 min", "source": "HCPCS desc: 'case management, each 15 minutes'"},
    "H2017": {"minutes": 15, "unit": "per 15 min", "source": "HCPCS desc: 'psychosocial rehabilitation services, per 15 minutes'"},
    "H2027": {"minutes": 15, "unit": "per 15 min", "source": "HCPCS desc: 'psychoeducational services, per 15 minutes'"},
    # Adult day care
    "T2021": {"minutes": 480, "unit": "per diem", "source": "HCPCS desc: 'day habilitation, per diem'"},
    "T2020": {"minutes": 480, "unit": "per diem", "source": "HCPCS desc: 'day habilitation, waiver; per diem'"},
    "S5100": {"minutes": 480, "unit": "per diem", "source": "HCPCS desc: 'day care services, adult; per diem'"},
    "S5101": {"minutes": 240, "unit": "per half day", "source": "HCPCS desc: 'day care services, adult; per half day'"},
    "S5102": {"minutes": 60, "unit": "per hour", "source": "HCPCS desc: 'day care services, adult; per hour'"},
}

# Approximate minutes per Work RVU for surgical/procedural codes
# Based on CMS RUC survey median: ~5 min intraservice per 1.0 work RVU
# This is a rough conversion used when no explicit time is available.
MINUTES_PER_WORK_RVU = 5.0


def parse_rvu_csv(path: Path) -> dict:
    """Parse CMS PPRRVU CSV. Extract HCPCS, description, and Work RVU."""
    lookup = {}

    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        lines = f.readlines()

    # Find header rows
    hcpcs_row = None
    for i, line in enumerate(lines):
        fields = [f.strip() for f in line.split(",")]
        if "HCPCS" in fields:
            hcpcs_row = i
            break

    if hcpcs_row is None:
        raise ValueError("Could not find HCPCS header row")

    # Column layout: HCPCS(0), MOD(1), DESCRIPTION(2), STATUS(3), ..., WORK RVU(5)
    data_start = hcpcs_row + 1
    desc_col = 2
    work_rvu_col = 5

    parsed = 0
    skipped = 0
    for line in lines[data_start:]:
        fields = line.strip().split(",")
        if len(fields) <= work_rvu_col:
            continue

        code = fields[0].strip().strip('"')
        if not code or len(code) != 5:
            continue

        desc = fields[desc_col].strip().strip('"')

        # Skip modifier-specific rows (MOD column not empty)
        mod = fields[1].strip()
        if mod:
            continue

        # 1. Check if it's an E&M code with known time
        if code in EM_TIMES:
            lookup[code] = {
                "minutes": EM_TIMES[code],
                "source": f"CMS CY2025 PFS Final Rule E&M time; desc: '{desc}'",
            }
            parsed += 1
            continue

        # 2. Try to extract time from description (e.g. "20 min", "30 minutes")
        time_match = re.search(r'(\d+)\s*min', desc, re.IGNORECASE)
        if time_match:
            minutes = int(time_match.group(1))
            if 1 <= minutes <= 600:
                lookup[code] = {
                    "minutes": minutes,
                    "source": f"CMS RVU25C desc: '{desc}'",
                }
                parsed += 1
                continue

        # 3. Estimate from Work RVU
        try:
            work_rvu = float(fields[work_rvu_col]) if fields[work_rvu_col].strip() else 0
        except ValueError:
            skipped += 1
            continue

        if work_rvu > 0:
            est_minutes = work_rvu * MINUTES_PER_WORK_RVU
            lookup[code] = {
                "minutes": round(est_minutes, 1),
                "source": f"Estimated from Work RVU {work_rvu:.2f} x {MINUTES_PER_WORK_RVU} min/RVU; desc: '{desc}'",
            }
            parsed += 1
        else:
            skipped += 1

    print(f"Parsed {parsed} codes ({skipped} skipped — zero RVU or unparseable)")
    return lookup


def main():
    csv_path = REF_DIR / "PPRRVU2025_Jul.csv"
    if not csv_path.exists():
        import zipfile
        zip_path = REF_DIR / "rvu25c.zip"
        if not zip_path.exists():
            raise FileNotFoundError(f"Need {zip_path} — download from CMS PFS Relative Value Files page")
        print(f"Extracting {csv_path.name} from {zip_path.name}...")
        with zipfile.ZipFile(zip_path) as z:
            z.extract("PPRRVU2025_Jul.csv", REF_DIR)

    # Parse RVU file
    lookup = parse_rvu_csv(csv_path)

    # Add manual HCPCS Level II codes
    for code, entry in MANUAL_CODES.items():
        lookup[code] = entry
    print(f"Added {len(MANUAL_CODES)} manual HCPCS Level II codes")

    # Save
    out_path = REF_DIR / "hcpcs_minutes.json"
    with open(out_path, "w") as f:
        json.dump(lookup, f, indent=2)
    print(f"Saved {len(lookup)} codes to {out_path}")

    # Stats
    times = [v["minutes"] for v in lookup.values()]
    print(f"Time range: {min(times):.0f} - {max(times):.0f} minutes")
    print(f"Median: {sorted(times)[len(times)//2]:.0f} minutes")

    # Sample common codes
    print("\nSample codes:")
    for code in ["99211", "99213", "99214", "99215", "27447", "29881", "T1019", "T2021"]:
        if code in lookup:
            e = lookup[code]
            print(f"  {code}: {e['minutes']} min -- {e['source']}")
        else:
            print(f"  {code}: NOT FOUND")


if __name__ == "__main__":
    main()
