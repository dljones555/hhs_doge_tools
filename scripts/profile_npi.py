"""
profile_npi.py — Deep-dive into a flagged NPI from the capacity simulation.

Pulls raw data from the subset parquet, computes capacity metrics per
servicing (worker) NPI, and outputs a structured narrative suitable for
piping into an LLM for interpretation.

Usage:
    uv run python scripts/profile_npi.py 1609875186
    uv run python scripts/profile_npi.py 1609875186 --data data/subset_high_value.parquet
    uv run python scripts/profile_npi.py 1609875186 | claude -p "Interpret this provider profile"
"""

import argparse
import json
import sys
from pathlib import Path

import polars as pl

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REF_DIR = DATA_DIR / "reference"
LOOKUP_PATH = REF_DIR / "hcpcs_minutes.json"

MAX_WORK_DAYS = 22
MAX_HOURS_PER_DAY = 14
MAX_MINUTES_PER_MONTH = MAX_WORK_DAYS * MAX_HOURS_PER_DAY * 60  # 18,480


def load_time_lookup() -> dict[str, float]:
    if not LOOKUP_PATH.exists():
        return {
            "99211": 5, "99212": 10, "99213": 20, "99214": 30, "99215": 40,
            "99202": 15, "99203": 30, "99204": 45, "99205": 60,
            "T1019": 15, "T1020": 480, "T2021": 480, "T2020": 480,
            "S5125": 15, "S5130": 60, "S5170": 30,
        }
    with open(LOOKUP_PATH) as f:
        raw = json.load(f)
    return {k: v["minutes"] if isinstance(v, dict) else v for k, v in raw.items()}


def _capacity_for_df(df: pl.DataFrame, times: dict[str, float]):
    """Compute monthly capacity stats from a DataFrame of spending rows."""
    month_code = df.group_by(["CLAIM_FROM_MONTH", "HCPCS_CODE"]).agg([
        pl.col("TOTAL_CLAIMS").sum(),
    ])
    month_min_rows = []
    for r in month_code.iter_rows(named=True):
        mins = times.get(r["HCPCS_CODE"], 15)
        month_min_rows.append({"month": r["CLAIM_FROM_MONTH"], "minutes": r["TOTAL_CLAIMS"] * mins})
    min_df = pl.DataFrame(month_min_rows).group_by("month").agg(pl.col("minutes").sum())

    monthly = df.group_by("CLAIM_FROM_MONTH").agg([
        pl.col("TOTAL_CLAIMS").sum().alias("claims"),
        pl.col("TOTAL_PAID").sum().alias("paid"),
        pl.col("TOTAL_UNIQUE_BENEFICIARIES").max().alias("max_benes"),
        pl.col("HCPCS_CODE").n_unique().alias("n_codes"),
    ]).join(min_df, left_on="CLAIM_FROM_MONTH", right_on="month")

    monthly = monthly.with_columns([
        (pl.col("minutes") / MAX_MINUTES_PER_MONTH).alias("capacity_ratio"),
        (pl.col("minutes") / MAX_WORK_DAYS / 60).alias("hours_per_day"),
    ]).sort("capacity_ratio", descending=True)

    return monthly


def _format_capacity_summary(monthly: pl.DataFrame, n_months: int) -> list[str]:
    """Format capacity summary stats into lines."""
    lines = []
    ratios = monthly["capacity_ratio"]
    peak_ratio = ratios.max()
    avg_ratio = ratios.mean()
    peak_hrs = monthly["hours_per_day"].max()
    peak_benes = monthly["max_benes"].max()
    max_codes = monthly["n_codes"].max()
    avg_codes = monthly["n_codes"].mean()

    flag_impossible = peak_ratio >= 1.0
    flag_high_cap = peak_ratio >= 0.70
    flag_cookie = avg_codes <= 3 and peak_benes >= 50
    flag_family = peak_benes <= 3 and n_months >= 12

    lines.append(f"  Peak capacity ratio: {peak_ratio:.2f} ({peak_ratio:.0f}x human capacity)")
    lines.append(f"  Avg capacity ratio:  {avg_ratio:.2f}")
    lines.append(f"  Peak hours/day:      {peak_hrs:.1f}")
    lines.append(f"  Peak benes/month:    {peak_benes}")
    lines.append(f"  Max distinct codes:  {max_codes}")
    lines.append(f"  Avg distinct codes:  {avg_codes:.2f}")
    lines.append(f"  Impossible hours:    {flag_impossible}")
    lines.append(f"  High capacity:       {flag_high_cap}")
    lines.append(f"  Cookie-cutter:       {flag_cookie}")
    lines.append(f"  Family care:         {flag_family}")
    return lines


def profile_npi(npi: str, data_path: Path, times: dict[str, float]) -> str:
    lf = pl.scan_parquet(data_path)

    df_billing = lf.filter(pl.col("BILLING_PROVIDER_NPI_NUM") == npi).collect()
    df_servicing = lf.filter(pl.col("SERVICING_PROVIDER_NPI_NUM") == npi).collect()

    if len(df_billing) == 0 and len(df_servicing) == 0:
        return f"NPI {npi}: no rows found in {data_path.name}"

    is_billing = len(df_billing) > 0
    is_servicing = len(df_servicing) > 0

    lines = []
    w = lines.append

    # ── Header ──
    # Combine both views for code/date summary
    all_rows = pl.concat([df_billing, df_servicing]).unique()
    codes = sorted(all_rows["HCPCS_CODE"].unique().to_list())
    month_min = all_rows["CLAIM_FROM_MONTH"].min()
    month_max = all_rows["CLAIM_FROM_MONTH"].max()

    w(f"=== NPI PROFILE: {npi} ===")
    w(f"Data source: {data_path.name}")
    if is_billing and is_servicing:
        w("Role: BOTH billing entity and servicing provider")
    elif is_billing:
        w("Role: BILLING ENTITY (submits claims, may not perform services)")
    else:
        w("Role: SERVICING PROVIDER (performs services)")
    w(f"Rows as billing NPI: {len(df_billing)}")
    w(f"Rows as servicing NPI: {len(df_servicing)}")
    w(f"HCPCS codes: {codes}")
    w(f"Active period: {month_min} to {month_max}")
    w(f"Capacity assumption: {MAX_WORK_DAYS} work days/month, {MAX_HOURS_PER_DAY} hrs/day = {MAX_MINUTES_PER_MONTH:,} min/month")
    w("")

    # ══════════════════════════════════════════════════════════════════
    # SERVICING VIEW — this NPI as the person doing the work
    # This is the meaningful capacity measure.
    # ══════════════════════════════════════════════════════════════════
    if is_servicing:
        n_months_serv = df_servicing["CLAIM_FROM_MONTH"].n_unique()
        n_billing_for = df_servicing["BILLING_PROVIDER_NPI_NUM"].n_unique()
        total_claims = df_servicing["TOTAL_CLAIMS"].sum()
        total_paid = df_servicing["TOTAL_PAID"].sum()

        w("=== WORKER CAPACITY (this NPI as servicing provider) ===")
        w(f"Billing NPIs this worker services under: {n_billing_for}")
        w(f"Active months: {n_months_serv}")
        w(f"Total claims: {total_claims:,}")
        w(f"Total paid: ${total_paid:,.2f}")
        w("")

        # Claims by code
        w("--- Claims by HCPCS code ---")
        by_code = df_servicing.group_by("HCPCS_CODE").agg([
            pl.col("TOTAL_CLAIMS").sum(),
            pl.col("TOTAL_PAID").sum(),
        ]).sort("TOTAL_CLAIMS", descending=True)
        for row in by_code.iter_rows(named=True):
            code = row["HCPCS_CODE"]
            mins = times.get(code, 15)
            total_mins = row["TOTAL_CLAIMS"] * mins
            w(f"  {code}: {row['TOTAL_CLAIMS']:>7,} claims x {mins} min = {total_mins:>10,.0f} min, paid ${row['TOTAL_PAID']:>12,.2f}")
        w("")

        # Capacity
        monthly_serv = _capacity_for_df(df_servicing, times)
        w("--- Capacity flags ---")
        for line in _format_capacity_summary(monthly_serv, n_months_serv):
            w(line)
        w("")

        # Top months
        top_n = min(10, len(monthly_serv))
        w(f"--- Top {top_n} months by capacity ratio ---")
        for row in monthly_serv.head(top_n).iter_rows(named=True):
            w(f"  {row['CLAIM_FROM_MONTH']}: {row['claims']:>5,} claims, {row['minutes']:>10,.0f} min, "
              f"ratio={row['capacity_ratio']:.2f}, {row['hours_per_day']:.1f} hrs/day, "
              f"{row['max_benes']} benes, {row['n_codes']} codes, "
              f"paid ${row['paid']:,.2f}")
        w("")

        # Peak month detail
        peak_month = monthly_serv["CLAIM_FROM_MONTH"][0]
        w(f"--- Peak month ({peak_month}) row-level detail ---")
        peak = df_servicing.filter(pl.col("CLAIM_FROM_MONTH") == peak_month).sort("TOTAL_CLAIMS", descending=True)
        for row in peak.head(20).iter_rows(named=True):
            code = row["HCPCS_CODE"]
            mins = times.get(code, 15)
            implied = row["TOTAL_CLAIMS"] * mins
            w(f"  Billing={row['BILLING_PROVIDER_NPI_NUM']}  {code}  claims={row['TOTAL_CLAIMS']}  "
              f"benes={row['TOTAL_UNIQUE_BENEFICIARIES']}  paid=${row['TOTAL_PAID']:,.2f}  "
              f"-> {implied:,} min ({implied/60:.1f} hrs)")
        if len(peak) > 20:
            w(f"  ... and {len(peak) - 20} more rows")
        w("")

    # ══════════════════════════════════════════════════════════════════
    # BILLING VIEW — this NPI as the entity submitting claims
    # Capacity here is aggregate across all servicing providers.
    # ══════════════════════════════════════════════════════════════════
    if is_billing:
        n_servicing_npis = df_billing["SERVICING_PROVIDER_NPI_NUM"].n_unique()
        n_months_bill = df_billing["CLAIM_FROM_MONTH"].n_unique()
        total_claims = df_billing["TOTAL_CLAIMS"].sum()
        total_paid = df_billing["TOTAL_PAID"].sum()
        is_tpa = n_servicing_npis > 3

        w("=== BILLING ENTITY VIEW ===")
        w(f"Unique servicing NPIs: {n_servicing_npis}")
        w(f"TPA pattern (4+ servicing NPIs): {is_tpa}")
        w(f"Active months: {n_months_bill}")
        w(f"Total claims submitted: {total_claims:,}")
        w(f"Total paid: ${total_paid:,.2f}")
        if n_servicing_npis > 1:
            w(f"NOTE: Capacity below is AGGREGATE across {n_servicing_npis} servicing NPIs.")
            w(f"Individual worker capacity is shown above in WORKER CAPACITY section.")
        w("")

        # Claims by code
        w("--- Claims by HCPCS code ---")
        by_code = df_billing.group_by("HCPCS_CODE").agg([
            pl.col("TOTAL_CLAIMS").sum(),
            pl.col("TOTAL_PAID").sum(),
        ]).sort("TOTAL_CLAIMS", descending=True)
        for row in by_code.iter_rows(named=True):
            code = row["HCPCS_CODE"]
            mins = times.get(code, 15)
            total_mins = row["TOTAL_CLAIMS"] * mins
            w(f"  {code}: {row['TOTAL_CLAIMS']:>7,} claims x {mins} min = {total_mins:>10,.0f} min, paid ${row['TOTAL_PAID']:>12,.2f}")
        w("")

        # Aggregate capacity (for context, not for flagging)
        monthly_bill = _capacity_for_df(df_billing, times)
        w("--- Aggregate capacity (all workers combined) ---")
        for line in _format_capacity_summary(monthly_bill, n_months_bill):
            w(line)
        w("")

        # Servicing NPI breakdown with individual capacity
        if n_servicing_npis > 1:
            w(f"=== SERVICING NPI BREAKDOWN (TOP 20) ===")
            by_serv = df_billing.group_by("SERVICING_PROVIDER_NPI_NUM").agg([
                pl.col("TOTAL_CLAIMS").sum(),
                pl.col("TOTAL_PAID").sum(),
                pl.col("HCPCS_CODE").n_unique().alias("n_codes"),
                pl.col("CLAIM_FROM_MONTH").n_unique().alias("active_months"),
            ]).sort("TOTAL_CLAIMS", descending=True)

            for row in by_serv.head(20).iter_rows(named=True):
                serv_npi = row["SERVICING_PROVIDER_NPI_NUM"]
                serv_label = str(serv_npi) if serv_npi is not None else "None"
                # Compute individual capacity for this servicing NPI
                if serv_npi is not None:
                    serv_df = df_billing.filter(pl.col("SERVICING_PROVIDER_NPI_NUM") == serv_npi)
                else:
                    serv_df = df_billing.filter(pl.col("SERVICING_PROVIDER_NPI_NUM").is_null())

                if len(serv_df) > 0:
                    serv_monthly = _capacity_for_df(serv_df, times)
                    peak_ratio = serv_monthly["capacity_ratio"].max()
                    peak_hrs = serv_monthly["hours_per_day"].max()
                    flag = " *** IMPOSSIBLE" if peak_ratio >= 1.0 else (" * HIGH" if peak_ratio >= 0.70 else "")
                    cap_str = f"peak={peak_ratio:.2f} ({peak_hrs:.1f} hrs/day){flag}"
                else:
                    cap_str = "no data"

                w(f"  {serv_label}: {row['TOTAL_CLAIMS']:>6,} claims, "
                  f"${row['TOTAL_PAID']:>10,.2f}, {row['n_codes']} codes, "
                  f"{row['active_months']} months, {cap_str}")
            if len(by_serv) > 20:
                w(f"  ... and {len(by_serv) - 20} more servicing NPIs")
            w("")

        # Peak month detail
        peak_month = monthly_bill.sort("capacity_ratio", descending=True)["CLAIM_FROM_MONTH"][0]
        w(f"--- Peak billing month ({peak_month}) row-level detail ---")
        peak = df_billing.filter(pl.col("CLAIM_FROM_MONTH") == peak_month).sort("TOTAL_CLAIMS", descending=True)
        for row in peak.head(25).iter_rows(named=True):
            code = row["HCPCS_CODE"]
            mins = times.get(code, 15)
            implied = row["TOTAL_CLAIMS"] * mins
            servicing = row["SERVICING_PROVIDER_NPI_NUM"] or "None"
            w(f"  Servicing={servicing}  {code}  claims={row['TOTAL_CLAIMS']}  "
              f"benes={row['TOTAL_UNIQUE_BENEFICIARIES']}  paid=${row['TOTAL_PAID']:,.2f}  "
              f"-> {implied:,} min ({implied/60:.1f} hrs)")
        if len(peak) > 25:
            w(f"  ... and {len(peak) - 25} more rows")
        w("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Profile an NPI from capacity simulation results",
        epilog="Pipe output to an LLM: uv run python scripts/profile_npi.py 1234567890 | claude -p 'Interpret this'",
    )
    parser.add_argument("npi", help="NPI to profile (billing or servicing)")
    parser.add_argument("--data", type=str, default=None,
                        help="Path to parquet file (default: data/subset_high_value.parquet)")
    args = parser.parse_args()

    data_path = Path(args.data) if args.data else DATA_DIR / "subset_high_value.parquet"
    if not data_path.exists():
        data_path = DATA_DIR / "medicaid-provider-spending.parquet"
    if not data_path.exists():
        print(f"ERROR: No data file found. Tried subset and full dataset in {DATA_DIR}", file=sys.stderr)
        sys.exit(1)

    times = load_time_lookup()
    output = profile_npi(args.npi, data_path, times)
    print(output)


if __name__ == "__main__":
    main()
