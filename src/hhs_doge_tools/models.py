"""Pydantic data models for providers, claims, and address matching."""

from pydantic import BaseModel


class Provider(BaseModel):
    """A healthcare provider from the NPPES registry."""

    npi: str
    first_name: str = ""
    last_name: str = ""
    org_name: str = ""
    address_line1: str = ""
    address_line2: str = ""
    city: str = ""
    state: str = ""
    zip5: str = ""
    taxonomy_code: str = ""
    taxonomy_desc: str = ""
    enumeration_date: str = ""
    entity_type: str = ""  # "1" = individual, "2" = organization


class Claim(BaseModel):
    """A summarized claim row from the HHS Medicaid dataset."""

    billing_npi: str
    servicing_npi: str = ""
    hcpcs_code: str = ""
    year: int = 0
    beneficiaries: int = 0
    claims: int = 0
    total_paid: float = 0.0


class AddressMatch(BaseModel):
    """A group of providers sharing the same normalized street address."""

    normalized_address: str
    city: str
    state: str
    zip5: str
    provider_npis: list[str]
    provider_count: int
