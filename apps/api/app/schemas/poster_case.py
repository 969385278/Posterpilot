from typing import Annotated, Literal

from pydantic import Field, HttpUrl, StringConstraints, model_validator

from app.schemas.design_control import Identifier, PriorityRole, ReferenceAspect, StrictModel

Hex = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
AssetName = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*\.(jpg|jpeg|png|webp)$")]


class CaseSource(StrictModel):
    creator: str = Field(min_length=1)
    institution: str = Field(min_length=1)
    source_url: HttpUrl
    image_url: HttpUrl
    rights: str = Field(min_length=1)
    rights_url: HttpUrl
    retrieved_at: str = Field(min_length=1)
    image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CaseSearchArguments(StrictModel):
    query: str = Field(min_length=1, max_length=300)
    aspects: list[ReferenceAspect] = Field(min_length=1, max_length=4)
    style: str = Field(default="", max_length=100)
    limit: int = Field(default=2, ge=1, le=3, strict=True)

    @model_validator(mode="after")
    def validate_query_and_aspects(self):
        if not self.query.strip() or len(self.aspects) != len(set(self.aspects)):
            raise ValueError("case search needs a nonempty query and unique aspects")
        return self


class PosterCase(StrictModel):
    id: Identifier
    title: str = Field(min_length=1, max_length=200)
    original_title: str = Field(min_length=1, max_length=300)
    image_asset: AssetName
    styles: list[str] = Field(min_length=1, max_length=8)
    scenarios: list[str] = Field(min_length=1, max_length=8)
    features: dict[ReferenceAspect, str]
    palette: list[Hex] = Field(default_factory=list, max_length=6)
    suggested_priority: list[PriorityRole] = Field(default_factory=list, max_length=5)
    # Curator-selected supported approximations, not recovered original fonts/coordinates.
    title_font_style: Literal["serif", "sans", "sans_bold"] = "sans"
    composition_preset: Literal["top_title", "bottom_title", "center_title"] = "top_title"
    cautions: list[str] = Field(default_factory=list, max_length=8)
    source: CaseSource
    status: Literal["candidate", "curated", "rejected"] = "candidate"
    analysis_basis: Literal["assistant_visual_review", "human_review", "unreviewed"] = "unreviewed"
    user_acceptance: Literal["pending", "accepted", "rejected"] = "pending"

    @model_validator(mode="after")
    def validate_features_and_review(self):
        if set(self.features) != {"palette", "typography", "composition", "hierarchy"}:
            raise ValueError("each case requires all four reference dimensions")
        if any(not value.strip() or len(value) > 1200 for value in self.features.values()):
            raise ValueError("case feature descriptions must contain 1 to 1200 characters")
        if self.status == "curated" and self.analysis_basis == "unreviewed":
            raise ValueError("curated cases require an explicit review basis")
        return self
