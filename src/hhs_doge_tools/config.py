"""Constants, paths, and API configuration."""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
NPI_CACHE_DIR = DATA_DIR / "npi_cache"

# ── HuggingFace dataset ───────────────────────────────────────────────
HF_REPO = "HHS-Official/medicaid-provider-spending"
HF_PARQUET_API = f"https://huggingface.co/api/datasets/{HF_REPO}/parquet"
HF_PARQUET_DOWNLOAD_DELAY = 2.0  # seconds between file downloads to avoid rate limit

# ── NPPES API ──────────────────────────────────────────────────────────
NPPES_API_BASE = "https://npiregistry.cms.hhs.gov/api/"
NPPES_API_VERSION = "2.1"
NPPES_MAX_PER_PAGE = 200
NPPES_MAX_RESULTS = 1200  # API hard cap per query
NPPES_RATE_LIMIT_DELAY = 0.5  # seconds between requests

# ── Analysis defaults ─────────────────────────────────────────────────
OUTLIER_STD_THRESHOLD = 2.0
