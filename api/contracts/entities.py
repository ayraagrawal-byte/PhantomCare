from datetime import date
from enum import StrEnum

from pydantic import Field, field_validator

from api.contracts.base import ContractModel
from api.contracts.evidence import EvidenceRecord


class OwnerType(StrEnum):
    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"
    UNKNOWN = "unknown"


class Address(ContractModel):
    raw: str = Field(min_length=1, max_length=500)
    normalized: str = Field(min_length=1, max_length=500)
    building_key: str = Field(min_length=1, max_length=500)
    suite: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=10)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    normalization_confidence: float = Field(default=1.0, ge=0, le=1)
    warnings: tuple[str, ...] = ()

    @field_validator("state")
    @classmethod
    def uppercase_state(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class Hospice(ContractModel):
    enrollment_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=500)
    address: Address
    npi: str | None = Field(default=None, pattern=r"^\d{10}$")
    ccn: str | None = Field(default=None, min_length=1, max_length=20)
    evidence: tuple[EvidenceRecord, ...] = Field(min_length=1)


class Owner(ContractModel):
    owner_id: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    owner_type: OwnerType
    address: Address | None = None
    is_masked: bool
    evidence: tuple[EvidenceRecord, ...] = Field(min_length=1)

    @field_validator("is_masked")
    @classmethod
    def require_masked_individuals(cls, value: bool, info) -> bool:
        if info.data.get("owner_type") == OwnerType.INDIVIDUAL and not value:
            raise ValueError("individual owners must be masked in application contracts")
        return value


class Ownership(ContractModel):
    enrollment_id: str = Field(min_length=1, max_length=100)
    owner_id: str = Field(min_length=1, max_length=100)
    ownership_percent: float | None = Field(default=None, ge=0, le=100)
    effective_date: date | None = None
    evidence: tuple[EvidenceRecord, ...] = Field(min_length=1)


class Building(ContractModel):
    building_id: str = Field(min_length=1, max_length=100)
    address: Address
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    building_type: str | None = Field(default=None, max_length=200)
    size_sqft: float | None = Field(default=None, gt=0)
    floors: float | None = Field(default=None, gt=0)
    tenant_count: int | None = Field(default=None, ge=0)
    min_suite_sqft: float | None = Field(default=None, gt=0)
    hospice_count: int = Field(default=0, ge=0)
    evidence: tuple[EvidenceRecord, ...] = ()

