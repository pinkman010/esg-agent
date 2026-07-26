from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ChunkEmbedding(BaseModel):
    chunk_id: str
    provider: str
    model: str
    embedding_dim: int = 1024
    embedding: list[float] | None = None
    input_hash: str = Field(min_length=64, max_length=64)
    status: Literal["succeeded", "failed"]
    error_code: str | None = None
    error_message: str | None = None
    usage: dict = Field(default_factory=dict)
    latency_ms: int | None = None
    retry_count: int = 0

    @model_validator(mode="after")
    def validate_status_vector(self) -> "ChunkEmbedding":
        if self.status == "succeeded":
            if self.embedding is None or len(self.embedding) != self.embedding_dim:
                raise ValueError("succeeded embedding must match embedding_dim")
        elif self.embedding is not None:
            raise ValueError("failed embedding must not contain a vector")
        return self


class ChunkEmbeddingSearchResult(BaseModel):
    chunk_id: str
    report_id: str
    text: str
    source_page: int
    source_file_hash: str
    score: float
