"""
load.py — Load Medicaid provider spending data and filter to subsets.

Expects parquet or CSV files in ../data/. Download from:
  https://opendata.hhs.gov/datasets/medicaid-provider-spending/

Usage:
    from load import load_spending, filter_npis, filter_state

    df = load_spending()                          # full dataset
    df = load_spending("data/subset.parquet")     # specific file
    sub = filter_npis(df, ["1234567890"])          # by NPI list
"""

from pathlib import Path
import polars as pl

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_spending(path: str | Path | None = None) -> pl.LazyFrame:
    """Load spending data as a LazyFrame. Auto-detects parquet vs CSV."""
    if path is not None:
        p = Path(path)
    else:
        # look for any parquet in data/, fall back to csv
        parquets = sorted(DATA_DIR.glob("*.parquet"))
        csvs = sorted(DATA_DIR.glob("*.csv"))
        if parquets:
            p = parquets[0]
        elif csvs:
            p = csvs[0]
        else:
            raise FileNotFoundError(
                f"No parquet or CSV files in {DATA_DIR}. "
                "Download from https://opendata.hhs.gov/datasets/medicaid-provider-spending/"
            )

    print(f"Loading {p.name} ...")
    if p.suffix == ".parquet":
        return pl.scan_parquet(p)
    elif p.suffix == ".csv":
        return pl.scan_csv(p)
    else:
        raise ValueError(f"Unsupported file type: {p.suffix}")


def filter_npis(lf: pl.LazyFrame, npis: list[str]) -> pl.LazyFrame:
    """Filter to rows where billing OR servicing NPI is in the list."""
    return lf.filter(
        pl.col("BILLING_PROVIDER_NPI_NUM").cast(pl.Utf8).is_in(npis)
        | pl.col("SERVICING_PROVIDER_NPI_NUM").cast(pl.Utf8).is_in(npis)
    )


def filter_hcpcs(lf: pl.LazyFrame, codes: list[str]) -> pl.LazyFrame:
    """Filter to specific HCPCS codes."""
    return lf.filter(pl.col("HCPCS_CODE").is_in(codes))


def filter_date_range(lf: pl.LazyFrame, start: str, end: str) -> pl.LazyFrame:
    """Filter by CLAIM_FROM_MONTH between start and end (YYYY-MM-01 format)."""
    return lf.filter(
        (pl.col("CLAIM_FROM_MONTH") >= start)
        & (pl.col("CLAIM_FROM_MONTH") <= end)
    )


def collect_and_save(lf: pl.LazyFrame, name: str) -> pl.DataFrame:
    """Collect a LazyFrame and save to data/ as parquet."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = lf.collect()
    out = DATA_DIR / f"{name}.parquet"
    df.write_parquet(out)
    print(f"Saved {len(df)} rows to {out}")
    return df
