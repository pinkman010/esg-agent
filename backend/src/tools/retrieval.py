from src.domain.enums import PageQualityFlag
from src.domain.models import DisclosureTask, DocumentChunk, EvidenceItem
from src.tools.evidence import chunk_to_evidence
from src.tools.kpi_row_matcher import match_kpi_rows


def retrieve_evidence(task: DisclosureTask, chunks: list[DocumentChunk], limit: int = 5) -> list[EvidenceItem]:
    if task.candidate_pages:
        candidate_page_set = set(task.candidate_pages)
        retrieval_metadata = {
            "retrieval_strategy": "index_page_bounded",
            "candidate_pages": task.candidate_pages,
            "candidate_pdf_pages": task.candidate_pdf_pages,
            "candidate_report_pages": task.candidate_report_pages,
            "candidate_page_source": task.candidate_page_source,
            "index_page": task.index_page,
            "kpi_table_pages": task.kpi_table_pages,
            "kpi_metric_terms": task.kpi_metric_terms,
            "kpi_year_columns": task.kpi_year_columns,
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
                "candidate_pdf_pages": task.candidate_pdf_pages,
                "candidate_report_pages": task.candidate_report_pages,
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
    kpi_metric_terms = list(retrieval_metadata.get("kpi_metric_terms") or [])
    kpi_table_pages = set(retrieval_metadata.get("kpi_table_pages") or [])
    if kpi_metric_terms and kpi_table_pages:
        kpi_chunks = [
            chunk
            for chunk in chunks
            if chunk.source_page in kpi_table_pages and PageQualityFlag.COMPLEX_TABLE in chunk.quality_flags
        ]
        row_matches = match_kpi_rows(
            kpi_chunks,
            kpi_metric_terms,
            year_columns=list(retrieval_metadata.get("kpi_year_columns") or ["2024"]),
        )
        if row_matches:
            return [
                chunk_to_evidence(
                    task,
                    match.chunk,
                    retrieval_metadata={
                        **retrieval_metadata,
                        "kpi_row_label": match.row_label,
                        "kpi_row_unit": match.unit,
                        "kpi_row_value": match.value,
                        "kpi_year_column": match.year_column,
                        "kpi_row_preview": match.preview,
                    },
                )
                for match in row_matches[:limit]
            ]

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
