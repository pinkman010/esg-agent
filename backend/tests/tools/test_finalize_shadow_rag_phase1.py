import csv
import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

import src.tools.finalize_shadow_rag_phase1 as finalizer
from src.tools.finalize_shadow_rag_phase1 import (
    FORMAL_TABLE_MODELS,
    ensure_offline_phase1_5,
    finalize_phase1_5,
    fingerprint_file,
)


def test_phase1_5_finalizer_blocks_when_embedding_enabled():
    with pytest.raises(
        RuntimeError,
        match="EMBEDDING_ENABLED=false",
    ):
        ensure_offline_phase1_5(embedding_enabled=True)


def test_phase1_5_finalizer_requires_demo_database():
    with pytest.raises(RuntimeError, match="esg_agent_demo"):
        finalizer.ensure_demo_phase1_5(
            app_env="demo",
            database_url=("postgresql+psycopg://user:pass@localhost/esg_agent"),
        )


def test_validate_git_head_rejects_supplied_head_mismatch():
    with pytest.raises(ValueError, match="git_head"):
        finalizer.validate_git_head(
            supplied_head="a" * 40,
            actual_head="b" * 40,
        )


def test_formal_table_model_set_excludes_shadow_embeddings():
    assert "document_chunk_embeddings" not in FORMAL_TABLE_MODELS
    assert {
        "reports",
        "analysis_runs",
        "analysis_stage_events",
        "document_pages",
        "document_chunks",
        "standard_requirements",
        "disclosure_tasks",
        "assessments",
        "ai_assessment_suggestions",
        "assessment_risks",
        "evidence_items",
        "recommendations",
        "review_decisions",
        "review_snapshots",
        "review_change_events",
        "improvement_actions",
        "export_versions",
        "audit_events",
    } == set(FORMAL_TABLE_MODELS)


def test_fingerprint_file_records_relative_path_hash_and_size(
    tmp_path,
):
    asset = tmp_path / "data" / "asset.txt"
    asset.parent.mkdir()
    asset.write_bytes(b"phase-1.5")

    result = fingerprint_file(asset, project_root=tmp_path)

    assert result == {
        "path": "data/asset.txt",
        "sha256": hashlib.sha256(b"phase-1.5").hexdigest(),
        "size_bytes": 9,
    }


def test_finalize_phase1_5_uses_read_only_transaction_and_two_builds(
    tmp_path,
    monkeypatch,
):
    retrieval_path = tmp_path / "cases.csv"
    with retrieval_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "report_id",
                "requirement_id",
                "gold_pages",
                "rule_pages",
                "vector_source_pages",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "report_id": "report-envision",
                "requirement_id": "GRI 2-1-a",
                "gold_pages": "[1]",
                "rule_pages": "[8]",
                "vector_source_pages": "[1]",
            }
        )
    input_paths = {
        name: tmp_path / name
        for name in (
            "requirements.json",
            "baseline.csv",
            "manual.xlsx",
            "adjudications.csv",
            "report.pdf",
        )
    }
    for path in input_paths.values():
        path.write_bytes(path.name.encode())
    for relative_path in (
        "backend/src/tools/shadow_context_acceptance.py",
        "backend/src/tools/finalize_shadow_rag_phase1.py",
        "backend/src/tools/build_shadow_rag_contexts.py",
        "backend/src/tools/evaluate_shadow_retrieval.py",
    ):
        implementation_path = tmp_path / relative_path
        implementation_path.parent.mkdir(parents=True, exist_ok=True)
        implementation_path.write_text(relative_path, encoding="utf-8")

    context = {
        "report_id": "report-envision",
        "requirement_id": "GRI 2-1-a",
        "context_hash": "a" * 64,
        "retrieval_mode": "hybrid_rrf",
        "vector_pool_k": 10,
        "context_k": 5,
        "top_k": 5,
        "rrf_rule_weight": 2.0,
        "rrf_vector_weight": 1.0,
        "rrf_constant": 60,
        "provider": "siliconflow",
        "model": "BAAI/bge-m3",
        "unresolved_rule_pages": [],
        "evidence": [
            {
                "chunk_id": f"chunk-{page}",
                "shadow_evidence_id": f"shadow-chunk:chunk-{page}",
                "source_page": page,
                "retrieval_sources": ["rule"],
                "rule_rank": page,
                "vector_rank": None,
                "fusion_score": 2 / (60 + page),
            }
            for page in range(1, 6)
        ],
    }

    class FakeSession:
        def __init__(self):
            self.events = []
            self.commit_calls = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.events.append("close")

        def execute(self, statement):
            self.events.append(f"execute:{statement}")

        def scalar(self, statement):
            self.events.append("scalar")
            if "current_database()" in str(statement):
                return "esg_agent_demo"
            return 10

        def add(self, *_args):
            raise AssertionError("read-only finalizer called add")

        def flush(self):
            raise AssertionError("read-only finalizer called flush")

        def commit(self):
            self.commit_calls += 1
            raise AssertionError("read-only finalizer called commit")

    fake_session = FakeSession()
    repository_calls = []

    class FakeRepository:
        def __init__(self, session):
            assert session is fake_session

        def list_document_chunks(self, *, report_id):
            repository_calls.append(report_id)
            return [
                {
                    "chunk_id": "chunk-1",
                    "report_id": report_id,
                    "source_page": 1,
                    "text": "正文",
                }
            ]

    build_calls = []

    def fake_load_contexts(cases_path, **kwargs):
        build_calls.append((cases_path, kwargs))
        return [deepcopy(context)]

    def fake_resolve_output(output):
        path = tmp_path / output.removeprefix("tmp/embedding/")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def fake_write_contexts(contexts, *, output):
        path = fake_resolve_output(output)
        serialized_contexts = deepcopy(contexts)
        serialized_contexts[0]["serialized_marker"] = True
        path.write_text(
            "".join(
                json.dumps(row, sort_keys=True) + "\n" for row in serialized_contexts
            ),
            encoding="utf-8",
        )
        return path

    audited_contexts = []
    real_audit_contexts = finalizer.audit_contexts

    def capture_audited_contexts(contexts, **kwargs):
        audited_contexts.extend(contexts)
        return real_audit_contexts(contexts, **kwargs)

    monkeypatch.setattr(finalizer, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(finalizer, "EXPECTED_CASE_COUNT", 1)
    monkeypatch.setattr(
        finalizer,
        "EXPECTED_EVALUATED_CASE_COUNT",
        1,
    )
    monkeypatch.setattr(
        finalizer,
        "get_settings",
        lambda: SimpleNamespace(
            app_env="demo",
            database_url=("postgresql+psycopg://user:pass@localhost/esg_agent_demo"),
            embedding_enabled=False,
            embedding_provider="siliconflow",
            embedding_model="BAAI/bge-m3",
        ),
    )
    monkeypatch.setattr(finalizer, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(finalizer, "Repository", FakeRepository)
    monkeypatch.setattr(
        finalizer,
        "load_shadow_contexts_from_cases",
        fake_load_contexts,
    )
    monkeypatch.setattr(
        finalizer,
        "write_shadow_contexts",
        fake_write_contexts,
    )
    monkeypatch.setattr(
        finalizer,
        "resolve_shadow_output",
        fake_resolve_output,
    )
    monkeypatch.setattr(
        finalizer,
        "capture_git_state",
        lambda **_kwargs: {
            "head": "a" * 40,
            "dirty": True,
            "status_sha256": "b" * 64,
            "changed_paths": ["backend/src/tools/example.py"],
        },
    )
    monkeypatch.setattr(
        finalizer,
        "audit_contexts",
        capture_audited_contexts,
    )

    result = finalize_phase1_5(
        report_id="report-envision",
        retrieval_cases_path=retrieval_path,
        requirements_path=input_paths["requirements.json"],
        baseline_path=input_paths["baseline.csv"],
        manual_review_path=input_paths["manual.xlsx"],
        final_adjudications_path=input_paths["adjudications.csv"],
        report_pdf_path=input_paths["report.pdf"],
        context_output="tmp/embedding/envision_phase1_5_contexts.jsonl",
        output_prefix="tmp/embedding/envision_phase1_5_acceptance",
        report_total_pages=78,
        git_head="a" * 40,
    )

    assert str(fake_session.events[0]).startswith(
        "execute:SET TRANSACTION ISOLATION LEVEL"
    )
    assert repository_calls == ["report-envision"]
    assert len(build_calls) == 2
    assert fake_session.commit_calls == 0
    assert result["ok"] is True
    assert result["deterministic_hash_mismatch_count"] == 0
    assert audited_contexts[0]["serialized_marker"] is True
    assert (tmp_path / "envision_phase1_5_acceptance_cases.csv").is_file()
    assert (tmp_path / "envision_phase1_5_acceptance_summary.json").is_file()
    assert (tmp_path / "envision_phase1_5_input_manifest.json").is_file()
    assert (tmp_path / "envision_phase1_5_formal_state.json").is_file()
    assert (tmp_path / "envision_phase1_5_acceptance_report.md").is_file()


def test_main_passes_cli_arguments_and_prints_json(
    tmp_path,
    monkeypatch,
    capsys,
):
    retrieval_path = tmp_path / "cases.csv"
    retrieval_path.write_text("", encoding="utf-8")
    calls = []

    def fake_finalize(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "case_count": 499}

    monkeypatch.setattr(finalizer, "finalize_phase1_5", fake_finalize)

    finalizer.main(
        [
            "--report-id",
            "report-envision",
            "--retrieval-cases",
            str(retrieval_path),
            "--git-head",
            "0cf3cbc",
        ]
    )

    assert calls[0]["report_id"] == "report-envision"
    assert calls[0]["retrieval_cases_path"] == retrieval_path
    assert json.loads(capsys.readouterr().out)["case_count"] == 499


def test_main_exits_nonzero_when_acceptance_gate_fails(
    tmp_path,
    monkeypatch,
):
    retrieval_path = tmp_path / "cases.csv"
    retrieval_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        finalizer,
        "finalize_phase1_5",
        lambda **_kwargs: {"ok": False},
    )

    with pytest.raises(SystemExit) as exc_info:
        finalizer.main(
            [
                "--report-id",
                "report-envision",
                "--retrieval-cases",
                str(retrieval_path),
                "--git-head",
                "0cf3cbc",
            ]
        )

    assert exc_info.value.code == 1
