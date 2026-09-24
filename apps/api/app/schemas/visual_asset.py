from typing import Annotated, Literal

from pydantic import ConfigDict, Field, HttpUrl, StringConstraints

from app.schemas.design_control import StrictModel

Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Scenario = Literal["campus_lecture", "cultural_event", "club_recruitment"]


class AssetSource(StrictModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    creator: str = Field(min_length=1, max_length=200)
    source_url: HttpUrl | None = None
    origin: Literal["original", "external"]
    rights: str = Field(min_length=1, max_length=1000)


class AssetMetadata(StrictModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    styles: list[Tag] = Field(default_factory=list, max_length=12)
    scenarios: list[Scenario] = Field(default_factory=list, max_length=3)
    visible_text: str = Field(default="", max_length=2000)
    composition: str = Field(default="", max_length=2000)
    cautions: str = Field(default="", max_length=2000)


class AssetUpload(StrictModel):
    image_base64: str = Field(min_length=1, max_length=14_000_000)
    metadata: AssetMetadata
    source: AssetSource


class AssetEdit(StrictModel):
    expected_revision: int = Field(ge=1, strict=True)
    metadata: AssetMetadata


class AssetReview(StrictModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    expected_revision: int = Field(ge=1, strict=True)
    action: Literal["approve", "withdraw", "reject"]
    reviewer: str = Field(min_length=1, max_length=80)
    note: str = Field(min_length=1, max_length=1000)
    rights_confirmed: bool = False


class AssetSearch(StrictModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    query: str = Field(min_length=1, max_length=1000)
    scenario: Scenario | None = None
    limit: int = Field(default=3, ge=1, le=10, strict=True)


class AssetEnrich(StrictModel):
    expected_revision: int = Field(ge=1, strict=True)
