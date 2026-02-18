"""HuggingFace parquet dataset loader using Polars lazy scan."""

from pathlib import Path

import polars as pl

from .config import DATA_DIR, HF_PARQUET_URL


def scan_hf_dataset() -> pl.LazyFrame:
    """Create a lazy scan of the full HF Medicaid provider spending dataset.

    Uses the hf:// URL scheme so Polars streams data without downloading
    the entire ~6GB dataset.
    """
    return pl.scan_parquet(HF_PARQUET_URL)


def load_city_subset(
    npi_list: list[str],
    *,
    output_name: str = "city_subset",
) -> pl.DataFrame:
    """Filter the HF dataset to only rows matching the given NPI list.

    Args:
        npi_list: List of NPI strings to filter on.
        output_name: Base name for the saved parquet file.

    Returns:
        Filtered DataFrame (collected, not lazy).
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / f"{output_name}.parquet"

    if out_path.exists():
        print(f"  Loading cached subset from {out_path}")
        return pl.read_parquet(out_path)

    print(f"  Scanning HF dataset for {len(npi_list)} NPIs...")
    lf = scan_hf_dataset()

    # Discover the actual NPI column name from the schema
    npi_col = _find_npi_column(lf)
    print(f"  Using NPI column: {npi_col}")

    # Filter: cast NPI column to string for safe comparison
    filtered = lf.filter(pl.col(npi_col).cast(pl.Utf8).is_in(npi_list))

    print("  Collecting filtered rows (this may take a while on first run)...")
    df = filtered.collect()
    print(f"  Got {len(df)} rows for {df[npi_col].n_unique()} unique NPIs")

    df.write_parquet(out_path)
    print(f"  Saved to {out_path}")
    return df


def _find_npi_column(lf: pl.LazyFrame) -> str:
    """Identify the NPI column name from schema (case-insensitive search)."""
    schema = lf.collect_schema()
    for col_name in schema.names():
        if "npi" in col_name.lower():
            return col_name
    raise ValueError(
        f"No NPI column found in dataset. Columns: {schema.names()}"
    )


def load_local_subset(name: str = "city_subset") -> pl.DataFrame:
    """Load a previously-saved local parquet subset."""
    path = DATA_DIR / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"No local subset at {path}. Run city-extract first."
        )
    return pl.read_parquet(path)


def get_dataset_schema() -> dict[str, str]:
    """Peek at the HF dataset schema without downloading data."""
    lf = scan_hf_dataset()
    schema = lf.collect_schema()
    return {name: str(dtype) for name, dtype in zip(schema.names(), schema.dtypes())}
