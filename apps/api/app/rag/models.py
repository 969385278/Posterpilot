from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.schemas.brief import NonEmptyText

KnowledgeType = Literal["theory", "rule", "diagnosis", "case"]
ReviewStatus = Literal["candidate", "approved", "rejected"]
SourceType = Literal["pdf", "web", "internal"]
ExtractionMode = Literal["pdf_text", "selected_ocr", "external_reference", "manual"]
SourceStatus = Literal["pending_review", "selected", "processed"]
RetrievalIntent = Literal["generation", "optimization", "evaluation"]


class KnowledgeCard(BaseModel):
    id: NonEmptyText
    knowledge_type: KnowledgeType
    category: NonEmptyText
    title: NonEmptyText
    content: NonEmptyText
    signals: list[NonEmptyText] = Field(default_factory=list, max_length=20)
    actions: list[NonEmptyText] = Field(min_length=1, max_length=20)
    constraints: list[NonEmptyText] = Field(default_factory=list, max_length=20)
    retrieval_aliases: list[NonEmptyText] = Field(default_factory=list, max_length=30)
    intents: list[RetrievalIntent] = Field(default_factory=list, max_length=3)
    target_roles: list[NonEmptyText] = Field(default_factory=list, max_length=12)
    source_id: str = ""
    source_pages: list[int] = Field(default_factory=list)
    source_locator: str | None = None
    source_url: HttpUrl | None = None
    review_status: ReviewStatus = "candidate"
    confidence: float = Field(default=0.5, ge=0, le=1)
    tags: list[NonEmptyText] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_source_and_pages(self) -> "KnowledgeCard":
        if any(page < 1 for page in self.source_pages):
            raise ValueError("source pages must use positive one-based page numbers")
        if len(self.source_pages) != len(set(self.source_pages)):
            raise ValueError("source pages must be unique")
        if self.review_status == "approved":
            has_source = self.source_id.strip() and (self.source_pages or self.source_locator)
            if not has_source:
                raise ValueError("approved knowledge requires a traceable source")
        return self


class SourceChunk(BaseModel):
    id: NonEmptyText
    source_id: NonEmptyText
    source_path: NonEmptyText
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    chapter: str | None = None
    title: str | None = None
    content: NonEmptyText
    extraction_method: Literal["text", "ocr"]
    quality_status: Literal["pending_review", "approved", "rejected"] = "pending_review"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_page_range(self) -> "SourceChunk":
        if self.page_end < self.page_start:
            raise ValueError("chunk page_end must not be before page_start")
        return self


class SourceDocument(BaseModel):
    id: NonEmptyText
    title: NonEmptyText
    source_type: SourceType
    path: str | None = None
    url: HttpUrl | None = None
    extraction_mode: ExtractionMode
    total_pages: int | None = Field(default=None, ge=1)
    selected_pages: list[int] = Field(default_factory=list)
    themes: list[NonEmptyText] = Field(default_factory=list)
    selection_rationale: str = ""
    status: SourceStatus = "pending_review"

    @model_validator(mode="after")
    def validate_location_and_selection(self) -> "SourceDocument":
        if self.source_type == "pdf" and not (self.path and self.path.strip()):
            raise ValueError("PDF source requires a path")
        if self.source_type == "web" and self.url is None:
            raise ValueError("web source requires a URL")
        if any(page < 1 for page in self.selected_pages):
            raise ValueError("selected pages must be positive")
        if len(self.selected_pages) != len(set(self.selected_pages)):
            raise ValueError("selected pages must be unique")
        if (
            self.extraction_mode == "selected_ocr"
            and self.status in {"selected", "processed"}
            and not self.selected_pages
        ):
            raise ValueError("selected OCR source requires selected pages")
        return self


class SourceManifest(BaseModel):
    version: int = Field(ge=1)
    sources: list[SourceDocument] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_source_ids(self) -> "SourceManifest":
        source_ids = [source.id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source ids must be unique")
        return self


class RetrievalCase(BaseModel):
    id: NonEmptyText
    intent: RetrievalIntent
    query: NonEmptyText
    context: dict[str, Any] = Field(default_factory=dict)
    expected_card_ids: list[NonEmptyText] = Field(min_length=1)
    excluded_card_ids: list[NonEmptyText] = Field(default_factory=list)


class RetrievalRequest(BaseModel):
    intent: RetrievalIntent
    query: NonEmptyText
    target_roles: list[NonEmptyText] = Field(default_factory=list)
    top_k: int = Field(default=3, ge=1, le=20)
    min_similarity: float = Field(default=0.3, ge=0, le=1)
    include_candidates: bool = False


class VectorHit(BaseModel):
    id: NonEmptyText
    similarity: float = Field(ge=0, le=1)


class RetrievalMatch(BaseModel):
    card: KnowledgeCard
    similarity: float = Field(ge=0, le=1)
    vector_similarity: float = Field(ge=0, le=1)
    lexical_similarity: float = Field(ge=0, le=1)


class RetrievalResult(BaseModel):
    query: NonEmptyText
    matches: list[RetrievalMatch] = Field(default_factory=list)
    candidate_ids: list[NonEmptyText] = Field(default_factory=list)
    fallback_reason: str | None = None
    error: str | None = None


class KnowledgeCitation(BaseModel):
    card_id: NonEmptyText
    title: NonEmptyText
    source_id: NonEmptyText
    source_pages: list[int] = Field(default_factory=list)
    source_locator: str | None = None
    source_url: HttpUrl | None = None
    similarity: float = Field(ge=0, le=1)
