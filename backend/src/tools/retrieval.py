from src.domain.models import DisclosureTask, DocumentChunk, EvidenceItem
from src.tools.evidence import chunk_to_evidence


def retrieve_evidence(task: DisclosureTask, chunks: list[DocumentChunk], limit: int = 5) -> list[EvidenceItem]:
    if task.candidate_pages:
        candidate_page_set = set(task.candidate_pages)
        retrieval_metadata = {
            "retrieval_strategy": "index_page_bounded",
            "candidate_pages": task.candidate_pages,
            "candidate_page_source": task.candidate_page_source,
            "index_page": task.index_page,
        }
        bounded_matches = _keyword_matches(
            task,
            [chunk for chunk in chunks if chunk.source_page in candidate_page_set],
            limit,
            retrieval_metadata,
        )
        if bounded_matches:
            return bounded_matches

        return _keyword_matches(
            task,
            chunks,
            limit,
            {
                "retrieval_strategy": "global_fallback",
                "candidate_pages": task.candidate_pages,
                "candidate_page_source": task.candidate_page_source,
                "index_page": task.index_page,
            },
        )

    return _keyword_matches(task, chunks, limit, {"retrieval_strategy": "global_no_index"})


def _keyword_matches(
    task: DisclosureTask,
    chunks: list[DocumentChunk],
    limit: int,
    retrieval_metadata: dict,
) -> list[EvidenceItem]:
    keywords = [keyword.lower() for keyword in task.keywords]
    matches: list[EvidenceItem] = []
    for chunk in chunks:
        text = chunk.text.lower()
        if keywords and not any(keyword in text for keyword in keywords):
            continue
        matches.append(chunk_to_evidence(task, chunk, retrieval_metadata=retrieval_metadata))
        if len(matches) >= limit:
            break
    return matches
