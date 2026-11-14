from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    """Strict, API-safe base model shared by all domain contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        use_enum_values=False,
    )

