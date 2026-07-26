# SiliconFlow BGE-M3 离线影子 RAG 实施计划

> **执行要求：** 按 Task 顺序逐项实施，优先使用 `subagent-driven-development` 或 `executing-plans`；每个检查项完成后再勾选。

**Goal:** 接入 SiliconFlow `BAAI/bge-m3`，把指定报告的 `document_chunks` 向量化，完成离线 top-k 召回、批量指标评估、影子 RAG context pack 和可选离线生成评估，不改变现有规则 assessment、正式 AI suggestion、人工 snapshot 或正式输出门禁。

**Architecture:** 新增独立 embedding 配置、SiliconFlow embedding client、`document_chunk_embeddings` 向量表、Repository 读写方法和离线工具。第一阶段只处理显式指定报告的 `document_chunks`，使用精确余弦排序生成影子召回结果，并以人工基线页码计算 `hit@k`、`recall@k` 和 MRR；随后构造独立 shadow evidence context pack，可在再次取得真实模型调用授权后使用现有 DeepSeek client 生成离线建议。全部结果只写入 `tmp/embedding/`，不写入 `evidence_items` 或 `ai_assessment_suggestions`，不接入 `retrieve_evidence()`、`SingleReportWorkflow` 或正式 API。

**Tech Stack:** Python 3.11、FastAPI 配置体系、Pydantic v2、SQLAlchemy 2.0、Alembic、PostgreSQL pgvector、SiliconFlow `/v1/embeddings`、pytest、uv。

---

## 1. 边界结论

- 本计划只做结构化数据库向量化、影子检索评估、shadow RAG context pack 和可选离线生成评估。
- 默认 `EMBEDDING_ENABLED=false`，没有显式开启时不能调用 SiliconFlow。
- `EMBEDDING_API_KEY` 只允许存在本机 `backend/.env` 或当前 shell 环境，禁止提交。
- `BAAI/bge-m3` 不传 `dimensions` 参数；按实际返回向量长度保存，预期为 `1024`。
- 第一阶段 `--report-id` 必填，禁止默认扫描长期库全部报告或跨报告检索。
- `EMBEDDING_ENABLED=false` 时在读取待处理 chunk 和写数据库前退出，不写 failed 记录或零向量。
- provider 调用失败可以记录 failed 状态，但 failed 记录的 `embedding` 必须为空，禁止用零向量表示失败。
- 第一阶段使用精确余弦排序，不创建 IVFFlat/HNSW 近似索引，避免近似召回干扰离线质量评估。
- 向量召回不直接改变 `verdict`、`review_status`、`risk_level`、`evidence_items` 或 `ai_assessment_suggestions`。
- 影子召回、批量指标、RAG context pack 和离线生成结果只进入 `tmp/embedding/` 诊断产物。
- 真实 SiliconFlow embedding 和 DeepSeek 生成分别需要用户在执行当时显式确认；实现、单测和默认 dry run 只使用 mock。

## 2. 影响文件

- Modify: `backend/pyproject.toml`
  增加 `pgvector`，用于 SQLAlchemy 映射 PostgreSQL `vector(1024)`。
- Modify: `backend/uv.lock`
  由 `uv sync` 同步 `pgvector` 依赖锁。
- Modify: `backend/.env.example`
  增加 embedding 配置模板，不写真实 key。
- Modify: `docs/DEVELOPMENT.md`
  增加 SiliconFlow BGE-M3 离线影子 RAG 运行说明。
- Modify: `docs/DESIGN.md`
  记录影子 RAG 与冻结主流程的架构边界。
- Modify: `docs/product/data-model-impact.md`
  登记 `0012_chunk_embeddings`、nullable failed vector 和多模型复合主键。
- Modify: `backend/src/config/settings.py`
  增加 embedding 配置、HTTPS 校验和安全摘要。
- Modify: `backend/src/db/models.py`
  增加 `DocumentChunkEmbeddingRecord`。
- Create: `backend/alembic/versions/0012_chunk_embeddings.py`
  启用 pgvector extension，创建 `document_chunk_embeddings`。
- Modify: `backend/src/db/repositories.py`
  增加 chunk 查询、embedding upsert、待处理列表、向量检索方法。
- Create: `backend/src/domain/embedding_models.py`
  定义 embedding domain DTO。
- Create: `backend/src/tools/embedding_client.py`
  封装 SiliconFlow `/v1/embeddings` 调用、重试和错误分类。
- Create: `backend/src/tools/embed_document_chunks.py`
  离线批量向量化工具。
- Create: `backend/src/tools/shadow_vector_retrieval.py`
  离线 top-k 影子召回工具。
- Create: `backend/src/tools/evaluate_shadow_retrieval.py`
  按 requirement 与人工基线页码批量计算规则/向量召回指标。
- Create: `backend/src/tools/build_shadow_rag_contexts.py`
  把 requirement 与 top-k chunk 构造成只读 shadow evidence context pack。
- Create: `backend/src/tools/evaluate_shadow_rag.py`
  可选调用现有 DeepSeek client 生成离线影子建议，输出诊断 JSONL/CSV。
- Create: `backend/tests/tools/test_embedding_client.py`
  单测 embedding client 请求、响应解析、失败重试和禁用保护。
- Create: `backend/tests/tools/test_shadow_retrieval.py`
  覆盖输入规范化、输出路径边界、批量指标和 report 隔离。
- Create: `backend/tests/tools/test_shadow_rag.py`
  覆盖 context pack、默认不调用生成模型、mock 生成和输出字段。
- Modify: `backend/tests/test_settings.py`
  覆盖 embedding 配置默认值和 HTTPS 校验。
- Modify: `backend/tests/db/test_repositories.py`
  覆盖 embedding upsert、待处理查询和向量检索排序。
- Modify: `backend/tests/db/test_migrations.py`
  覆盖 `0012_chunk_embeddings` revision id 长度；现有测试会自动扫描。
- Modify: `backend/tests/database.py`
  测试库重建时确保 pgvector extension 已启用，避免 `Base.metadata.create_all()` 找不到 `vector` 类型。

## 3. 数据模型

新增表 `document_chunk_embeddings`：

```text
chunk_id          string(64) composite primary key, FK document_chunks.chunk_id on delete cascade
provider          string(64) not null
model             string(128) not null
embedding_dim     integer not null
embedding         vector(1024) nullable
input_hash        string(64) not null
status            string(32) not null
error_code        string(64) nullable
error_message     text nullable
usage             jsonb not null default {}
latency_ms        integer nullable
retry_count       integer not null default 0
created_at        timestamptz not null default now()
updated_at        timestamptz not null default now()
```

约束：

- `embedding_dim = 1024`
- `status in ('succeeded','failed')`
- `status = 'succeeded'` 时 `embedding is not null`
- `status = 'failed'` 时 `embedding is null`
- `latency_ms is null or latency_ms >= 0`
- `retry_count >= 0`

索引：

- `ix_chunk_embeddings_provider_model`
- `ix_chunk_embeddings_status`

第一阶段不创建向量近似索引。指定单份报告的 chunk 规模较小，精确余弦排序可以作为影子评估基准；达到需要优化的实际数据规模后，再以独立计划评估 HNSW 或 IVFFlat。

## 4. Task 1: 配置项和依赖

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/.env.example`
- Modify: `backend/src/config/settings.py`
- Modify: `backend/tests/test_settings.py`

- [x] **Step 1: 写配置测试**

在 `backend/tests/test_settings.py` 增加：

```python
import pytest
from pydantic import ValidationError

from src.config.settings import Settings


def test_embedding_settings_default_to_disabled_shadow_mode():
    settings = Settings()

    assert settings.embedding_enabled is False
    assert settings.embedding_provider == "siliconflow"
    assert settings.embedding_api_base == "https://api.siliconflow.cn/v1"
    assert settings.embedding_api_key == ""
    assert settings.embedding_model == "BAAI/bge-m3"
    assert settings.embedding_dim == 1024
    assert settings.embedding_batch_size == 16
    assert settings.embedding_max_input_tokens == 8192
    assert settings.embedding_max_input_chars == 6000
    assert settings.embedding_timeout_seconds == 60
    assert settings.embedding_max_retries == 2
    assert settings.embedding_retry_delay_seconds == 2


def test_embedding_api_base_must_be_https():
    with pytest.raises(ValidationError, match="EMBEDDING_API_BASE must be an HTTPS URL"):
        Settings(embedding_api_base="http://api.siliconflow.cn/v1")


def test_embedding_configuration_summary_hides_api_key():
    settings = Settings(embedding_api_key="secret-key")

    summary = settings.embedding_configuration_summary()

    assert summary["api_key_present"] is True
    assert "secret-key" not in str(summary)
```

- [x] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/test_settings.py -q
```

Expected: FAIL，错误包含 `Settings` 没有 `embedding_enabled` 或 `embedding_configuration_summary`。

- [x] **Step 3: 增加依赖**

在 `backend/pyproject.toml` 的 `dependencies` 中增加：

```toml
  "pgvector>=0.3.6",
```

- [x] **Step 4: 增加配置字段**

在 `backend/src/config/settings.py` 的 `Settings` 类中增加：

```python
    embedding_enabled: bool = False
    embedding_provider: Literal["siliconflow"] = "siliconflow"
    embedding_api_base: str = "https://api.siliconflow.cn/v1"
    embedding_api_key: str = ""
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = Field(default=1024, ge=1, le=8192)
    embedding_batch_size: int = Field(default=16, ge=1, le=128)
    embedding_max_input_tokens: int = Field(default=8192, ge=1, le=32768)
    embedding_max_input_chars: int = Field(default=6000, ge=256, le=24000)
    embedding_timeout_seconds: int = Field(default=60, ge=1, le=600)
    embedding_max_retries: int = Field(default=2, ge=0, le=5)
    embedding_retry_delay_seconds: float = Field(default=2, ge=0, le=60)
```

在 `Settings` 类中增加校验器：

```python
    @field_validator("embedding_api_base")
    @classmethod
    def validate_embedding_api_base(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("EMBEDDING_API_BASE must be an HTTPS URL")
        return normalized
```

在 `Settings` 类中增加摘要方法：

```python
    def embedding_configuration_summary(self) -> dict[str, object]:
        return {
            "enabled": self.embedding_enabled,
            "provider": self.embedding_provider,
            "api_base": self.embedding_api_base,
            "api_key_present": bool(self.embedding_api_key.strip()),
            "model": self.embedding_model,
            "dim": self.embedding_dim,
            "batch_size": self.embedding_batch_size,
            "max_input_tokens": self.embedding_max_input_tokens,
            "max_input_chars": self.embedding_max_input_chars,
            "timeout_seconds": self.embedding_timeout_seconds,
            "max_retries": self.embedding_max_retries,
        }
```

- [x] **Step 5: 更新 env example**

在 `backend/.env.example` 追加：

```env
EMBEDDING_ENABLED=false
EMBEDDING_PROVIDER=siliconflow
EMBEDDING_API_BASE=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024
EMBEDDING_BATCH_SIZE=16
EMBEDDING_MAX_INPUT_TOKENS=8192
EMBEDDING_MAX_INPUT_CHARS=6000
EMBEDDING_TIMEOUT_SECONDS=60
EMBEDDING_MAX_RETRIES=2
EMBEDDING_RETRY_DELAY_SECONDS=2
```

- [x] **Step 6: 运行配置测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/test_settings.py -q
```

Expected: PASS。

- [x] **Step 7: 同步依赖锁**

Run:

```powershell
cd backend
uv sync
```

Expected: `uv.lock` 更新且依赖解析成功。

## 5. Task 2: Alembic migration 和 ORM 模型

**Files:**
- Create: `backend/alembic/versions/0012_chunk_embeddings.py`
- Modify: `backend/src/db/models.py`
- Modify: `backend/tests/database.py`
- Test: `backend/tests/db/test_repositories.py`

- [x] **Step 1: 写数据库结构测试**

在 `backend/tests/db/test_repositories.py` 增加：

```python
def test_chunk_embedding_table_is_declared():
    engine, session = make_session()
    try:
        table_names = set(inspect(engine).get_table_names())
        assert "document_chunk_embeddings" in table_names

        columns = {
            column["name"]
            for column in inspect(engine).get_columns("document_chunk_embeddings")
        }
        assert {
            "chunk_id",
            "provider",
            "model",
            "embedding_dim",
            "embedding",
            "input_hash",
            "status",
            "error_code",
            "error_message",
            "usage",
            "latency_ms",
            "retry_count",
            "created_at",
            "updated_at",
        }.issubset(columns)
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()
```

- [x] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/db/test_repositories.py::test_chunk_embedding_table_is_declared -q
```

Expected: FAIL，表不存在。

- [x] **Step 3: 创建 ORM 模型**

在 `backend/src/db/models.py` 增加 import：

```python
from pgvector.sqlalchemy import Vector
```

在 `DocumentChunkRecord` 后增加：

```python
class DocumentChunkEmbeddingRecord(Base):
    __tablename__ = "document_chunk_embeddings"

    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("document_chunks.chunk_id", ondelete="CASCADE"),
        primary_key=True,
    )
    provider: Mapped[str] = mapped_column(String(64), primary_key=True)
    model: Mapped[str] = mapped_column(String(128), primary_key=True)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    usage: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
```

在文件底部增加索引：

```python
Index("ix_chunk_embeddings_provider_model", DocumentChunkEmbeddingRecord.provider, DocumentChunkEmbeddingRecord.model)
Index("ix_chunk_embeddings_status", DocumentChunkEmbeddingRecord.status)
```

- [x] **Step 4: 更新测试数据库 helper**

在 `backend/tests/database.py` 的 `reset_database()` 中增加 extension 初始化：

```python
def reset_database(engine) -> None:
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
```

- [x] **Step 5: 创建 Alembic migration**

创建 `backend/alembic/versions/0012_chunk_embeddings.py`：

```python
"""add document chunk embeddings

Revision ID: 0012_chunk_embeddings
Revises: 0011_ai_suggestions
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0012_chunk_embeddings"
down_revision: str | None = "0011_ai_suggestions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "document_chunk_embeddings",
        sa.Column(
            "chunk_id",
            sa.String(length=64),
            sa.ForeignKey("document_chunks.chunk_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("provider", sa.String(length=64), primary_key=True),
        sa.Column("model", sa.String(length=128), primary_key=True),
        sa.Column("embedding_dim", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("embedding_dim = 1024", name="ck_chunk_embeddings_dim_1024"),
        sa.CheckConstraint("status IN ('succeeded', 'failed')", name="ck_chunk_embeddings_status"),
        sa.CheckConstraint(
            "(status = 'succeeded' AND embedding IS NOT NULL) OR "
            "(status = 'failed' AND embedding IS NULL)",
            name="ck_chunk_embeddings_status_vector",
        ),
        sa.CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_chunk_embeddings_latency_ms"),
        sa.CheckConstraint("retry_count >= 0", name="ck_chunk_embeddings_retry_count"),
    )
    op.create_index(
        "ix_chunk_embeddings_provider_model",
        "document_chunk_embeddings",
        ["provider", "model"],
    )
    op.create_index(
        "ix_chunk_embeddings_status",
        "document_chunk_embeddings",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_chunk_embeddings_status", table_name="document_chunk_embeddings")
    op.drop_index("ix_chunk_embeddings_provider_model", table_name="document_chunk_embeddings")
    op.drop_table("document_chunk_embeddings")
```

- [x] **Step 6: 运行 migration 和结构测试**

Run:

```powershell
cd backend
$env:APP_ENV="test"
$env:DATABASE_URL="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_test"
uv run --no-sync python -c "from sqlalchemy.engine import make_url; from src.config.settings import get_settings; print(make_url(get_settings().database_url).database)"
uv run --no-sync alembic upgrade head
uv run --no-sync pytest tests/db/test_repositories.py::test_chunk_embedding_table_is_declared tests/db/test_migrations.py -q
```

Expected: 数据库名输出 `esg_agent_test`，migration 和测试 PASS。禁止在本步骤升级 `esg_agent` 或 `esg_agent_demo`；若 PostgreSQL extension、权限或类型初始化失败，立即停止，不降级为普通 JSON 向量。

## 6. Task 3: Domain DTO 和 Repository 方法

**Files:**
- Create: `backend/src/domain/embedding_models.py`
- Modify: `backend/src/db/repositories.py`
- Test: `backend/tests/db/test_repositories.py`

- [x] **Step 1: 写 repository 测试**

在 `backend/tests/db/test_repositories.py` 增加 import：

```python
from src.domain.embedding_models import ChunkEmbedding, ChunkEmbeddingSearchResult
```

增加测试：

```python
def test_repository_upserts_chunk_embedding_and_lists_pending_chunks():
    engine, session = make_session()
    try:
        repo = Repository(session)
        repo.create_report(Report(report_id="report-emb", original_filename="report.pdf", stored_path="x", file_hash="hash-emb"))
        repo.save_pages_and_chunks(
            pages=[],
            chunks=[
                DocumentChunk(
                    chunk_id="chunk-emb-1",
                    report_id="report-emb",
                    text="温室气体排放数据",
                    source_page=1,
                    source_method=EvidenceSourceMethod.PDFPLUMBER,
                    source_file_hash="hash-emb",
                )
            ],
        )

        pending_before = repo.list_chunks_missing_embeddings(
            provider="siliconflow",
            model="BAAI/bge-m3",
            limit=10,
        )
        assert [chunk.chunk_id for chunk in pending_before] == ["chunk-emb-1"]

        repo.upsert_chunk_embedding(
            ChunkEmbedding(
                chunk_id="chunk-emb-1",
                provider="siliconflow",
                model="BAAI/bge-m3",
                embedding_dim=1024,
                embedding=[0.1] * 1024,
                input_hash="a" * 64,
                status="succeeded",
                usage={"total_tokens": 12},
                latency_ms=30,
                retry_count=0,
            )
        )

        pending_after = repo.list_chunks_missing_embeddings(
            provider="siliconflow",
            model="BAAI/bge-m3",
            limit=10,
        )
        assert pending_after == []
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()
```

- [x] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/db/test_repositories.py::test_repository_upserts_chunk_embedding_and_lists_pending_chunks -q
```

Expected: FAIL，`ChunkEmbedding` 或 repository 方法不存在。

- [x] **Step 3: 创建 DTO**

创建 `backend/src/domain/embedding_models.py`：

```python
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
```

- [x] **Step 4: 修改 Repository imports**

把 `backend/src/db/repositories.py` 顶部 SQLAlchemy import 改为：

```python
from sqlalchemy import delete, func, or_, select, text
```

在 `from src.db.models import (...)` 中增加：

```python
    DocumentChunkEmbeddingRecord,
```

并增加：

```python
from src.domain.embedding_models import ChunkEmbedding, ChunkEmbeddingSearchResult
```

- [x] **Step 5: 增加 Repository 方法**

在 `Repository` 类中增加：

```python
    def list_chunks_missing_embeddings(
        self,
        *,
        provider: str,
        model: str,
        limit: int,
        report_id: str,
    ) -> list[DocumentChunk]:
        filters = [
            or_(
                DocumentChunkEmbeddingRecord.chunk_id.is_(None),
                DocumentChunkEmbeddingRecord.status != "succeeded",
            ),
        ]
        filters.append(DocumentChunkRecord.report_id == report_id)
        records = self.session.scalars(
            select(DocumentChunkRecord)
            .outerjoin(
                DocumentChunkEmbeddingRecord,
                (DocumentChunkEmbeddingRecord.chunk_id == DocumentChunkRecord.chunk_id)
                & (DocumentChunkEmbeddingRecord.provider == provider)
                & (DocumentChunkEmbeddingRecord.model == model),
            )
            .where(*filters)
            .order_by(DocumentChunkRecord.report_id, DocumentChunkRecord.source_page, DocumentChunkRecord.chunk_id)
            .limit(limit)
        ).all()
        return [self._chunk_from_record(record) for record in records]

    def upsert_chunk_embedding(self, embedding: ChunkEmbedding) -> ChunkEmbedding:
        record = self.session.get(
            DocumentChunkEmbeddingRecord,
            {
                "chunk_id": embedding.chunk_id,
                "provider": embedding.provider,
                "model": embedding.model,
            },
        )
        if record is None:
            record = DocumentChunkEmbeddingRecord(chunk_id=embedding.chunk_id)
            self.session.add(record)
        record.provider = embedding.provider
        record.model = embedding.model
        record.embedding_dim = embedding.embedding_dim
        record.embedding = embedding.embedding
        record.input_hash = embedding.input_hash
        record.status = embedding.status
        record.error_code = embedding.error_code
        record.error_message = embedding.error_message
        record.usage = embedding.usage
        record.latency_ms = embedding.latency_ms
        record.retry_count = embedding.retry_count
        self.session.commit()
        self.session.refresh(record)
        return self._chunk_embedding_from_record(record)
```

在 `_evidence_from_record` 前增加 helper：

```python
    def _chunk_from_record(self, record: DocumentChunkRecord) -> DocumentChunk:
        return DocumentChunk(
            chunk_id=record.chunk_id,
            report_id=record.report_id,
            text=record.text,
            source_page=record.source_page,
            source_method=EvidenceSourceMethod(record.source_method),
            source_file_hash=record.source_file_hash,
            bbox=record.bbox,
            quality_flags=[PageQualityFlag(flag) for flag in record.quality_flags],
            embedding_status=record.embedding_status,
            embedding_model=record.embedding_model,
            embedding_dim=record.embedding_dim,
            metadata=record.chunk_metadata,
        )

    def _chunk_embedding_from_record(self, record: DocumentChunkEmbeddingRecord) -> ChunkEmbedding:
        return ChunkEmbedding(
            chunk_id=record.chunk_id,
            provider=record.provider,
            model=record.model,
            embedding_dim=record.embedding_dim,
            embedding=list(record.embedding) if record.embedding is not None else None,
            input_hash=record.input_hash,
            status=record.status,
            error_code=record.error_code,
            error_message=record.error_message,
            usage=record.usage,
            latency_ms=record.latency_ms,
            retry_count=record.retry_count,
        )
```

- [x] **Step 6: 运行 repository 测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/db/test_repositories.py::test_repository_upserts_chunk_embedding_and_lists_pending_chunks -q
```

Expected: PASS。

## 7. Task 4: SiliconFlow embedding client

**Files:**
- Create: `backend/src/tools/embedding_client.py`
- Create: `backend/tests/tools/test_embedding_client.py`

- [x] **Step 1: 写 client 测试**

创建 `backend/tests/tools/test_embedding_client.py`：

```python
from types import SimpleNamespace

import pytest

from src.tools.embedding_client import (
    EmbeddingCallBlocked,
    EmbeddingClient,
    EmbeddingClientError,
)


class FakeAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str = "provider error"):
        super().__init__(message)
        self.status_code = status_code


def _response(vectors=None, model="BAAI/bge-m3"):
    return SimpleNamespace(
        model=model,
        data=[
            SimpleNamespace(embedding=vector, index=index)
            for index, vector in enumerate(vectors or [[0.1] * 1024])
        ],
        usage=SimpleNamespace(prompt_tokens=8, total_tokens=8),
    )


def test_embedding_client_blocks_when_disabled():
    calls = []
    client = EmbeddingClient(
        model="BAAI/bge-m3",
        api_key="key",
        base_url="https://api.siliconflow.cn/v1",
        embedding_factory=lambda **kwargs: calls.append(kwargs),
    )

    with pytest.raises(EmbeddingCallBlocked):
        client.embed_texts(["text"], embedding_enabled=False)

    assert calls == []


def test_embedding_client_sends_bge_m3_request_without_dimensions():
    calls = []

    def fake_embeddings_create(**kwargs):
        calls.append(kwargs)
        return _response([[0.2] * 1024])

    client = EmbeddingClient(
        model="BAAI/bge-m3",
        api_key="key",
        base_url="https://api.siliconflow.cn/v1",
        embedding_factory=fake_embeddings_create,
        sleep_fn=lambda _seconds: None,
    )

    result = client.embed_texts(["温室气体排放"], embedding_enabled=True)

    assert result.model == "BAAI/bge-m3"
    assert result.embeddings == [[0.2] * 1024]
    assert result.usage == {"prompt_tokens": 8, "total_tokens": 8}
    assert len(calls) == 1
    assert calls[0]["model"] == "BAAI/bge-m3"
    assert calls[0]["input"] == ["温室气体排放"]
    assert calls[0]["encoding_format"] == "float"
    assert "dimensions" not in calls[0]


@pytest.mark.parametrize("status_code", [429, 503, 504])
def test_embedding_client_retries_transient_provider_errors(status_code):
    calls = []

    def fail(**kwargs):
        calls.append(kwargs)
        raise FakeAPIError(status_code)

    client = EmbeddingClient(
        model="BAAI/bge-m3",
        api_key="key",
        base_url="https://api.siliconflow.cn/v1",
        embedding_factory=fail,
        max_retries=2,
        retry_delay_seconds=0,
        sleep_fn=lambda _seconds: None,
    )

    with pytest.raises(EmbeddingClientError) as exc_info:
        client.embed_texts(["text"], embedding_enabled=True)

    assert exc_info.value.retry_count == 2
    assert len(calls) == 3


def test_embedding_client_rejects_unexpected_dimension():
    client = EmbeddingClient(
        model="BAAI/bge-m3",
        api_key="key",
        base_url="https://api.siliconflow.cn/v1",
        expected_dim=1024,
        embedding_factory=lambda **_kwargs: _response([[0.1] * 3]),
        sleep_fn=lambda _seconds: None,
    )

    with pytest.raises(EmbeddingClientError) as exc_info:
        client.embed_texts(["text"], embedding_enabled=True)

    assert exc_info.value.error_code == "embedding_dimension_mismatch"
```

- [x] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_embedding_client.py -q
```

Expected: FAIL，模块不存在。

- [x] **Step 3: 实现 client**

创建 `backend/src/tools/embedding_client.py`：

```python
import time
from collections.abc import Callable
from typing import Any

from openai import APIConnectionError, APITimeoutError, OpenAI
from pydantic import BaseModel


class EmbeddingCallBlocked(RuntimeError):
    pass


class EmbeddingClientError(RuntimeError):
    def __init__(self, *, error_code: str, retry_count: int):
        super().__init__(f"Embedding request failed ({error_code})")
        self.error_code = error_code
        self.retry_count = retry_count


class EmbeddingResult(BaseModel):
    embeddings: list[list[float]]
    model: str
    usage: dict[str, Any]
    latency_ms: int
    retry_count: int


EmbeddingFactory = Callable[..., Any]


class EmbeddingClient:
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        embedding_factory: EmbeddingFactory | None = None,
        *,
        expected_dim: int = 1024,
        timeout_seconds: int = 60,
        max_retries: int = 2,
        retry_delay_seconds: float = 2,
        sleep_fn: Callable[[float], None] = time.sleep,
        clock_fn: Callable[[], float] = time.monotonic,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.embedding_factory = embedding_factory
        self.expected_dim = expected_dim
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.sleep_fn = sleep_fn
        self.clock_fn = clock_fn

    def embed_texts(self, texts: list[str], *, embedding_enabled: bool) -> EmbeddingResult:
        if not embedding_enabled:
            raise EmbeddingCallBlocked("external embedding call requires EMBEDDING_ENABLED=true")
        if not texts or any(not text.strip() for text in texts):
            raise EmbeddingClientError(error_code="embedding_empty_input", retry_count=0)

        embedding_create = self.embedding_factory
        if embedding_create is None:
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout_seconds,
            )
            embedding_create = client.embeddings.create

        request = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float",
        }
        started_at = self.clock_fn()
        retry_count = 0
        while True:
            try:
                response = embedding_create(**request)
                return self._parse_response(response, retry_count, started_at)
            except Exception as exc:
                error_code, retryable = self._classify_error(exc)
                if not retryable or retry_count >= self.max_retries:
                    raise EmbeddingClientError(
                        error_code=error_code,
                        retry_count=retry_count,
                    ) from None
                retry_count += 1
                if self.retry_delay_seconds:
                    self.sleep_fn(self.retry_delay_seconds)

    def _parse_response(self, response: Any, retry_count: int, started_at: float) -> EmbeddingResult:
        data = sorted(getattr(response, "data", None) or [], key=lambda item: getattr(item, "index", 0))
        embeddings = [list(getattr(item, "embedding", []) or []) for item in data]
        if not embeddings:
            raise EmbeddingClientError(error_code="embedding_empty_response", retry_count=retry_count)
        if any(len(vector) != self.expected_dim for vector in embeddings):
            raise EmbeddingClientError(error_code="embedding_dimension_mismatch", retry_count=retry_count)
        return EmbeddingResult(
            embeddings=embeddings,
            model=str(getattr(response, "model", None) or self.model),
            usage=self._usage_dict(getattr(response, "usage", None)),
            latency_ms=max(0, round((self.clock_fn() - started_at) * 1000)),
            retry_count=retry_count,
        )

    @staticmethod
    def _usage_dict(usage: Any) -> dict[str, Any]:
        if usage is None:
            return {}
        if isinstance(usage, dict):
            return usage
        if hasattr(usage, "model_dump"):
            return usage.model_dump(exclude_none=True)
        return {
            name: getattr(usage, name)
            for name in ("prompt_tokens", "completion_tokens", "total_tokens")
            if getattr(usage, name, None) is not None
        }

    @staticmethod
    def _classify_error(exc: Exception) -> tuple[str, bool]:
        if isinstance(exc, EmbeddingClientError):
            return exc.error_code, False
        if isinstance(exc, (APIConnectionError, APITimeoutError, TimeoutError, ConnectionError)):
            return "embedding_connection_error", True
        status_code = getattr(exc, "status_code", None)
        if status_code == 429:
            return "embedding_rate_limited", True
        if status_code in {500, 503, 504}:
            return "embedding_server_error", True
        if status_code in {400, 401, 402, 403, 404, 422}:
            return "embedding_request_rejected", False
        return "embedding_call_failed", False
```

- [x] **Step 4: 运行 client 测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_embedding_client.py -q
```

Expected: PASS。

## 8. Task 5: 批量向量化离线工具

**Files:**
- Create: `backend/src/tools/embed_document_chunks.py`
- Test: `backend/tests/tools/test_embedding_client.py`

- [x] **Step 1: 写输入哈希测试**

在 `backend/tests/tools/test_embedding_client.py` 增加：

```python
from src.tools.embed_document_chunks import (
    chunk_embedding_input_hash,
    normalize_embedding_input,
)


def test_chunk_embedding_input_hash_changes_with_text_and_model():
    first = chunk_embedding_input_hash("文本", provider="siliconflow", model="BAAI/bge-m3")
    same = chunk_embedding_input_hash("文本", provider="siliconflow", model="BAAI/bge-m3")
    different_text = chunk_embedding_input_hash("另一个文本", provider="siliconflow", model="BAAI/bge-m3")
    different_model = chunk_embedding_input_hash("文本", provider="siliconflow", model="BAAI/bge-large-zh-v1.5")

    assert first == same
    assert len(first) == 64
    assert first != different_text
    assert first != different_model


def test_normalize_embedding_input_is_deterministic_and_bounded():
    normalized = normalize_embedding_input("  温室气体\\n\\n排放  ", max_chars=6)

    assert normalized == "温室气体 排"
    assert len(normalized) == 6
```

- [x] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_embedding_client.py::test_chunk_embedding_input_hash_changes_with_text_and_model -q
```

Expected: FAIL，模块不存在。

- [x] **Step 3: 实现离线工具**

创建 `backend/src/tools/embed_document_chunks.py`：

```python
import argparse
import hashlib
from collections.abc import Sequence

from src.config.settings import get_settings
from src.db.repositories import Repository
from src.db.session import SessionLocal
from src.domain.embedding_models import ChunkEmbedding
from src.tools.embedding_client import EmbeddingCallBlocked, EmbeddingClient


def normalize_embedding_input(text: str, *, max_chars: int) -> str:
    normalized = " ".join(text.split()).strip()
    if not normalized:
        raise ValueError("embedding input must not be empty")
    return normalized[:max_chars]


def chunk_embedding_input_hash(text: str, *, provider: str, model: str) -> str:
    payload = f"{provider}\n{model}\n{text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def embed_pending_chunks(*, report_id: str, limit: int = 128) -> dict[str, int]:
    settings = get_settings()
    if not settings.embedding_enabled:
        raise EmbeddingCallBlocked(
            "external embedding call requires EMBEDDING_ENABLED=true"
        )
    client = EmbeddingClient(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_api_base,
        expected_dim=settings.embedding_dim,
        timeout_seconds=settings.embedding_timeout_seconds,
        max_retries=settings.embedding_max_retries,
        retry_delay_seconds=settings.embedding_retry_delay_seconds,
    )
    succeeded = 0
    failed = 0
    with SessionLocal() as session:
        repo = Repository(session)
        chunks = repo.list_chunks_missing_embeddings(
            provider=settings.embedding_provider,
            model=settings.embedding_model,
            report_id=report_id,
            limit=limit,
        )
        for start in range(0, len(chunks), settings.embedding_batch_size):
            batch = chunks[start : start + settings.embedding_batch_size]
            texts = [
                normalize_embedding_input(
                    chunk.text,
                    max_chars=settings.embedding_max_input_chars,
                )
                for chunk in batch
            ]
            try:
                result = client.embed_texts(texts, embedding_enabled=settings.embedding_enabled)
                for chunk, normalized_text, vector in zip(
                    batch,
                    texts,
                    result.embeddings,
                    strict=True,
                ):
                    repo.upsert_chunk_embedding(
                        ChunkEmbedding(
                            chunk_id=chunk.chunk_id,
                            provider=settings.embedding_provider,
                            model=settings.embedding_model,
                            embedding_dim=len(vector),
                            embedding=vector,
                            input_hash=chunk_embedding_input_hash(
                                normalized_text,
                                provider=settings.embedding_provider,
                                model=settings.embedding_model,
                            ),
                            status="succeeded",
                            usage=result.usage,
                            latency_ms=result.latency_ms,
                            retry_count=result.retry_count,
                        )
                    )
                    succeeded += 1
            except Exception as exc:
                for chunk in batch:
                    repo.upsert_chunk_embedding(
                        ChunkEmbedding(
                            chunk_id=chunk.chunk_id,
                            provider=settings.embedding_provider,
                            model=settings.embedding_model,
                            embedding_dim=settings.embedding_dim,
                            embedding=None,
                            input_hash=chunk_embedding_input_hash(
                                normalize_embedding_input(
                                    chunk.text,
                                    max_chars=settings.embedding_max_input_chars,
                                ),
                                provider=settings.embedding_provider,
                                model=settings.embedding_model,
                            ),
                            status="failed",
                            error_code=getattr(exc, "error_code", "embedding_batch_failed"),
                            error_message=str(exc),
                            usage={},
                            latency_ms=None,
                            retry_count=getattr(exc, "retry_count", 0),
                        )
                    )
                    failed += 1
    return {"succeeded": succeeded, "failed": failed}


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--limit", type=int, default=128)
    args = parser.parse_args(argv)
    result = embed_pending_chunks(report_id=args.report_id, limit=args.limit)
    print(result)


if __name__ == "__main__":
    main()
```

- [x] **Step 4: 运行工具相关测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_embedding_client.py -q
```

Expected: PASS。

- [x] **Step 5: 手工 dry run 验证禁用保护**

Run:

```powershell
cd backend
$env:EMBEDDING_ENABLED="false"
uv run --no-sync python -m src.tools.embed_document_chunks --report-id report-test --limit 1
```

Expected: 命令在查询 chunk 和写数据库前以 `EmbeddingCallBlocked` 退出；不得发出真实外部请求，不得新增 succeeded/failed embedding 记录。该验证使用 mock 或 `esg_agent_test`，不在长期验收库直接跑。

## 9. Task 6: 影子向量召回工具

**Files:**
- Modify: `backend/src/db/repositories.py`
- Create: `backend/src/tools/shadow_vector_retrieval.py`
- Test: `backend/tests/db/test_repositories.py`

- [x] **Step 1: 写检索 repository 测试**

在 `backend/tests/db/test_repositories.py` 增加：

```python
def test_repository_searches_chunk_embeddings_by_cosine_distance():
    engine, session = make_session()
    try:
        repo = Repository(session)
        repo.create_report(Report(report_id="report-search", original_filename="report.pdf", stored_path="x", file_hash="hash-search"))
        repo.save_pages_and_chunks(
            pages=[],
            chunks=[
                DocumentChunk(
                    chunk_id="chunk-close",
                    report_id="report-search",
                    text="温室气体排放",
                    source_page=1,
                    source_method=EvidenceSourceMethod.PDFPLUMBER,
                    source_file_hash="hash-search",
                ),
                DocumentChunk(
                    chunk_id="chunk-far",
                    report_id="report-search",
                    text="员工培训",
                    source_page=2,
                    source_method=EvidenceSourceMethod.PDFPLUMBER,
                    source_file_hash="hash-search",
                ),
            ],
        )
        repo.upsert_chunk_embedding(
            ChunkEmbedding(
                chunk_id="chunk-close",
                provider="siliconflow",
                model="BAAI/bge-m3",
                embedding=[1.0] + [0.0] * 1023,
                input_hash="a" * 64,
                status="succeeded",
            )
        )
        repo.upsert_chunk_embedding(
            ChunkEmbedding(
                chunk_id="chunk-far",
                provider="siliconflow",
                model="BAAI/bge-m3",
                embedding=[0.0, 1.0] + [0.0] * 1022,
                input_hash="b" * 64,
                status="succeeded",
            )
        )

        results = repo.search_chunk_embeddings(
            provider="siliconflow",
            model="BAAI/bge-m3",
            query_embedding=[1.0] + [0.0] * 1023,
            report_id="report-search",
            limit=2,
        )

        assert [item.chunk_id for item in results] == ["chunk-close", "chunk-far"]
        assert results[0].score > results[1].score
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()
```

- [x] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/db/test_repositories.py::test_repository_searches_chunk_embeddings_by_cosine_distance -q
```

Expected: FAIL，`search_chunk_embeddings` 不存在。

- [x] **Step 3: 增加向量检索方法**

在 `backend/src/db/repositories.py` 增加 import：

```python
from pgvector.sqlalchemy import Vector
```

在 `Repository` 类中增加：

```python
    def search_chunk_embeddings(
        self,
        *,
        provider: str,
        model: str,
        query_embedding: list[float],
        report_id: str,
        limit: int,
    ) -> list[ChunkEmbeddingSearchResult]:
        filters = [
            DocumentChunkEmbeddingRecord.provider == provider,
            DocumentChunkEmbeddingRecord.model == model,
            DocumentChunkEmbeddingRecord.status == "succeeded",
            DocumentChunkRecord.report_id == report_id,
        ]
        distance = DocumentChunkEmbeddingRecord.embedding.cosine_distance(query_embedding)
        rows = self.session.execute(
            select(DocumentChunkRecord, (1 - distance).label("score"))
            .join(DocumentChunkEmbeddingRecord, DocumentChunkEmbeddingRecord.chunk_id == DocumentChunkRecord.chunk_id)
            .where(*filters)
            .order_by(distance.asc())
            .limit(limit)
        ).all()
        return [
            ChunkEmbeddingSearchResult(
                chunk_id=chunk.chunk_id,
                report_id=chunk.report_id,
                text=chunk.text,
                source_page=chunk.source_page,
                source_file_hash=chunk.source_file_hash,
                score=float(score),
            )
            for chunk, score in rows
        ]
```

- [x] **Step 4: 创建影子检索工具**

创建 `backend/src/tools/shadow_vector_retrieval.py`：

```python
import argparse
import csv
from collections.abc import Sequence
from pathlib import Path

from src.config.settings import PROJECT_ROOT, get_settings
from src.db.repositories import Repository
from src.db.session import SessionLocal
from src.tools.embedding_client import EmbeddingClient


def resolve_shadow_output(output: str) -> Path:
    output_root = (PROJECT_ROOT / "tmp" / "embedding").resolve()
    resolved = (PROJECT_ROOT / output).resolve()
    if not resolved.is_relative_to(output_root):
        raise ValueError("shadow output must stay under tmp/embedding")
    return resolved


def shadow_search(query: str, *, report_id: str, top_k: int) -> list[dict]:
    settings = get_settings()
    client = EmbeddingClient(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_api_base,
        expected_dim=settings.embedding_dim,
        timeout_seconds=settings.embedding_timeout_seconds,
        max_retries=settings.embedding_max_retries,
        retry_delay_seconds=settings.embedding_retry_delay_seconds,
    )
    embedding_result = client.embed_texts([query], embedding_enabled=settings.embedding_enabled)
    query_embedding = embedding_result.embeddings[0]
    with SessionLocal() as session:
        repo = Repository(session)
        results = repo.search_chunk_embeddings(
            provider=settings.embedding_provider,
            model=settings.embedding_model,
            query_embedding=query_embedding,
            report_id=report_id,
            limit=top_k,
        )
    return [item.model_dump() for item in results]


def write_csv(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["chunk_id", "report_id", "source_page", "score", "source_file_hash", "text"]
    with output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--output", default="tmp/embedding/shadow_vector_retrieval.csv")
    args = parser.parse_args(argv)
    rows = shadow_search(args.query, report_id=args.report_id, top_k=args.top_k)
    output = resolve_shadow_output(args.output)
    write_csv(rows, output)
    print({"rows": len(rows), "output": str(output)})


if __name__ == "__main__":
    main()
```

- [x] **Step 5: 运行检索测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/db/test_repositories.py::test_repository_searches_chunk_embeddings_by_cosine_distance -q
```

Expected: PASS。

## 10. Task 7: 批量影子召回评估

**Files:**
- Create: `backend/src/tools/evaluate_shadow_retrieval.py`
- Create: `backend/tests/tools/test_shadow_retrieval.py`

- [x] **Step 1: 写纯指标函数测试**

测试至少覆盖：

- `hit@1`、`hit@3`、`recall@k` 和 MRR 的计算；
- 多个正确页时，召回率按命中的正确页数计算；
- 没有人工正确页的 requirement 进入明细，但不进入召回指标分母；
- 向量召回页与现有规则候选页的 `vector_only`、`rule_only`、`both`、`neither` 分类；
- 输出路径越出 `tmp/embedding/` 时拒绝写入。

示例：

```python
from src.tools.evaluate_shadow_retrieval import compute_retrieval_metrics


def test_compute_retrieval_metrics_uses_only_cases_with_gold_pages():
    cases = [
        {
            "requirement_id": "GRI 305-1-a",
            "gold_pages": [40, 41],
            "vector_pages": [41, 8, 40],
            "rule_pages": [40],
        },
        {
            "requirement_id": "GRI 305-2-a",
            "gold_pages": [],
            "vector_pages": [42],
            "rule_pages": [],
        },
    ]

    metrics = compute_retrieval_metrics(cases, k_values=(1, 3))

    assert metrics["case_count"] == 2
    assert metrics["evaluated_case_count"] == 1
    assert metrics["hit_at_1"] == 1.0
    assert metrics["recall_at_1"] == 0.5
    assert metrics["recall_at_3"] == 1.0
    assert metrics["mrr"] == 1.0
```

- [x] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_shadow_retrieval.py -q
```

Expected: FAIL，批量评估工具尚不存在。

- [x] **Step 3: 实现批量评估工具**

创建 `backend/src/tools/evaluate_shadow_retrieval.py`，职责如下：

1. `--report-id` 必填，只评估一份报告。
2. 从 `gri_requirement_checklist_v3.json` 读取 499 个独立 assessment 的 `effective_requirement_text`，不把 78 个上下文项当作独立查询。
3. 从批准的人工复核工作簿和 regeneration CSV 按 `requirement_id` 聚合：
   - 工作簿 `correct_pdf_pages` 作为人工正确页；
   - CSV 的 candidate/source page 字段作为现有规则召回对照；
   - 空页码不得构造成 `0` 或虚假正确页。
4. 每个 requirement 使用与批量向量化相同的输入规范化函数生成 query embedding。
5. 只在指定报告内执行精确余弦 top-k。
6. 输出逐项明细 CSV 和汇总 JSON，不写正式数据库表。

CLI 参数：

```text
--report-id              required
--requirements           default data/manifests/gri_requirement_checklist_v3.json
--baseline               default data/review_inputs/envision_2024/baselines/current_577_review_regenerated.csv
--manual-review-workbook default data/review_inputs/envision_2024/manual/envision_2024_577_manual_review_second_review_Pro_20260719.xlsx
--top-k                  default 10
--output-prefix          default tmp/embedding/envision_shadow_retrieval
```

汇总至少包含：

```text
case_count
evaluated_case_count
no_gold_page_case_count
hit_at_1
hit_at_3
hit_at_5
hit_at_10
recall_at_1
recall_at_3
recall_at_5
recall_at_10
mrr
vector_only_hit_count
rule_only_hit_count
both_hit_count
neither_hit_count
```

明细至少包含：

```text
requirement_id
query_text
gold_pages
rule_pages
vector_pages
vector_source_pages
vector_chunk_ids
vector_scores
vector_texts
first_hit_rank
hit_at_1
hit_at_3
hit_at_5
hit_at_10
comparison_bucket
```

`output-prefix` 解析后的 CSV/JSON 均必须位于 `tmp/embedding/`。该工具不得更新 `evidence_items`、assessment、risk、review snapshot、AI suggestion 或 export。

- [x] **Step 4: 运行工具测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_shadow_retrieval.py -q
```

Expected: PASS，测试全部使用 fake embedding client 和测试库，不发真实网络请求。

## 11. Task 8: 影子 RAG context pack 与可选生成评估

**Files:**
- Create: `backend/src/tools/build_shadow_rag_contexts.py`
- Create: `backend/src/tools/evaluate_shadow_rag.py`
- Create: `backend/tests/tools/test_shadow_rag.py`

- [x] **Step 1: 写 context pack 和禁用保护测试**

测试至少覆盖：

- 每个 requirement 只包含指定报告的 top-k chunk；
- 每条 chunk 都带 `shadow_evidence_id`、`source_page`、`score` 和有界文本；
- `shadow_evidence_id` 使用 `shadow-chunk:<chunk_id>`，不会与正式 `evidence_id` 混用；
- 未传 `--confirm-llm` 时只生成 context pack，不调用 LLM；
- fake LLM 返回的引用超出 context pack 时标记为 `invalid_shadow_citation`；
- mock 生成结果只写 `tmp/embedding/`，正式数据库写方法调用次数为 0。

示例：

```python
def test_build_context_pack_keeps_shadow_evidence_separate():
    context = build_shadow_context(
        report_id="report-envision",
        requirement_id="GRI 305-1-a",
        requirement_text="披露范围一温室气体排放。",
        hits=[
            {
                "chunk_id": "chunk-1",
                "source_page": 40,
                "score": 0.91,
                "text": "范围一温室气体排放为……",
            }
        ],
    )

    assert context["evidence"][0]["shadow_evidence_id"] == "shadow-chunk:chunk-1"
    assert context["evidence"][0]["source_page"] == 40
    assert "evidence_id" not in context["evidence"][0]
```

- [x] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_shadow_rag.py -q
```

Expected: FAIL，影子 RAG 工具尚不存在。

- [x] **Step 3: 实现只读 context pack**

创建 `backend/src/tools/build_shadow_rag_contexts.py`：

- 输入 requirement 清单与 Task 7 的召回明细；
- 每个 requirement 保留 top-k chunk，单个 chunk 文本上限 1200 字符；
- 输出 JSONL 到 `tmp/embedding/`；
- 记录 `report_id`、`requirement_id`、`requirement_text`、provider、model、top-k、context hash 和生成时间；
- 禁止构造正式 `EvidenceItem`，禁止写数据库；
- 无需 DeepSeek 授权，也不会发出外部生成请求。

默认命令：

```powershell
cd backend
uv run --no-sync python -m src.tools.build_shadow_rag_contexts `
  --report-id report-xxx `
  --retrieval-cases tmp/embedding/envision_shadow_retrieval_cases.csv `
  --output tmp/embedding/envision_shadow_rag_contexts.jsonl
```

- [x] **Step 4: 实现可选离线生成评估**

创建 `backend/src/tools/evaluate_shadow_rag.py`：

- 复用 `src.tools.llm_client.LLMClient`；
- prompt 版本固定为 `shadow-rag-v1`，与正式 AI suggestion prompt 分离；
- 没有 `--confirm-llm` 时抛出 `ModelCallBlocked`，不得仅凭环境变量自动调用；
- 输出字段使用 `shadow_suggested_verdict`、`shadow_rationale`、`shadow_cited_evidence_ids`，避免伪装成正式建议；
- 只允许引用当前 context pack 中的 `shadow_evidence_id`；
- 与人工基线比较时至少输出 verdict 一致数、false disclosed、wrong source page、unknown leakage 和 invalid shadow citation；
- 结果和汇总只写 `tmp/embedding/`；
- 不调用 `AIAssessmentService`，不写 `ai_assessment_suggestions`，不修改 assessment。

默认只构造 context pack。真实生成命令属于单独停止点，必须同时满足：

1. 用户当次明确批准 DeepSeek 真实调用；
2. 本机已配置 LLM key；
3. 命令显式传入 `--confirm-llm`；
4. 输入 context pack 已完成结构和页码抽样检查。

- [x] **Step 5: 运行影子 RAG 测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_shadow_rag.py -q
```

Expected: PASS。默认测试只使用 fake LLM，不访问 SiliconFlow 或 DeepSeek。

## 12. Task 9: 文档与数据模型影响说明

**Files:**
- Modify: `docs/DESIGN.md`
- Modify: `docs/DEVELOPMENT.md`
- Modify: `docs/product/data-model-impact.md`

- [x] **Step 1: 更新技术设计边界**

在 `docs/DESIGN.md` 记录：

- `document_chunk_embeddings` 是可重建的派生数据；
- 第一阶段只支持显式 report 范围、精确余弦检索和离线产物；
- 影子 RAG 不属于正式 evidence、AI suggestion 或 assessment；
- `retrieve_evidence()`、`SingleReportWorkflow` 和前端 API 无变化；
- Phase 2/3 需要独立计划和重新验收，不能通过当前开关自动启用。

- [x] **Step 2: 更新开发文档**

在 `docs/DEVELOPMENT.md` 增加：

```markdown
SiliconFlow BGE-M3 离线影子 RAG 环境变量：

- `EMBEDDING_ENABLED=false`：默认关闭；
- `EMBEDDING_PROVIDER=siliconflow`；
- `EMBEDDING_API_BASE=https://api.siliconflow.cn/v1`；
- `EMBEDDING_API_KEY`：只保存在本机 `backend/.env` 或当前 shell；
- `EMBEDDING_MODEL=BAAI/bge-m3`；
- `EMBEDDING_DIM=1024`；
- `EMBEDDING_BATCH_SIZE=16`；
- `EMBEDDING_MAX_INPUT_TOKENS=8192`；
- `EMBEDDING_MAX_INPUT_CHARS=6000`；
- `EMBEDDING_TIMEOUT_SECONDS=60`；
- `EMBEDDING_MAX_RETRIES=2`。
```

运行示例：

```powershell
cd backend
$env:EMBEDDING_ENABLED="true"
uv run --no-sync python -m src.tools.embed_document_chunks `
  --report-id report-xxx `
  --limit 128
uv run --no-sync python -m src.tools.shadow_vector_retrieval `
  --report-id report-xxx `
  --query "温室气体排放范围一和范围二披露" `
  --top-k 10 `
  --output tmp/embedding/ghg_scope_search.csv
uv run --no-sync python -m src.tools.evaluate_shadow_retrieval `
  --report-id report-xxx `
  --output-prefix tmp/embedding/envision_shadow_retrieval
uv run --no-sync python -m src.tools.build_shadow_rag_contexts `
  --report-id report-xxx `
  --retrieval-cases tmp/embedding/envision_shadow_retrieval_cases.csv `
  --output tmp/embedding/envision_shadow_rag_contexts.jsonl
```

文档必须明确：

- 以上命令中的真实 SiliconFlow 调用需要执行当次单独授权；
- DeepSeek 影子生成需要另一项单独授权和 `--confirm-llm`；
- API key 由用户预先放入本机环境，文档和命令输出不打印 key；
- `tmp/embedding/` 产物是诊断材料，不构成最终合规结论；
- migration 在测试库验证通过后，升级 main/demo 数据库需要再次请示；
- migration head 会从 `0011_ai_suggestions` 变为 `0012_chunk_embeddings`，业务冻结版本仍保持 Envision v1.1。

- [x] **Step 3: 更新数据模型影响文档**

在 `docs/product/data-model-impact.md` 登记：

- 新表、字段、复合主键和约束；
- `document_chunks` 删除时 embedding 级联删除；
- failed 记录不保存零向量；
- 不复用 `document_chunks.embedding_*` 旧字段；
- 表可重建，不属于正式证据或审计事实；
- migration 只新增 extension 和表，不回写现有报告、run、assessment 或 export。

- [x] **Step 4: 检查文档安全**

Run:

```powershell
rg -n "(SILICONFLOW_API_KEY|EMBEDDING_API_KEY|LLM_API_KEY)=.*(sk-|[A-Za-z0-9]{24,})" docs backend/.env.example
rg -n "C:\\\\|C:/" docs/plan/siliconflow-bge-m3-shadow-embedding-plan.md
```

Expected: 没有密钥或本机绝对路径输出。

## 13. Task 10: 回归验证与基线零变化

**Files:**
- No production code changes.

- [x] **Step 1: 只升级并验证测试库**

Run:

```powershell
cd backend
$env:APP_ENV="test"
$env:DATABASE_URL="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_test"
uv run --no-sync python -c "from src.config.settings import get_settings; print(get_settings().database_url)"
uv run --no-sync alembic upgrade head
uv run --no-sync alembic current
```

Expected: 输出明确指向 `esg_agent_test`，migration head 为 `0012_chunk_embeddings`。若 extension、权限或向量类型失败，立即停止；不得改 main/demo 数据库来绕过。

- [x] **Step 2: 运行 focused tests**

Run:

```powershell
cd backend
uv run --no-sync pytest `
  tests/test_settings.py `
  tests/tools/test_embedding_client.py `
  tests/tools/test_shadow_retrieval.py `
  tests/tools/test_shadow_rag.py `
  tests/db/test_repositories.py `
  tests/db/test_migrations.py `
  -q
```

Expected: PASS，且测试日志不包含真实外部请求。

- [x] **Step 3: 运行后端全量测试**

Run:

```powershell
cd backend
uv run --no-sync pytest -q
```

Expected: PASS。当前基线为 651 项，新增测试后数量增加；已有测试不得减少或跳过。

- [x] **Step 4: 重跑 Envision v3 冻结门禁**

Run:

```powershell
cd backend
uv run --no-sync python -m src.tools.regenerate_review_csv `
  --report-id envision_2024_v3 `
  --pdf "data/reports/Envision Energy 2024-zh.pdf" `
  --profile data/reports/profiles/envision_2024.json `
  --requirements data/manifests/gri_requirement_checklist_v3.json `
  --manual-review-workbook data/review_inputs/envision_2024/manual/envision_2024_577_manual_review_second_review_Pro_20260719.xlsx `
  --final-adjudications data/review_inputs/envision_2024/adjudication/envision_2024_result_adjudication_v1.csv `
  --output data/runtime/evaluations/envision_2024/current_499_review_regenerated.csv `
  --baseline data/review_inputs/envision_2024/baselines/current_577_review_regenerated.csv `
  --audit-output data/runtime/evaluations/envision_2024/current_499_review_regenerated_audit.json `
  --diff-summary-output data/runtime/evaluations/envision_2024/current_499_review_regeneration_diff_summary.json `
  --scope-summary-output data/runtime/evaluations/envision_2024/current_499_review_scope_summary.json `
  --report-total-pages 78
```

Expected:

- `577/499/78/0` 保持不变；
- global fallback 为 0；
- 新增 false disclosed 为 0；
- 新增 wrong source page 为 0；
- audit 为 0 error、0 warning；
- assessment、risk、review snapshot 和 export 没有 embedding/RAG 字段或行为变化。

- [x] **Step 5: 验证默认禁用和仓库卫生**

Run:

```powershell
cd backend
$env:EMBEDDING_ENABLED="false"
uv run --no-sync pytest tests/tools/test_embedding_client.py::test_embedding_client_blocks_when_disabled -q
cd ..
git diff --check
rg -n "(sk-[A-Za-z0-9_-]+|EMBEDDING_API_KEY=.*\\S|SILICONFLOW_API_KEY=.*\\S)" --glob "!backend/.env" .
```

Expected: 禁用测试通过、`git diff --check` 无输出、没有新增密钥。

- [x] **Step 6: 主库和 demo 库迁移停止点**

在 Step 1–5 全部通过后，汇报：

- migration 影响；
- 测试结果；
- Envision 零回归结果；
- 是否发现 main/demo schema 差异。

只有获得用户再次明确批准，才分别对 main 和 demo 数据库执行 `alembic upgrade head`。升级后只验证 extension、表、约束和 head，不自动批量向量化。

执行记录（2026-07-26）：用户明确批准后，`esg_agent` 与 `esg_agent_demo` 均已升级到 `0012_chunk_embeddings`。两个库均启用 pgvector `0.8.4`，向量列为 `vector(1024)`，迁移后影子向量记录均为 0；正式库 64 份报告、demo 库 5 份报告均保留。

- [ ] **Step 7: 真实 API 停止点**

真实 SiliconFlow 冒烟、指定 Envision 报告批量向量化、批量召回评估和 DeepSeek 影子生成分开请示。实现完成不以真实 API 调用为必要条件。

## 14. 后续迭代规划

以下内容只登记方向，不属于本计划当前实施范围，不随 `EMBEDDING_ENABLED` 自动启用。

### Phase 1.5：离线混合影子上下文（已实现）

基于 Envision 人工页码基线，规则召回与向量召回采用 RRF 2：1 融合：

- 向量 Top 10 作为内部候选池；
- 规则页从指定报告的 `document_chunks` 只读补齐正文；
- 最终影子 RAG context 截取 Top 5；
- 输出融合来源、双路排名、融合分数和未解析规则页；
- 默认纯向量模式继续保留；
- 不调用外部服务，不写数据库，不进入正式分析链路。

实现和验证细节见：

- `docs/plan/hybrid-shadow-context-design.md`
- `docs/plan/hybrid-shadow-context-implementation-plan.md`

### Phase 2: 影子 RAG 进入正式 AI suggestion

目标：在 assessment 已由现有规则生成后，把规则证据与向量候选组成混合上下文，提升 AI 建议的证据覆盖与解释质量。AI suggestion 仍然是辅助层，不覆盖规则 assessment。

进入条件：

- Envision 影子召回 `recall@5` 不低于当前规则召回基线；
- 存在经过抽样确认的 `vector_only` 有效新证据；
- 至少 20–50 条影子生成结果完成人工抽查；
- false disclosed、wrong source page 和 invalid citation 均为 0；
- 费用、时延、失败降级和 prompt 版本已记录。

需要独立计划评估的改动：

- 把已验证的离线混合检索接入正式 suggestion 输入，并完成证据 ID 正式化和来源追踪；
- `ai_suggestion_input_hash`、prompt 版本及模型版本；
- 外部模型失败时保持当前规则结果和人工流程可用；
- AI suggestion API、审计字段、前端标签和用户解释；
- 旧 suggestion 兼容与重新生成策略。

Phase 2 不允许直接修改 `assessment.verdict`、risk 或正式输出门禁。

### Phase 3: RAG 参与 assessment

目标：评估向量候选能否进入正式证据路由并影响 assessment。该阶段会解除部分后端冻结，影响范围显著，必须另写计划并重新验收。

前置条件：

- Phase 2 已形成稳定、可追溯的混合证据；
- Envision 全量人工基线与最终裁决可重放；
- 有独立 holdout 或新增报告验证，避免只对 Envision 过拟合；
- 明确披露结论、证据质量、复核优先级三层职责；
- AI 结果仍不能直接成为最终合规结论。

必须重新设计和验证：

- 向量候选提升为正式 `EvidenceItem` 的准入条件；
- 页码、文本、文件 hash 和 chunk 来源的完整审计链；
- 冲突证据、低相似度、无证据和模型失败时的确定性降级；
- assessment、risk-v2.1、review snapshot、整改任务和 export 的连锁影响；
- Envision 577、人工裁决、Goldwind/新报告泛化、前端说明和 API 契约；
- 数据迁移、历史 run 可重放与版本隔离。

未满足上述条件时，Phase 3 保持关闭。

## 15. 风险与取舍

- **外部服务风险：** SiliconFlow 限流、过载或超时会导致批次失败。失败向量保存为空并记录错误，不影响主分析。
- **成本风险：** 同一 PDF 重复上传会产生不同 report/chunk ID，可能重复付费。所有批量操作强制 `--report-id`，按 `(chunk_id, provider, model)` 幂等写入。
- **输入长度风险：** 数据库存在超长 chunk。先做确定性的空白规范化和 6000 字符上限；该限制只影响 embedding 输入，不覆盖原文。
- **召回误导风险：** 相似度高不代表披露充分。用人工正确页计算指标，并把无人工页项目从 recall 分母排除。
- **生成误导风险：** 影子 LLM 可能产生错误结论或越界引用。引用必须来自 context pack，越界单独计错，结果只保存在 `tmp/embedding/`。
- **近似索引风险：** 小样本上 IVFFlat/HNSW 参数会影响召回。第一阶段使用精确余弦检索，不创建近似索引。
- **迁移风险：** pgvector extension 依赖数据库权限。测试库失败时停止，不降级为 JSON 或覆盖旧 embedding 字段。
- **环境误操作风险：** main/demo 数据库可能使用不同连接。每次迁移先打印数据库 URL/名称，测试库、main、demo 分开授权和执行。
- **冻结基线风险：** schema head 会增加到 `0012_chunk_embeddings`，业务行为仍保持 Envision v1.1。必须以 Envision regeneration gate 证明 assessment、risk、review 和 export 零变化。
- **密钥风险：** SiliconFlow 和 DeepSeek key 只能存在本机环境；命令、日志、文档和提交都不得包含值。

## 16. 完成标准

- `EMBEDDING_ENABLED=false` 时，在读取 chunk、写 embedding 和外部请求前阻断。
- `BAAI/bge-m3` 请求不包含 `dimensions`，返回向量严格校验为 1024 维。
- `document_chunk_embeddings.embedding` 使用 nullable `vector(1024)`，failed 记录没有零向量。
- migration 先在 `esg_agent_test` 验证；main/demo 升级需要独立批准。
- 可以幂等向量化指定 report 的 `document_chunks`，不能默认跨报告运行。
- 可以在指定报告内精确召回 top-k chunk，输出页码、chunk_id、score 和原文片段。
- 可以按人工正确页生成 `hit@k`、`recall@k`、MRR 和规则/向量对照明细。
- 可以生成独立 shadow RAG context pack；可选生成结果只使用 `shadow_*` 字段并保存在 `tmp/embedding/`。
- 默认测试不调用 SiliconFlow 或 DeepSeek，不写正式 evidence、AI suggestion、assessment、risk、review snapshot 或 export。
- focused tests、后端全量 pytest 和 Envision `577/499/78/0` 零回归门禁通过。
- `docs/DESIGN.md`、`docs/DEVELOPMENT.md` 和 `docs/product/data-model-impact.md` 说明 schema 与业务冻结的区别。
- 仓库没有新增 `.env`、API key、外部服务非公开响应或本机绝对路径。
- 真实 API 冒烟不是代码完成条件，每次真实调用都需再次显式确认。
