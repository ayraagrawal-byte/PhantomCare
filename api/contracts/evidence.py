from enum import StrEnum

from pydantic import AwareDatetime, Field, JsonValue

from api.contracts.base import ContractModel


class SourceDataset(StrEnum):
    CMS_ENROLLMENTS = "cms_hospice_enrollments"
    CMS_OWNERS = "cms_hospice_all_owners"
    CMS_ADDITIONAL_ADDRESSES = "cms_hospice_additional_addresses"
    COSTAR = "costar"
    VEXCEL = "vexcel"
    MATTERPORT = "matterport"
    DERIVED = "derived"


class EvidenceRecord(ContractModel):
    """A stable pointer to the source values supporting a derived claim."""

    source: SourceDataset
    record_id: str = Field(min_length=1, max_length=256)
    retrieved_at: AwareDatetime
    fields: dict[str, JsonValue] = Field(default_factory=dict)
    source_url: str | None = Field(default=None, max_length=2048)
    notes: tuple[str, ...] = ()

