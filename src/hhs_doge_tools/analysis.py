"""Fraud analysis query foundation — averages, outliers, volume summaries."""

import polars as pl

from .config import OUTLIER_STD_THRESHOLD


def _find_paid_column(df: pl.DataFrame) -> str:
    """Find the total-paid column (case-insensitive)."""
    for col in df.columns:
        if "paid" in col.lower() or "payment" in col.lower():
            return col
    raise ValueError(f"No paid/payment column found. Columns: {df.columns}")


def _find_hcpcs_column(df: pl.DataFrame) -> str:
    """Find the HCPCS/procedure code column."""
    for col in df.columns:
        lower = col.lower()
        if "hcpcs" in lower or "procedure" in lower or "cpt" in lower:
            return col
    raise ValueError(f"No HCPCS/procedure column found. Columns: {df.columns}")


def _find_npi_column(df: pl.DataFrame) -> str:
    """Find the NPI column."""
    for col in df.columns:
        if "npi" in col.lower():
            return col
    raise ValueError(f"No NPI column found. Columns: {df.columns}")


def avg_paid_by_hcpcs(df: pl.DataFrame) -> pl.DataFrame:
    """Average total paid per HCPCS code, sorted descending.

    Returns DataFrame with columns: hcpcs_code, avg_paid, provider_count, total_claims
    """
    paid_col = _find_paid_column(df)
    hcpcs_col = _find_hcpcs_column(df)
    npi_col = _find_npi_column(df)

    return (
        df.group_by(hcpcs_col)
        .agg(
            pl.col(paid_col).mean().alias("avg_paid"),
            pl.col(npi_col).n_unique().alias("provider_count"),
            pl.len().alias("total_rows"),
        )
        .sort("avg_paid", descending=True)
    )


def find_outliers(
    df: pl.DataFrame,
    hcpcs_code: str,
    *,
    std_threshold: float = OUTLIER_STD_THRESHOLD,
) -> pl.DataFrame:
    """Find providers billing significantly above average for a specific HCPCS code.

    Returns rows where the provider's average paid amount exceeds
    (global_mean + std_threshold * global_std) for that code.
    """
    paid_col = _find_paid_column(df)
    hcpcs_col = _find_hcpcs_column(df)
    npi_col = _find_npi_column(df)

    code_df = df.filter(pl.col(hcpcs_col) == hcpcs_code)
    if code_df.is_empty():
        return code_df

    global_mean = code_df[paid_col].mean()
    global_std = code_df[paid_col].std()

    if global_std is None or global_std == 0:
        return code_df.clear()

    threshold = global_mean + std_threshold * global_std

    # Average per provider, then filter outliers
    per_provider = (
        code_df.group_by(npi_col)
        .agg(
            pl.col(paid_col).mean().alias("provider_avg_paid"),
            pl.col(paid_col).sum().alias("provider_total_paid"),
            pl.len().alias("row_count"),
        )
        .filter(pl.col("provider_avg_paid") > threshold)
        .sort("provider_avg_paid", descending=True)
        .with_columns(
            pl.lit(global_mean).alias("code_avg"),
            pl.lit(global_std).alias("code_std"),
            pl.lit(threshold).alias("outlier_threshold"),
        )
    )

    return per_provider


def billing_volume_summary(df: pl.DataFrame) -> pl.DataFrame:
    """Summary of billing volume per provider: total rows, total paid, unique codes."""
    paid_col = _find_paid_column(df)
    hcpcs_col = _find_hcpcs_column(df)
    npi_col = _find_npi_column(df)

    return (
        df.group_by(npi_col)
        .agg(
            pl.col(paid_col).sum().alias("total_paid"),
            pl.col(paid_col).mean().alias("avg_paid"),
            pl.len().alias("total_rows"),
            pl.col(hcpcs_col).n_unique().alias("unique_codes"),
        )
        .sort("total_paid", descending=True)
    )
