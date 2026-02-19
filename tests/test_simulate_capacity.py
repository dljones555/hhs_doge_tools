"""Tests for simulate_capacity.py — verify fraud detection against known patterns."""

import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from simulate_capacity import (
    estimate_minutes,
    run_capacity_analysis,
    MAX_MINUTES_PER_MONTH,
    HCPCS_MINUTES,
)


# ── Helpers ──

def make_rows(npi, servicing_npi=None, codes_claims=None, months=None):
    """Build a list of spending row dicts for one provider."""
    if servicing_npi is None:
        servicing_npi = npi
    if months is None:
        months = ["2024-01-01"]
    rows = []
    for month in months:
        for code, claims, benes, paid in codes_claims:
            rows.append({
                "BILLING_PROVIDER_NPI_NUM": npi,
                "SERVICING_PROVIDER_NPI_NUM": servicing_npi,
                "HCPCS_CODE": code,
                "CLAIM_FROM_MONTH": month,
                "TOTAL_UNIQUE_BENEFICIARIES": benes,
                "TOTAL_CLAIMS": claims,
                "TOTAL_PAID": paid,
            })
    return rows


def make_lf(rows):
    """Convert row dicts to a Polars LazyFrame."""
    return pl.DataFrame(rows).lazy()


def get_npi_row(summary, npi):
    """Pull a single NPI's row from the summary DataFrame (keyed by WORKER_NPI)."""
    filtered = summary.filter(pl.col("WORKER_NPI") == npi)
    assert len(filtered) == 1, f"Expected 1 row for NPI {npi}, got {len(filtered)}"
    return filtered.row(0, named=True)


# ── estimate_minutes tests ──

class TestEstimateMinutes:
    def test_known_code(self):
        assert estimate_minutes("99213") == 20
        assert estimate_minutes("99215") == 40
        assert estimate_minutes("T1020") == 480

    def test_unknown_em_code(self):
        """Unknown 992xx code should get generic E&M estimate."""
        assert estimate_minutes("99218") == 20

    def test_unknown_99_prefix(self):
        assert estimate_minutes("99600") == 15

    def test_home_care_fallback(self):
        """Unknown T1/T2/S5 codes should get home/community default."""
        assert estimate_minutes("T1999") == 60
        assert estimate_minutes("T2099") == 60
        assert estimate_minutes("S5999") == 60

    def test_surgical_range(self):
        """Numeric codes in 10000-69999 should get a reasonable surgical estimate.
        With CMS RVU lookup loaded, exact value comes from Work RVU."""
        mins = estimate_minutes("27500")
        assert 20 <= mins <= 60  # reasonable surgical range

    def test_alpha_fallback(self):
        """Unknown alpha-prefixed code gets HCPCS level II default."""
        assert estimate_minutes("J3301") == 20

    def test_pure_fallback(self):
        """Codes that match nothing get 15 min."""
        assert estimate_minutes("99999") == 15


# ── Flag detection tests ──

class TestImpossibleHours:
    def test_flags_impossible(self):
        """A provider billing 1000 x 99215 (40min each) in one month = 666 hrs.
        That's ~30 hrs/day. Must flag impossible."""
        rows = make_rows(
            npi=1, codes_claims=[("99215", 1000, 500, 50000.0)],
        )
        summary = run_capacity_analysis(make_lf(rows))
        row = get_npi_row(summary, 1)
        assert row["flag_impossible_hours"] is True
        assert row["peak_hours_per_day"] > 24

    def test_legit_not_flagged(self):
        """A provider billing 20 x 99213 (15min each) = 5 hrs. Should not flag."""
        rows = make_rows(
            npi=2, codes_claims=[("99213", 20, 18, 2000.0)],
        )
        summary = run_capacity_analysis(make_lf(rows))
        row = get_npi_row(summary, 2)
        assert row["flag_impossible_hours"] is False
        assert row["flag_high_capacity"] is False


class TestCookieCutter:
    def test_flags_cookie_cutter(self):
        """2 codes, 200 patients each = cookie-cutter assembly line."""
        rows = make_rows(
            npi=10,
            codes_claims=[
                ("99213", 200, 200, 20000.0),
                ("99214", 200, 200, 30000.0),
            ],
        )
        summary = run_capacity_analysis(make_lf(rows))
        row = get_npi_row(summary, 10)
        assert row["flag_cookie_cutter"] is True

    def test_diverse_not_flagged(self):
        """7 codes = not cookie-cutter even with high volume."""
        rows = make_rows(
            npi=11,
            codes_claims=[
                ("99211", 10, 10, 500.0),
                ("99212", 10, 10, 800.0),
                ("99213", 30, 25, 3000.0),
                ("99214", 20, 18, 4000.0),
                ("99215", 5, 5, 1500.0),
                ("27447", 2, 2, 5000.0),
                ("29881", 3, 3, 2000.0),
            ],
        )
        summary = run_capacity_analysis(make_lf(rows))
        row = get_npi_row(summary, 11)
        assert row["flag_cookie_cutter"] is False


class TestFamilyCare:
    def test_flags_family_pattern(self):
        """1 beneficiary, billing every month for 2 years = family care."""
        months = [f"2023-{m:02d}-01" for m in range(1, 13)] + \
                 [f"2024-{m:02d}-01" for m in range(1, 13)]
        rows = make_rows(
            npi=20,
            codes_claims=[("T1019", 28, 1, 4200.0)],
            months=months,
        )
        summary = run_capacity_analysis(make_lf(rows))
        row = get_npi_row(summary, 20)
        assert row["flag_family_care"] is True
        assert row["peak_benes_per_month"] <= 3

    def test_many_benes_not_flagged(self):
        """50 beneficiaries = not a family care pattern."""
        months = [f"2024-{m:02d}-01" for m in range(1, 13)]
        rows = make_rows(
            npi=21,
            codes_claims=[("T1019", 50, 50, 7500.0)],
            months=months,
        )
        summary = run_capacity_analysis(make_lf(rows))
        row = get_npi_row(summary, 21)
        assert row["flag_family_care"] is False


class TestTPAPattern:
    def test_flags_tpa(self):
        """One billing NPI with 5 different servicing NPIs = TPA ring.
        With worker-level grouping, each servicing NPI gets its own row.
        The billing NPI only gets a TPA flag if it also appears as a worker."""
        rows = []
        for srv in range(101, 106):
            rows.extend(make_rows(
                npi=30, servicing_npi=srv,
                codes_claims=[("T2021", 20, 15, 8000.0)],
            ))
        # Also add a row where billing NPI 30 services itself, so it appears as a worker
        rows.extend(make_rows(
            npi=30, servicing_npi=30,
            codes_claims=[("99213", 5, 5, 500.0)],
        ))
        summary = run_capacity_analysis(make_lf(rows))
        # Billing NPI 30 is also a worker and should have the TPA flag
        row = get_npi_row(summary, 30)
        assert row["flag_tpa_pattern"] is True
        assert row["max_servicing_npis"] >= 5
        # Individual servicing NPIs should have their own capacity rows
        for srv in range(101, 106):
            srv_row = get_npi_row(summary, srv)
            assert srv_row["flag_tpa_pattern"] is False  # they're workers, not billing entities

    def test_self_billing_not_flagged(self):
        """Provider billing for themselves only = not TPA."""
        rows = make_rows(
            npi=31, codes_claims=[("99213", 30, 25, 3000.0)],
        )
        summary = run_capacity_analysis(make_lf(rows))
        row = get_npi_row(summary, 31)
        assert row["flag_tpa_pattern"] is False


# ── Scoring tests ──

class TestSuspicionScore:
    def test_impossible_scores_higher_than_legit(self):
        """Impossible provider must outscore a legit one."""
        rows = (
            make_rows(npi=40, codes_claims=[("99215", 1000, 500, 50000.0)])
            + make_rows(npi=41, codes_claims=[("99213", 10, 8, 1000.0)])
        )
        summary = run_capacity_analysis(make_lf(rows))
        fraud = get_npi_row(summary, 40)
        legit = get_npi_row(summary, 41)
        assert fraud["suspicion_score"] > legit["suspicion_score"]

    def test_multiple_flags_stack(self):
        """A provider with impossible hours + cookie-cutter should score
        higher than one with just impossible hours."""
        # Impossible + cookie-cutter: 2 codes, huge volume
        rows_both = make_rows(
            npi=50,
            codes_claims=[
                ("99214", 500, 300, 50000.0),
                ("99215", 500, 300, 80000.0),
            ],
        )
        # Impossible only: many codes, huge volume
        rows_one = make_rows(
            npi=51,
            codes_claims=[
                ("99211", 100, 80, 5000.0),
                ("99212", 100, 80, 8000.0),
                ("99213", 100, 80, 10000.0),
                ("99214", 100, 80, 15000.0),
                ("99215", 100, 80, 20000.0),
            ],
        )
        summary = run_capacity_analysis(make_lf(rows_both + rows_one))
        both = get_npi_row(summary, 50)
        one = get_npi_row(summary, 51)
        assert both["flag_cookie_cutter"] is True
        assert one["flag_cookie_cutter"] is False
        assert both["suspicion_score"] > one["suspicion_score"]

    def test_clean_provider_low_score(self):
        """A small legit provider should have a very low score."""
        rows = make_rows(
            npi=60,
            codes_claims=[
                ("99213", 15, 12, 1500.0),
                ("99214", 8, 7, 1600.0),
                ("99211", 5, 5, 250.0),
                ("29881", 2, 2, 3000.0),
            ],
        )
        summary = run_capacity_analysis(make_lf(rows))
        row = get_npi_row(summary, 60)
        assert row["suspicion_score"] < 20
        assert row["flag_impossible_hours"] is False
        assert row["flag_cookie_cutter"] is False
        assert row["flag_family_care"] is False
        assert row["flag_tpa_pattern"] is False


# ── Edge cases ──

class TestEdgeCases:
    def test_single_row(self):
        """Analysis shouldn't crash on a single row of data."""
        rows = make_rows(npi=70, codes_claims=[("99213", 1, 1, 100.0)])
        summary = run_capacity_analysis(make_lf(rows))
        assert len(summary) == 1

    def test_multiple_months_aggregation(self):
        """Peak should be the worst single month, not cumulative."""
        months = ["2024-01-01", "2024-02-01", "2024-03-01"]
        # 50 claims/month x 15min = 12.5 hrs/month = 0.57 hrs/day — fine
        rows = make_rows(
            npi=71,
            codes_claims=[("99213", 50, 40, 5000.0)],
            months=months,
        )
        summary = run_capacity_analysis(make_lf(rows))
        row = get_npi_row(summary, 71)
        # Peak should reflect ONE month (50 claims), not all 3 (150)
        assert row["peak_hours_per_day"] < 2
        assert row["active_months"] == 3
