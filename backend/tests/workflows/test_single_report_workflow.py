import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from src.agents.disclosure_agent import DisclosureAgent
from src.db.base import Base
from src.db.models import AssessmentRecord, AuditEventRecord, DisclosureTaskRecord, EvidenceItemRecord, RecommendationRecord
from src.db.repositories import Repository
from src.domain.enums import EvidenceSourceMethod, RunStatus
from src.domain.models import AnalysisRun, DisclosureRequirement, DocumentChunk, PageExtraction, Report
from src.services.document_parser import ParsedDocument
from src.workflows.single_report_workflow import SingleReportWorkflow
from tests.database import make_test_engine, reset_database


class FakeParser:
    def parse_pdf(self, pdf_path, report_id, source_file_hash, ocr_pages=None):
        return ParsedDocument(
            report_id=report_id,
            page_count=1,
            pages=[PageExtraction(report_id=report_id, page_number=1, text="Energy consumption is disclosed.")],
            chunks=[
                DocumentChunk(
                    chunk_id="chunk-1",
                    report_id=report_id,
                    text="Energy consumption is disclosed.",
                    source_page=1,
                    source_method=EvidenceSourceMethod.PDFPLUMBER,
                    source_file_hash=source_file_hash,
                )
            ],
            metadata={},
            outline=[],
        )


class FailingParser:
    def parse_pdf(self, pdf_path, report_id, source_file_hash, ocr_pages=None):
        raise RuntimeError("parse failed")


class IndexParser:
    def parse_pdf(self, pdf_path, report_id, source_file_hash, ocr_pages=None):
        return ParsedDocument(
            report_id=report_id,
            page_count=71,
            pages=[
                PageExtraction(
                    report_id=report_id,
                    page_number=71,
                    text="2-1 组织详细情况 关于远景能源 5",
                )
            ],
            chunks=[
                DocumentChunk(
                    chunk_id="chunk-page-1",
                    report_id=report_id,
                    text="legal name appears on the wrong page",
                    source_page=1,
                    source_method=EvidenceSourceMethod.PDFPLUMBER,
                    source_file_hash=source_file_hash,
                ),
                DocumentChunk(
                    chunk_id="chunk-page-6",
                    report_id=report_id,
                    text="Legal name: Envision Energy Co., Ltd.",
                    source_page=6,
                    source_method=EvidenceSourceMethod.PDFPLUMBER,
                    source_file_hash=source_file_hash,
                ),
            ],
            metadata={},
            outline=[],
        )


class FakeAdapter:
    def load_requirements(self):
        return [
            DisclosureRequirement(
                standard_id="GRI 2",
                standard_version="2021",
                disclosure_id="GRI 2-1",
                requirement_id="GRI 2-1-a",
                requirement_text="report its legal name;",
                keywords=["legal", "name"],
            )
        ]

    def build_tasks(self, run_id, report_id):
        return [requirement_to_task(self.load_requirements()[0], run_id, report_id)]


def requirement_to_task(requirement, run_id, report_id):
    from src.domain.models import DisclosureTask

    return DisclosureTask(
        task_id=f"{run_id}:{requirement.requirement_id}",
        run_id=run_id,
        report_id=report_id,
        standard_id=requirement.standard_id,
        standard_version=requirement.standard_version,
        disclosure_id=requirement.disclosure_id,
        requirement_id=requirement.requirement_id,
        requirement_text=requirement.requirement_text,
        keywords=requirement.keywords,
    )


@pytest.fixture
def repo_session():
    engine = make_test_engine()
    reset_database(engine)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()


def seed_report(repo):
    repo.create_report(
        Report(
            report_id="report-1",
            original_filename="report.pdf",
            stored_path="backend/data/runtime/uploads/report.pdf",
            file_hash="hash-1",
            page_count=1,
        )
    )


def test_single_report_workflow_completes_without_model_calls(repo_session):
    repo = Repository(repo_session)
    seed_report(repo)
    workflow = SingleReportWorkflow(repo, FakeParser(), FakeAdapter(), DisclosureAgent())

    run = workflow.run("report-1", Path("report.pdf"), "hash-1", confirm_llm=False)

    assert run.status is RunStatus.COMPLETED
    assert repo_session.scalar(select(AssessmentRecord).where(AssessmentRecord.run_id == run.run_id)).model_called is False
    event_types = repo_session.scalars(
        select(AuditEventRecord.event_type)
        .where(AuditEventRecord.run_id == run.run_id)
        .order_by(AuditEventRecord.audit_event_id)
    ).all()
    assert event_types == ["analysis_started", "parse_completed", "analysis_completed"]


def test_single_report_workflow_marks_run_failed_on_parser_error(repo_session):
    repo = Repository(repo_session)
    seed_report(repo)
    workflow = SingleReportWorkflow(repo, FailingParser(), FakeAdapter(), DisclosureAgent())

    run = workflow.run("report-1", Path("report.pdf"), "hash-1", confirm_llm=False)

    assert run.status is RunStatus.FAILED
    assert "parse failed" in (run.error_message or "")
    assert repo_session.scalar(select(RecommendationRecord).where(RecommendationRecord.run_id == run.run_id)) is None


def test_single_report_workflow_attaches_report_index_candidate_pages(repo_session, tmp_path):
    pack_path = tmp_path / "gri_requirement_pack.json"
    pack_path.write_text(
        json.dumps(
            {
                "requirements": [
                    {
                        "canonical_disclosure_id": "2-1",
                        "report_index_pdf_page": 71,
                        "report_index_report_page": 70,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    repo = Repository(repo_session)
    seed_report(repo)
    workflow = SingleReportWorkflow(
        repo,
        IndexParser(),
        FakeAdapter(),
        DisclosureAgent(),
        requirement_pack_path=pack_path,
    )

    run = workflow.run("report-1", Path("report.pdf"), "hash-1", confirm_llm=False)

    assert run.status is RunStatus.COMPLETED
    task = repo_session.scalar(select(DisclosureTaskRecord).where(DisclosureTaskRecord.run_id == run.run_id))
    assert task.keywords == ["legal", "name"]
    evidence = repo_session.scalar(select(EvidenceItemRecord).where(EvidenceItemRecord.run_id == run.run_id))
    assert evidence.source_page == 6
    assert evidence.source_pdf_page == 6
    assert evidence.source_report_page == 5
    assert evidence.evidence_metadata["retrieval_strategy"] == "index_page_bounded"
    assert evidence.evidence_metadata["candidate_pages"] == [6]
    assert evidence.evidence_metadata["candidate_pdf_pages"] == [6]
    assert evidence.evidence_metadata["candidate_report_pages"] == [5]
    assert evidence.evidence_metadata["index_page"] == 71
    assert evidence.evidence_metadata["source_pdf_page"] == 6
    assert evidence.evidence_metadata["source_report_page"] == 5


def test_single_report_workflow_supplements_candidate_pages_for_entity_attributes(tmp_path):
    pack_path = tmp_path / "gri_requirement_pack.json"
    pack_path.write_text(
        json.dumps(
            {
                "requirements": [
                    {
                        "canonical_disclosure_id": "2-1",
                        "report_index_pdf_page": 71,
                        "report_index_report_page": 70,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    workflow = SingleReportWorkflow(
        None,
        FakeParser(),
        FakeAdapter(),
        DisclosureAgent(),
        requirement_pack_path=pack_path,
    )
    pages = [
        PageExtraction(report_id="report-1", page_number=1, text="远景能源有限公司 Envision Energy Co., Ltd."),
        PageExtraction(report_id="report-1", page_number=3, text="报告主体为远景能源有限公司。"),
        PageExtraction(report_id="report-1", page_number=6, text="关于远景能源"),
        PageExtraction(report_id="report-1", page_number=28, text="上海总部大楼持续推进绿色运营。"),
        PageExtraction(report_id="report-1", page_number=71, text="2-1 组织详细情况 关于远景能源 5"),
    ]
    from src.domain.models import DisclosureTask

    tasks = [
        DisclosureTask(
            task_id="task-2-1-a",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 2",
            standard_version="2021",
            disclosure_id="GRI 2-1",
            requirement_id="GRI 2-1-a",
            requirement_text="report its legal name;",
            keywords=["有限公司"],
        ),
        DisclosureTask(
            task_id="task-2-1-c",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 2",
            standard_version="2021",
            disclosure_id="GRI 2-1",
            requirement_id="GRI 2-1-c",
            requirement_text="report the location of its headquarters;",
            keywords=["总部"],
        ),
    ]

    enriched = workflow._attach_report_index_candidates(pages, tasks)

    assert enriched[0].candidate_pages == [1, 3, 6]
    assert enriched[0].candidate_pdf_pages == [1, 3, 6]
    assert enriched[0].candidate_report_pages == [None, 2, 5]
    assert enriched[0].candidate_page_source == "gri_report_index+requirement_supplement"
    assert enriched[1].candidate_pages == [6, 28]
    assert enriched[1].candidate_pdf_pages == [6, 28]
    assert enriched[1].candidate_report_pages == [5, 27]
    assert enriched[1].candidate_page_source == "gri_report_index+requirement_supplement"


def test_single_report_workflow_supplements_candidate_pages_for_current_50_rules(tmp_path):
    pack_path = tmp_path / "gri_requirement_pack.json"
    pack_path.write_text(
        json.dumps(
            {
                "requirements": [
                    {"canonical_disclosure_id": "2-6", "report_index_pdf_page": 71, "report_index_report_page": 70},
                    {"canonical_disclosure_id": "2-7", "report_index_pdf_page": 71, "report_index_report_page": 70},
                    {"canonical_disclosure_id": "2-9", "report_index_pdf_page": 71, "report_index_report_page": 70},
                ]
            }
        ),
        encoding="utf-8",
    )
    workflow = SingleReportWorkflow(
        None,
        FakeParser(),
        FakeAdapter(),
        DisclosureAgent(),
        requirement_pack_path=pack_path,
    )
    pages = [
        PageExtraction(report_id="report-1", page_number=4, text="全球企业和政府深化合作。"),
        PageExtraction(report_id="report-1", page_number=6, text="主要业务包括智能风电、智慧储能系统和绿氢解决方案。"),
        PageExtraction(report_id="report-1", page_number=9, text="ESG 合作网络拓展。"),
        PageExtraction(report_id="report-1", page_number=13, text="ESG 治理架构 ESG委员会 ESG办公室 ESG议题执行小组。"),
        PageExtraction(report_id="report-1", page_number=33, text="人员结构 截至报告期末，员工组成。"),
        PageExtraction(report_id="report-1", page_number=52, text="责任采购，产业共荣 可持续供应链管理。"),
        PageExtraction(report_id="report-1", page_number=53, text="供应商准入 供应商尽职调查。"),
        PageExtraction(report_id="report-1", page_number=54, text="供应商退出 供应商培训与赋能。"),
        PageExtraction(report_id="report-1", page_number=65, text="社会绩效 员工组成 2024 2023 2022。"),
        PageExtraction(
            report_id="report-1",
            page_number=71,
            text=(
                "2-6 活动、价值链和其他业务关系 关于远景能源 5 ESG合作网络拓展 8\n"
                "2-7 员工 人才招聘与雇佣 31 附录 62\n"
                "2-9 管治架构和组成 ESG治理架构 12"
            ),
        ),
    ]
    from src.domain.models import DisclosureTask

    tasks = [
        DisclosureTask(
            task_id="task-2-6-b",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 2",
            standard_version="2021",
            disclosure_id="GRI 2-6",
            requirement_id="GRI 2-6-b",
            requirement_text="describe activities, products, services and markets;",
            keywords=["主要业务"],
        ),
        DisclosureTask(
            task_id="task-2-7-c",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 2",
            standard_version="2021",
            disclosure_id="GRI 2-7",
            requirement_id="GRI 2-7-c",
            requirement_text="describe methodologies and assumptions used to compile employee data;",
            keywords=["人员结构"],
        ),
        DisclosureTask(
            task_id="task-2-9-b",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 2",
            standard_version="2021",
            disclosure_id="GRI 2-9",
            requirement_id="GRI 2-9-b",
            requirement_text="list committees of the highest governance body;",
            keywords=["ESG治理架构"],
        ),
    ]

    enriched = workflow._attach_report_index_candidates(pages, tasks)

    assert enriched[0].candidate_pdf_pages == [4, 6, 9, 52, 53, 54]
    assert enriched[0].candidate_report_pages == [3, 5, 8, 51, 52, 53]
    assert enriched[1].candidate_pdf_pages == [32, 33, 63, 65]
    assert enriched[1].candidate_report_pages == [31, 32, 62, 64]
    assert enriched[2].candidate_pdf_pages == [13]
    assert enriched[2].candidate_report_pages == [12]


def test_single_report_workflow_supplements_candidate_pages_for_current_150_rules(tmp_path):
    pack_path = tmp_path / "gri_requirement_pack.json"
    pack_path.write_text(
        json.dumps(
            {
                "requirements": [
                    {"canonical_disclosure_id": "2-22", "report_index_pdf_page": 72, "report_index_report_page": 71},
                    {"canonical_disclosure_id": "2-23", "report_index_pdf_page": 72, "report_index_report_page": 71},
                    {"canonical_disclosure_id": "2-24", "report_index_pdf_page": 72, "report_index_report_page": 71},
                    {"canonical_disclosure_id": "2-25", "report_index_pdf_page": 72, "report_index_report_page": 71},
                    {"canonical_disclosure_id": "2-26", "report_index_pdf_page": 72, "report_index_report_page": 71},
                    {"canonical_disclosure_id": "2-28", "report_index_pdf_page": 72, "report_index_report_page": 71},
                    {"canonical_disclosure_id": "2-29", "report_index_pdf_page": 72, "report_index_report_page": 71},
                    {"canonical_disclosure_id": "3-1", "report_index_pdf_page": 72, "report_index_report_page": 71},
                ]
            }
        ),
        encoding="utf-8",
    )
    workflow = SingleReportWorkflow(
        None,
        FakeParser(),
        FakeAdapter(),
        DisclosureAgent(),
        requirement_pack_path=pack_path,
    )
    pages = [
        PageExtraction(report_id="report-1", page_number=4, text="董事长致辞 可持续发展 零碳目标。"),
        PageExtraction(report_id="report-1", page_number=5, text="CSO 致辞 可持续发展 治理结构。"),
        PageExtraction(report_id="report-1", page_number=9, text="UNGC RE100 SBTi CDP IEA WEF ESG 合作网络。"),
        PageExtraction(report_id="report-1", page_number=10, text="概述 责任治理 永续发展。"),
        PageExtraction(report_id="report-1", page_number=11, text="ESG战略与目标 政策承诺。"),
        PageExtraction(report_id="report-1", page_number=13, text="ESG治理架构 ESG委员会。"),
        PageExtraction(report_id="report-1", page_number=14, text="利益相关方沟通 关注议题 沟通渠道。"),
        PageExtraction(report_id="report-1", page_number=15, text="重要性评估 重要性矩阵 利益相关方调研。"),
        PageExtraction(report_id="report-1", page_number=16, text="环境章节封面。"),
        PageExtraction(report_id="report-1", page_number=31, text="人章节封面。"),
        PageExtraction(report_id="report-1", page_number=32, text="劳工与人权 人权侵害投诉机制 ILO 世界人权宣言。"),
        PageExtraction(report_id="report-1", page_number=33, text="挑战者代表 建言献策。"),
        PageExtraction(report_id="report-1", page_number=45, text="产品章节封面。"),
        PageExtraction(report_id="report-1", page_number=46, text="客户质量 产品安全。"),
        PageExtraction(report_id="report-1", page_number=53, text="供应商尽调 整改闭环。"),
        PageExtraction(report_id="report-1", page_number=54, text="供应商行为准则 供应商培训与赋能。"),
        PageExtraction(report_id="report-1", page_number=56, text="治理章节封面。"),
        PageExtraction(report_id="report-1", page_number=57, text="合规风险排查 政策制度。"),
        PageExtraction(report_id="report-1", page_number=59, text="阳光热线 举报电话 举报邮箱 调查处理 举报人保护。"),
        PageExtraction(
            report_id="report-1",
            page_number=72,
            text=(
                "2-22 关于可持续发展战略的声明 董事长致辞 3 ESG合作网络拓展 8 CSO致辞 4\n"
                "2-23 政策承诺 概述：责任治理 永续发展 9 环境：远瞩绿能 智护地球 15 人：以人为本 知行合一 30\n"
                "2-24 融合政策承诺 概述：责任治理 永续发展 9 环境：远瞩绿能 智护地球 15\n"
                "2-25 补救负面影响的程序 质量为基，客户至上 45\n"
                "2-26 寻求建议和提出关切的机制 概述：责任治理 永续发展 9 环境 15 人 30 产品 44 治理 55 202\n"
                "2-28 协会的成员资格 关于远景能源 5\n"
                "2-29 利益相关方参与的方法 概述：责任治理 永续发展 9\n"
                "3-1 确定重大议题的过程 重要性评估 14 治理 55"
            ),
        ),
    ]
    from src.domain.models import DisclosureTask

    tasks = [
        DisclosureTask(task_id="task-2-22-a", run_id="run-1", report_id="report-1", standard_id="GRI 2", standard_version="2021", disclosure_id="GRI 2-22", requirement_id="GRI 2-22-a", requirement_text="statement on sustainable development strategy;", keywords=["可持续发展"]),
        DisclosureTask(task_id="task-2-23-a", run_id="run-1", report_id="report-1", standard_id="GRI 2", standard_version="2021", disclosure_id="GRI 2-23", requirement_id="GRI 2-23-a", requirement_text="policy commitments;", keywords=["政策承诺"]),
        DisclosureTask(task_id="task-2-24-a", run_id="run-1", report_id="report-1", standard_id="GRI 2", standard_version="2021", disclosure_id="GRI 2-24", requirement_id="GRI 2-24-a", requirement_text="embed policy commitments;", keywords=["政策制度"]),
        DisclosureTask(task_id="task-2-25-a", run_id="run-1", report_id="report-1", standard_id="GRI 2", standard_version="2021", disclosure_id="GRI 2-25", requirement_id="GRI 2-25-a", requirement_text="remediate negative impacts;", keywords=["整改"]),
        DisclosureTask(task_id="task-2-26-a", run_id="run-1", report_id="report-1", standard_id="GRI 2", standard_version="2021", disclosure_id="GRI 2-26", requirement_id="GRI 2-26-a", requirement_text="mechanisms for advice and concerns;", keywords=["阳光热线"]),
        DisclosureTask(task_id="task-2-28-a", run_id="run-1", report_id="report-1", standard_id="GRI 2", standard_version="2021", disclosure_id="GRI 2-28", requirement_id="GRI 2-28-a", requirement_text="membership associations;", keywords=["UNGC"]),
        DisclosureTask(task_id="task-2-29-a", run_id="run-1", report_id="report-1", standard_id="GRI 2", standard_version="2021", disclosure_id="GRI 2-29", requirement_id="GRI 2-29-a", requirement_text="stakeholder engagement;", keywords=["利益相关方"]),
        DisclosureTask(task_id="task-3-1-a", run_id="run-1", report_id="report-1", standard_id="GRI 3", standard_version="2021", disclosure_id="GRI 3-1", requirement_id="GRI 3-1-a", requirement_text="process to determine material topics;", keywords=["重要性评估"]),
    ]

    enriched = workflow._attach_report_index_candidates(pages, tasks)

    assert enriched[0].candidate_pdf_pages == [4, 5]
    assert enriched[1].candidate_pdf_pages == [9, 11, 32, 54, 57, 59]
    assert enriched[2].candidate_pdf_pages == [11, 13, 32, 53, 54, 57, 59]
    assert enriched[3].candidate_pdf_pages == [32, 53, 59]
    assert enriched[4].candidate_pdf_pages == [33, 59]
    assert 203 not in enriched[4].candidate_pdf_pages
    assert enriched[5].candidate_pdf_pages == [9]
    assert enriched[6].candidate_pdf_pages == [14, 15]
    assert enriched[7].candidate_pdf_pages == [14, 15]
