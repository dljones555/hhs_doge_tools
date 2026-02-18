"""
generate_test_data.py — Create synthetic Medicaid spending data with planted fraud.

Generates realistic-looking aggregated data (NPI x HCPCS x Month) with:
  - Normal providers (legit billing patterns)
  - Impossible-hours providers (more procedures than hours in a day)
  - Personal care family fraud (1-2 beneficiaries, max hours, residential)
  - Cookie-cutter cramming (tons of patients, same few codes)
  - Billing/servicing split (TPA billing on behalf of many new NPIs)

Output: data/test_spending.parquet

Usage:
    uv run python scripts/generate_test_data.py
"""

import random
from pathlib import Path
import polars as pl

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

random.seed(42)

# -- HCPCS code pools by category --
OFFICE_VISIT_CODES = ["99211", "99212", "99213", "99214", "99215"]
PERSONAL_CARE_CODES = ["T1019", "T1020", "S5125", "S5130", "S5170"]
ADULT_DAY_CODES = ["T2021", "T2020", "S5100", "S5101", "S5102"]
SCREENING_CODES = ["99381", "99385", "99391", "99395", "99397"]
SURGICAL_CODES = ["27447", "27130", "29881", "43239", "47562"]
RARE_CODES = ["0523T", "0524T", "0620T", "64624", "0693T"]

MONTHS = [f"{y}-{m:02d}-01" for y in range(2018, 2025) for m in range(1, 13)]


def make_npi(n: int) -> str:
    return f"{1000000000 + n}"


def gen_normal_provider(npi: str, months: list[str]) -> list[dict]:
    """A legit doc: 5-8 codes, reasonable volume, spread across months."""
    rows = []
    codes = random.sample(OFFICE_VISIT_CODES + SURGICAL_CODES, k=random.randint(4, 7))
    for month in random.sample(months, k=min(len(months), random.randint(30, 60))):
        for code in random.sample(codes, k=random.randint(2, len(codes))):
            benes = random.randint(5, 40)
            claims = benes + random.randint(0, benes)  # some return visits
            paid = claims * random.uniform(50, 300)
            rows.append({
                "BILLING_PROVIDER_NPI_NUM": int(npi),
                "SERVICING_PROVIDER_NPI_NUM": int(npi),
                "HCPCS_CODE": code,
                "CLAIM_FROM_MONTH": month,
                "TOTAL_UNIQUE_BENEFICIARIES": benes,
                "TOTAL_CLAIMS": claims,
                "TOTAL_PAID": round(paid, 2),
            })
    return rows


def gen_impossible_hours_provider(npi: str, months: list[str]) -> list[dict]:
    """Fraud: bills way more procedures than humanly possible in a month."""
    rows = []
    codes = random.sample(OFFICE_VISIT_CODES, k=4)
    for month in random.sample(months, k=random.randint(20, 40)):
        for code in codes:
            # 80-200 claims per code per month = 320-800 visits/month
            # at 15-30 min each = physically impossible for one provider
            benes = random.randint(60, 180)
            claims = random.randint(80, 200)
            paid = claims * random.uniform(80, 200)
            rows.append({
                "BILLING_PROVIDER_NPI_NUM": int(npi),
                "SERVICING_PROVIDER_NPI_NUM": int(npi),
                "HCPCS_CODE": code,
                "CLAIM_FROM_MONTH": month,
                "TOTAL_UNIQUE_BENEFICIARIES": benes,
                "TOTAL_CLAIMS": claims,
                "TOTAL_PAID": round(paid, 2),
            })
    return rows


def gen_family_care_fraud(npi: str, months: list[str]) -> list[dict]:
    """Fraud: personal care aide billing max hours for 1-2 people."""
    rows = []
    codes = random.sample(PERSONAL_CARE_CODES, k=2)
    for month in months[-36:]:  # last 3 years, every month
        for code in codes:
            # 1-2 beneficiaries, 28-31 claims (daily billing), high hours
            benes = random.randint(1, 2)
            claims = random.randint(25, 31)
            paid = claims * random.uniform(150, 300)  # $150-300/day
            rows.append({
                "BILLING_PROVIDER_NPI_NUM": int(npi),
                "SERVICING_PROVIDER_NPI_NUM": int(npi),
                "HCPCS_CODE": code,
                "CLAIM_FROM_MONTH": month,
                "TOTAL_UNIQUE_BENEFICIARIES": benes,
                "TOTAL_CLAIMS": claims,
                "TOTAL_PAID": round(paid, 2),
            })
    return rows


def gen_cramming_provider(npi: str, months: list[str]) -> list[dict]:
    """Fraud: huge patient volume, cookie-cutter code mix (same 2 codes for everyone)."""
    rows = []
    codes = ["99213", "99214"]  # same two codes always
    for month in months[-24:]:  # appeared 2 years ago
        for code in codes:
            benes = random.randint(150, 400)  # way too many patients
            claims = benes  # exactly 1 visit each = assembly line
            paid = claims * random.uniform(80, 120)
            rows.append({
                "BILLING_PROVIDER_NPI_NUM": int(npi),
                "SERVICING_PROVIDER_NPI_NUM": int(npi),
                "HCPCS_CODE": code,
                "CLAIM_FROM_MONTH": month,
                "TOTAL_UNIQUE_BENEFICIARIES": benes,
                "TOTAL_CLAIMS": claims,
                "TOTAL_PAID": round(paid, 2),
            })
    return rows


def gen_tpa_ring(billing_npi: str, servicing_npis: list[str], months: list[str]) -> list[dict]:
    """Fraud: one billing entity, many servicing NPIs, all new, adult day care codes."""
    rows = []
    codes = ADULT_DAY_CODES[:3] + SCREENING_CODES[:2]
    # servicing NPIs only appear in recent months (new entities)
    recent = months[-18:]
    for srv_npi in servicing_npis:
        start = random.randint(0, 6)
        for month in recent[start:]:
            for code in random.sample(codes, k=random.randint(2, 4)):
                benes = random.randint(20, 80)
                claims = benes + random.randint(5, 30)
                paid = claims * random.uniform(100, 400)
                rows.append({
                    "BILLING_PROVIDER_NPI_NUM": int(billing_npi),
                    "SERVICING_PROVIDER_NPI_NUM": int(srv_npi),
                    "HCPCS_CODE": code,
                    "CLAIM_FROM_MONTH": month,
                    "TOTAL_UNIQUE_BENEFICIARIES": benes,
                    "TOTAL_CLAIMS": claims,
                    "TOTAL_PAID": round(paid, 2),
                })
    return rows


def gen_rats_scurry(npi_before: str, npi_after: str, months: list[str]) -> list[dict]:
    """Fraud: one NPI drops off, another picks up the same codes right after."""
    rows = []
    codes = random.sample(OFFICE_VISIT_CODES + SURGICAL_CODES, k=5)
    cutoff = len(months) // 2 + random.randint(-6, 6)

    # NPI "before" bills normally then drops to near zero
    for month in months[:cutoff]:
        for code in random.sample(codes, k=random.randint(3, 5)):
            benes = random.randint(15, 50)
            claims = benes + random.randint(0, 20)
            paid = claims * random.uniform(80, 250)
            rows.append({
                "BILLING_PROVIDER_NPI_NUM": int(npi_before),
                "SERVICING_PROVIDER_NPI_NUM": int(npi_before),
                "HCPCS_CODE": code,
                "CLAIM_FROM_MONTH": month,
                "TOTAL_UNIQUE_BENEFICIARIES": benes,
                "TOTAL_CLAIMS": claims,
                "TOTAL_PAID": round(paid, 2),
            })

    # NPI "after" starts billing the same codes right after cutoff
    for month in months[cutoff:]:
        for code in random.sample(codes, k=random.randint(3, 5)):
            benes = random.randint(15, 50)
            claims = benes + random.randint(0, 20)
            paid = claims * random.uniform(80, 250)
            rows.append({
                "BILLING_PROVIDER_NPI_NUM": int(npi_after),
                "SERVICING_PROVIDER_NPI_NUM": int(npi_after),
                "HCPCS_CODE": code,
                "CLAIM_FROM_MONTH": month,
                "TOTAL_UNIQUE_BENEFICIARIES": benes,
                "TOTAL_CLAIMS": claims,
                "TOTAL_PAID": round(paid, 2),
            })
    return rows


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = []

    # 50 normal providers
    for i in range(50):
        all_rows.extend(gen_normal_provider(make_npi(i), MONTHS))

    # 5 impossible-hours providers
    for i in range(50, 55):
        all_rows.extend(gen_impossible_hours_provider(make_npi(i), MONTHS))

    # 5 family care fraud
    for i in range(55, 60):
        all_rows.extend(gen_family_care_fraud(make_npi(i), MONTHS))

    # 3 cramming providers
    for i in range(60, 63):
        all_rows.extend(gen_cramming_provider(make_npi(i), MONTHS))

    # 1 TPA ring: 1 billing entity + 6 servicing NPIs
    tpa_billing = make_npi(70)
    tpa_servicing = [make_npi(71 + j) for j in range(6)]
    all_rows.extend(gen_tpa_ring(tpa_billing, tpa_servicing, MONTHS))

    # 2 rats-scurry pairs
    all_rows.extend(gen_rats_scurry(make_npi(80), make_npi(81), MONTHS))
    all_rows.extend(gen_rats_scurry(make_npi(82), make_npi(83), MONTHS))

    df = pl.DataFrame(all_rows)
    out = DATA_DIR / "test_spending.parquet"
    df.write_parquet(out)

    # Print summary
    print(f"Generated {len(df)} rows, {df['BILLING_PROVIDER_NPI_NUM'].n_unique()} billing NPIs")
    print(f"Saved to {out}")
    print()
    print("Planted fraud:")
    print(f"  Impossible hours:  NPIs 1000000050-1000000054")
    print(f"  Family care fraud: NPIs 1000000055-1000000059")
    print(f"  Patient cramming:  NPIs 1000000060-1000000062")
    print(f"  TPA ring:          billing=1000000070, servicing=1000000071-1000000076")
    print(f"  Rats scurry:       pairs (1000000080,1000000081) and (1000000082,1000000083)")


if __name__ == "__main__":
    main()
