from src.domain.models import DisclosureTask, DocumentChunk, EvidenceItem
from src.tools.ids import database_safe_id


def evidence_id_for(task_id: str, chunk_id: str) -> str:
    raw_id = f"{task_id}:{chunk_id}"
    return database_safe_id(raw_id, "evidence")


def chunk_to_evidence(
    task: DisclosureTask,
    chunk: DocumentChunk,
    retrieval_metadata: dict | None = None,
) -> EvidenceItem:
    metadata = {**chunk.metadata, "task_id": task.task_id, "chunk_id": chunk.chunk_id}
    if retrieval_metadata:
        metadata.update(retrieval_metadata)

    return EvidenceItem(
        evidence_id=evidence_id_for(task.task_id, chunk.chunk_id),
        run_id=task.run_id,
        report_id=task.report_id,
        source_text=chunk.text,
        source_page=chunk.source_page,
        source_file_hash=chunk.source_file_hash,
        source_method=chunk.source_method,
        bbox=chunk.bbox,
        quality_flags=chunk.quality_flags,
        metadata=metadata,
    )
