from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, Field, HttpUrl, model_validator

CAMS_LAYER = (
    "https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/"
    "eGIS_Addressing_ADDRESS_POINTSv2/FeatureServer/0"
)
CAMS_SOURCE = "LA County CAMS"
CENSUS_SOURCE = "U.S. Census Bureau Geocoder"
CENSUS_GEOCODER = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
SEARCH_RADIUS_METERS = 100


class CamsLocation(BaseModel):
    source: Literal["LA County CAMS"] = CAMS_SOURCE
    feature_id: int = Field(gt=0)
    county_record_source: str
    matched_address: str
    confidence: Literal["exact", "standardized"]
    precision: Literal["address_point"] = "address_point"
    latitude: float = Field(ge=33.2, le=35)
    longitude: float = Field(ge=-119, le=-117.4)


class CamsResult(BaseModel):
    building_key: str
    location: CamsLocation | None = None
    reason: Literal[
        "unsupported_address",
        "no_address_match",
        "community_mismatch",
        "unit_records_only",
        "ambiguous_points",
        "invalid_geometry",
    ] | None = None

    @model_validator(mode="after")
    def check_outcome(self) -> Self:
        if (self.location is None) == (self.reason is None):
            raise ValueError("CAMS result requires one location or one rejection reason")
        return self


class CamsCache(BaseModel):
    schema_version: Literal[1] = 1
    source_url: str
    retrieved_at: AwareDatetime
    results: dict[str, CamsResult]


class ApproximateLocation(BaseModel):
    source: Literal["U.S. Census Bureau Geocoder"] = CENSUS_SOURCE
    confidence: Literal["approximate"] = "approximate"
    precision: Literal["street_interpolation"] = "street_interpolation"
    matched_address: str
    address_basis: Literal["full_address", "civic_address_only"] = "full_address"
    county: Literal["Los Angeles", "San Bernardino", "Ventura"] = "Los Angeles"
    tiger_line_id: str
    benchmark: str
    latitude: float = Field(ge=33.2, le=35)
    longitude: float = Field(ge=-119, le=-117.4)


class SupplementalResult(BaseModel):
    building_key: str
    verified: CamsLocation | None = None
    anchor: ApproximateLocation | None = None
    reason: Literal[
        "no_defensible_anchor", "street_interpolation_only", "unit_or_conflicting_points",
        "corroborated_address_point",
    ]
    nearby_matching_feature_ids: list[int] = Field(default_factory=list)
    verified_distance_meters: float | None = Field(
        default=None, ge=0, le=SEARCH_RADIUS_METERS
    )

    @model_validator(mode="after")
    def check_evidence(self) -> Self:
        if self.verified is not None:
            if (
                self.anchor is None
                or self.verified_distance_meters is None
                or self.verified.feature_id not in self.nearby_matching_feature_ids
                or self.reason != "corroborated_address_point"
            ):
                raise ValueError("Verification requires a corroborating point inside the radius")
        elif (
            self.reason == "corroborated_address_point" or self.verified_distance_meters is not None
        ):
            raise ValueError("Verification evidence requires a verified point")
        if (self.anchor is None) != (self.reason == "no_defensible_anchor"):
            raise ValueError("Only an unresolved address may lack a Census anchor")
        return self


class SupplementalCache(BaseModel):
    schema_version: Literal[1] = 1
    census_url: Literal[
        "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
    ] = CENSUS_GEOCODER
    cams_url: str = CAMS_LAYER
    search_radius_meters: Literal[100] = SEARCH_RADIUS_METERS
    retrieved_at: AwareDatetime
    results: dict[str, SupplementalResult]


class ReviewedLocation(BaseModel):
    source: str = Field(min_length=1)
    record_id: str = Field(min_length=1)
    matched_address: str
    county: Literal["Los Angeles", "Ventura"]
    confidence: Literal["verified", "approximate"]
    precision: Literal["address_point", "parcel_interior", "street_interpolation"]
    latitude: float = Field(ge=33.2, le=35)
    longitude: float = Field(ge=-119, le=-117.4)
    evidence_urls: list[HttpUrl] = Field(min_length=2)

    @model_validator(mode="after")
    def check_precision(self) -> Self:
        if (self.confidence == "verified") != (self.precision == "address_point"):
            raise ValueError("Only reviewed address points are verified")
        return self


class ReviewedResult(BaseModel):
    building_key: str
    original_cms_address: str
    notes: str
    location: ReviewedLocation | None = None


class ReviewedCache(BaseModel):
    schema_version: Literal[1] = 1
    results: dict[str, ReviewedResult]
