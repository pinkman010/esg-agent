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
    def __init__(self):
        self.calls = []

    def parse_pdf(self, pdf_path, report_id, source_file_hash, ocr_pages=None):
        self.calls.append(ocr_pages)
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


class LowTextParser:
    def __init__(self):
        self.calls = []

    def parse_pdf(self, pdf_path, report_id, source_file_hash, ocr_pages=None):
        self.calls.append(ocr_pages)
        if ocr_pages is None:
            return ParsedDocument(
                report_id=report_id,
                page_count=3,
                pages=[
                    PageExtraction(report_id=report_id, page_number=1, text="Normal disclosure text."),
                    PageExtraction(report_id=report_id, page_number=2, text="", quality_flags=["low_text_density"]),
                    PageExtraction(report_id=report_id, page_number=3, text="", quality_flags=["scanned"]),
                ],
                chunks=[],
                metadata={},
                outline=[],
            )
        return ParsedDocument(
            report_id=report_id,
            page_count=3,
            pages=[],
            chunks=[],
            metadata={},
            outline=[],
        )


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


def test_single_report_workflow_does_not_request_ocr_by_default(repo_session):
    repo = Repository(repo_session)
    seed_report(repo)
    parser = FakeParser()
    workflow = SingleReportWorkflow(repo, parser, FakeAdapter(), DisclosureAgent())

    run = workflow.run("report-1", Path("report.pdf"), "hash-1", confirm_llm=False)

    assert run.status is RunStatus.COMPLETED
    assert parser.calls == [None]


def test_single_report_workflow_passes_explicit_ocr_pages(repo_session):
    repo = Repository(repo_session)
    seed_report(repo)
    parser = FakeParser()
    workflow = SingleReportWorkflow(repo, parser, FakeAdapter(), DisclosureAgent())

    run = workflow.run("report-1", Path("report.pdf"), "hash-1", confirm_llm=False, enable_ocr=True, ocr_pages=[77])

    assert run.status is RunStatus.COMPLETED
    assert parser.calls == [[77]]


def test_single_report_workflow_selects_low_quality_pages_when_ocr_pages_are_empty(repo_session):
    repo = Repository(repo_session)
    seed_report(repo)
    parser = LowTextParser()
    workflow = SingleReportWorkflow(repo, parser, FakeAdapter(), DisclosureAgent(), ocr_max_pages=1)

    run = workflow.run("report-1", Path("report.pdf"), "hash-1", confirm_llm=False, enable_ocr=True)

    assert run.status is RunStatus.COMPLETED
    assert parser.calls == [None, [2]]


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


def test_single_report_workflow_rejects_product_service_section_for_customer_privacy_complaints(tmp_path):
    pack_path = tmp_path / "gri_requirement_pack.json"
    pack_path.write_text(json.dumps({"requirements": []}), encoding="utf-8")
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "report_id": "goldwind_2024",
                "company_name": "Goldwind",
                "report_year": 2024,
                "pdf_file": "goldwind.pdf",
                "total_pdf_pages": 52,
                "page_numbering": {
                    "report_index_pdf_page": 50,
                    "report_index_report_page": 96,
                    "total_pdf_pages": 52,
                },
                "gri_index": {"pdf_pages": [50, 51]},
                "sections": [
                    {
                        "name": "产品服务与研发创新",
                        "pdf_pages": [13, 14, 15],
                        "report_pages": [22, 24, 26],
                        "terms": ["产品服务与研发创新", "产品质量", "产品安全", "客户", "服务"],
                    }
                ],
                "index_note_pages": [],
                "assurance_pages": [],
                "requirement_routes": {},
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
        report_profile_path=profile_path,
    )
    from src.domain.models import DisclosureTask

    task = DisclosureTask(
        task_id="task-418-1-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        standard_version="2016",
        disclosure_id="GRI 418-1",
        requirement_id="GRI 418-1-a",
        requirement_text="customer privacy complaints",
        keywords=["customer", "privacy", "complaints"],
    )

    enriched = workflow._attach_report_index_candidates([], [task])

    assert enriched[0].candidate_pdf_pages == []
    assert enriched[0].candidate_report_pages == []
    assert enriched[0].candidate_page_source == "requirement_contract"


def test_single_report_workflow_prefers_requirement_override_over_profile_section_route(tmp_path):
    pack_path = tmp_path / "gri_requirement_pack.json"
    pack_path.write_text(json.dumps({"requirements": []}), encoding="utf-8")
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "report_id": "envision_2024",
                "company_name": "Envision",
                "report_year": 2024,
                "pdf_file": "envision.pdf",
                "total_pdf_pages": 78,
                "page_numbering": {
                    "report_index_pdf_page": 71,
                    "report_index_report_page": 70,
                    "total_pdf_pages": 78,
                },
                "gri_index": {"pdf_pages": [71, 72]},
                "sections": [
                    {
                        "name": "stakeholder_engagement",
                        "pdf_pages": [14, 15],
                        "report_pages": [13, 14],
                        "terms": ["利益相关方"],
                    }
                ],
                "index_note_pages": [],
                "assurance_pages": [],
                "requirement_routes": {},
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
        report_profile_path=profile_path,
    )
    from src.domain.models import DisclosureTask

    tasks = [
        DisclosureTask(
            task_id="task-203-2-b",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 203",
            standard_version="2016",
            disclosure_id="GRI 203-2",
            requirement_id="GRI 203-2-b",
            requirement_text="significant indirect economic impacts.",
            keywords=["利益相关方", "SDGs"],
        ),
        DisclosureTask(
            task_id="task-207-3-a",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 207",
            standard_version="2019",
            disclosure_id="GRI 207-3",
            requirement_id="GRI 207-3-a",
            requirement_text="stakeholder concerns related to tax.",
            keywords=["利益相关方"],
        ),
        DisclosureTask(
            task_id="task-202-2-a",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 202",
            standard_version="2016",
            disclosure_id="GRI 202-2",
            requirement_id="GRI 202-2-a",
            requirement_text="proportion of senior management hired from the local community.",
            keywords=["利益相关方"],
        ),
    ]

    enriched = workflow._attach_report_index_candidates([], tasks)

    assert enriched[0].candidate_pdf_pages == [12, 42, 43, 44, 69]
    assert enriched[0].candidate_page_source == "requirement_contract"
    assert enriched[1].candidate_pdf_pages == [57]
    assert enriched[1].candidate_page_source == "requirement_contract"
    assert enriched[2].candidate_pdf_pages == [72]
    assert enriched[2].candidate_page_source == "requirement_contract"


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


def test_single_report_workflow_supplements_candidate_pages_for_topic_specific_200_rules(tmp_path):
    pack_path = tmp_path / "gri_requirement_pack.json"
    pack_path.write_text(
        json.dumps(
            {
                "requirements": [
                    {"canonical_disclosure_id": "201-2", "report_index_pdf_page": 72, "report_index_report_page": 71},
                    {"canonical_disclosure_id": "201-3", "report_index_pdf_page": 72, "report_index_report_page": 71},
                    {"canonical_disclosure_id": "202-1", "report_index_pdf_page": 72, "report_index_report_page": 71},
                    {"canonical_disclosure_id": "203-1", "report_index_pdf_page": 72, "report_index_report_page": 71},
                    {"canonical_disclosure_id": "203-2", "report_index_pdf_page": 72, "report_index_report_page": 71},
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
        PageExtraction(report_id="report-1", page_number=4, text="董事长致辞 绿色能源项目 产业升级。"),
        PageExtraction(report_id="report-1", page_number=12, text="UN SDGs 千乡万村驭风行动。"),
        PageExtraction(report_id="report-1", page_number=17, text="气候风险 实体风险 转型风险 财务影响。"),
        PageExtraction(report_id="report-1", page_number=18, text="气候机遇 市场风险 法律风险 绿色投融资。"),
        PageExtraction(report_id="report-1", page_number=19, text="气候风险管理流程 应对措施。"),
        PageExtraction(report_id="report-1", page_number=31, text="人章节封面 景行公益 厚植人文。"),
        PageExtraction(report_id="report-1", page_number=32, text="关怀员工 幸福职场 员工权益 DEI。"),
        PageExtraction(report_id="report-1", page_number=34, text="薪酬福利 社会保障 医疗保险 公积金。"),
        PageExtraction(report_id="report-1", page_number=42, text="携手社区 贡献社会 乡村振兴工程。"),
        PageExtraction(report_id="report-1", page_number=43, text="沙特风电装备合资公司 印度森林保护 老挝项目捐赠。"),
        PageExtraction(report_id="report-1", page_number=44, text="清华可持续基金 西藏地震援助。"),
        PageExtraction(report_id="report-1", page_number=69, text="UN SDGs 乡村振兴 一带一路。"),
        PageExtraction(
            report_id="report-1",
            page_number=72,
            text=(
                "201-2 气候变化带来的财务影响以及其他风险和机遇 气候先锋，创新能源 16\n"
                "201-3 固定福利计划义务和其他退休计划 关怀员工，幸福职场 31\n"
                "202-1 按性别的标准起薪水平工资与当地最低工资之比 概述：责任治理 永续发展 10\n"
                "203-1 基础设施投资和支持性服务 人：景行公益 厚植人文 30\n"
                "203-2 重大间接经济影响 人：景行公益 厚植人文 30"
            ),
        ),
    ]
    from src.domain.models import DisclosureTask

    tasks = [
        DisclosureTask(task_id="task-201-2-a", run_id="run-1", report_id="report-1", standard_id="GRI 201", standard_version="2016", disclosure_id="GRI 201-2", requirement_id="GRI 201-2-a", requirement_text="climate financial implications.", keywords=["气候风险"]),
        DisclosureTask(task_id="task-201-3-d", run_id="run-1", report_id="report-1", standard_id="GRI 201", standard_version="2016", disclosure_id="GRI 201-3", requirement_id="GRI 201-3-d", requirement_text="contribution percentages.", keywords=["福利"]),
        DisclosureTask(task_id="task-202-1-a", run_id="run-1", report_id="report-1", standard_id="GRI 202", standard_version="2016", disclosure_id="GRI 202-1", requirement_id="GRI 202-1-a", requirement_text="entry wage compared to minimum wage.", keywords=["维生工资"]),
        DisclosureTask(task_id="task-203-1-a", run_id="run-1", report_id="report-1", standard_id="GRI 203", standard_version="2016", disclosure_id="GRI 203-1", requirement_id="GRI 203-1-a", requirement_text="infrastructure investments.", keywords=["社区"]),
        DisclosureTask(task_id="task-203-2-b", run_id="run-1", report_id="report-1", standard_id="GRI 203", standard_version="2016", disclosure_id="GRI 203-2", requirement_id="GRI 203-2-b", requirement_text="significant indirect economic impacts.", keywords=["SDGs"]),
    ]

    enriched = workflow._attach_report_index_candidates(pages, tasks)

    assert enriched[0].candidate_pdf_pages == [17, 18, 19]
    assert enriched[1].candidate_pdf_pages == []
    assert enriched[2].candidate_pdf_pages == []
    assert enriched[3].candidate_pdf_pages == [4, 12, 42, 43, 44]
    assert enriched[4].candidate_pdf_pages == [12, 42, 43, 44, 69]


def test_single_report_workflow_supplements_candidate_pages_for_topic_specific_250_rules(tmp_path):
    pack_path = tmp_path / "gri_requirement_pack.json"
    pack_path.write_text(
        json.dumps(
            {
                "requirements": [
                    {"canonical_disclosure_id": "204-1", "report_index_pdf_page": 73, "report_index_report_page": 72},
                    {"canonical_disclosure_id": "205-1", "report_index_pdf_page": 73, "report_index_report_page": 72},
                    {"canonical_disclosure_id": "205-2", "report_index_pdf_page": 73, "report_index_report_page": 72},
                    {"canonical_disclosure_id": "205-3", "report_index_pdf_page": 73, "report_index_report_page": 72},
                    {"canonical_disclosure_id": "206-1", "report_index_pdf_page": 73, "report_index_report_page": 72},
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
        PageExtraction(report_id="report-1", page_number=54, text="供应商阳光协议 可持续采购章程 供应商行为准则。"),
        PageExtraction(report_id="report-1", page_number=56, text="治理章节封面 源正风清 行稳致远。"),
        PageExtraction(report_id="report-1", page_number=57, text="合规制度 商业道德。"),
        PageExtraction(report_id="report-1", page_number=58, text="贪污贿赂风险评估 内部审计 外部商业道德审计 第三方反腐败尽调。"),
        PageExtraction(report_id="report-1", page_number=59, text="阳光热线 举报机制 合规培训 利益冲突申报。"),
        PageExtraction(report_id="report-1", page_number=68, text="贪污腐败事件数量 员工因腐败被开除或受到处分的事件数量 反竞争行为事件数量。"),
        PageExtraction(
            report_id="report-1",
            page_number=73,
            text=(
                "204-1 向当地供应商采购的支出比例 因商业保密限制从略披露\n"
                "205-1 已进行腐败风险评估的运营点 治理：源正风清 行稳致远 55\n"
                "205-2 反腐败政策和程序的传达及培训 治理：源正风清 行稳致远 55\n"
                "205-3 经确认的腐败事件和采取的行动 治理：源正风清 行稳致远 55\n"
                "206-1 针对反竞争行为、反托拉斯和反垄断实践的法律诉讼 治理：源正风清 行稳致远 55"
            ),
        ),
    ]
    from src.domain.models import DisclosureTask

    tasks = [
        DisclosureTask(task_id="task-204-1-a", run_id="run-1", report_id="report-1", standard_id="GRI 204", standard_version="2016", disclosure_id="GRI 204-1", requirement_id="GRI 204-1-a", requirement_text="local supplier spending.", keywords=["从略披露"]),
        DisclosureTask(task_id="task-205-1-a", run_id="run-1", report_id="report-1", standard_id="GRI 205", standard_version="2016", disclosure_id="GRI 205-1", requirement_id="GRI 205-1-a", requirement_text="operations assessed for corruption risks.", keywords=["风险评估"]),
        DisclosureTask(task_id="task-205-2-b", run_id="run-1", report_id="report-1", standard_id="GRI 205", standard_version="2016", disclosure_id="GRI 205-2", requirement_id="GRI 205-2-b", requirement_text="employees trained on anti-corruption.", keywords=["合规培训"]),
        DisclosureTask(task_id="task-205-2-c", run_id="run-1", report_id="report-1", standard_id="GRI 205", standard_version="2016", disclosure_id="GRI 205-2", requirement_id="GRI 205-2-c", requirement_text="business partners communicated anti-corruption procedures.", keywords=["供应商阳光协议"]),
        DisclosureTask(task_id="task-205-3-b", run_id="run-1", report_id="report-1", standard_id="GRI 205", standard_version="2016", disclosure_id="GRI 205-3", requirement_id="GRI 205-3-b", requirement_text="employees disciplined for corruption.", keywords=["员工因腐败"]),
        DisclosureTask(task_id="task-206-1-a", run_id="run-1", report_id="report-1", standard_id="GRI 206", standard_version="2016", disclosure_id="GRI 206-1", requirement_id="GRI 206-1-a", requirement_text="anti-competitive legal actions.", keywords=["反竞争行为"]),
    ]

    enriched = workflow._attach_report_index_candidates(pages, tasks)

    assert enriched[0].candidate_pdf_pages == [73]
    assert enriched[1].candidate_pdf_pages == [58, 68]
    assert enriched[2].candidate_pdf_pages == [59, 68]
    assert enriched[3].candidate_pdf_pages == [54, 58]
    assert enriched[4].candidate_pdf_pages == [68]
    assert enriched[5].candidate_pdf_pages == [68]


def test_single_report_workflow_supplements_candidate_pages_for_tax_and_energy_250_rules(tmp_path):
    pack_path = tmp_path / "gri_requirement_pack.json"
    pack_path.write_text(
        json.dumps(
            {
                "requirements": [
                    {"canonical_disclosure_id": "207-1", "report_index_pdf_page": 73, "report_index_report_page": 72},
                    {"canonical_disclosure_id": "207-2", "report_index_pdf_page": 73, "report_index_report_page": 72},
                    {"canonical_disclosure_id": "207-3", "report_index_pdf_page": 73, "report_index_report_page": 72},
                    {"canonical_disclosure_id": "207-4", "report_index_pdf_page": 73, "report_index_report_page": 72},
                    {"canonical_disclosure_id": "302-1", "report_index_pdf_page": 73, "report_index_report_page": 72},
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
        PageExtraction(report_id="report-1", page_number=57, text="财务合规与安全部门 税务治理 财务风险管理 税务管理标准 税法要求 税收协定 利益相关方对税务管理的期待。"),
        PageExtraction(report_id="report-1", page_number=63, text="不可再生能源燃料消耗量 不可再生能源消耗总量(kWh) 电力消耗总量(kWh) 办公用电总量(kWh) 绿色电力使用总量(kWh)。"),
        PageExtraction(
            report_id="report-1",
            page_number=73,
            text=(
                "207-1 税务方针 治理：源正风清 行稳致远 56\n"
                "207-2 税务治理、控制和风险管理 治理：源正风清 行稳致远 56\n"
                "207-3 与税务相关的利益相关方参与及关切管理 治理：源正风清 行稳致远 56\n"
                "207-4 国别报告 因商业保密限制从略披露\n"
                "302-1 组织内部的能源消耗 附录一：关键绩效数据表 62"
            ),
        ),
    ]
    from src.domain.models import DisclosureTask

    tasks = [
        DisclosureTask(task_id="task-207-1-a", run_id="run-1", report_id="report-1", standard_id="GRI 207", standard_version="2019", disclosure_id="GRI 207-1", requirement_id="GRI 207-1-a", requirement_text="approach to tax.", keywords=["税务治理"]),
        DisclosureTask(task_id="task-207-1-a-iii", run_id="run-1", report_id="report-1", standard_id="GRI 207", standard_version="2019", disclosure_id="GRI 207-1", requirement_id="GRI 207-1-a-iii", requirement_text="regulatory compliance.", keywords=["税收协定"]),
        DisclosureTask(task_id="task-207-2-a", run_id="run-1", report_id="report-1", standard_id="GRI 207", standard_version="2019", disclosure_id="GRI 207-2", requirement_id="GRI 207-2-a", requirement_text="tax governance and control.", keywords=["财务合规"]),
        DisclosureTask(task_id="task-207-3-a", run_id="run-1", report_id="report-1", standard_id="GRI 207", standard_version="2019", disclosure_id="GRI 207-3", requirement_id="GRI 207-3-a", requirement_text="stakeholder concerns related to tax.", keywords=["利益相关方"]),
        DisclosureTask(task_id="task-207-4-b-x", run_id="run-1", report_id="report-1", standard_id="GRI 207", standard_version="2019", disclosure_id="GRI 207-4", requirement_id="GRI 207-4-b-x", requirement_text="country-by-country reporting.", keywords=["从略披露"]),
        DisclosureTask(task_id="task-302-1-a", run_id="run-1", report_id="report-1", standard_id="GRI 302", standard_version="2016", disclosure_id="GRI 302-1", requirement_id="GRI 302-1-a", requirement_text="non-renewable fuel consumption.", keywords=["不可再生能源"]),
        DisclosureTask(task_id="task-302-1-c", run_id="run-1", report_id="report-1", standard_id="GRI 302", standard_version="2016", disclosure_id="GRI 302-1", requirement_id="GRI 302-1-c", requirement_text="electricity consumption.", keywords=["电力消耗"]),
    ]

    enriched = workflow._attach_report_index_candidates(pages, tasks)

    assert enriched[0].candidate_pdf_pages == [57]
    assert enriched[1].candidate_pdf_pages == [57]
    assert enriched[2].candidate_pdf_pages == [57]
    assert enriched[3].candidate_pdf_pages == [57]
    assert enriched[4].candidate_pdf_pages == [73]
    assert enriched[5].candidate_pdf_pages == [63]
    assert enriched[6].candidate_pdf_pages == [63]


def test_single_report_workflow_supplements_candidate_pages_for_energy_and_water_300_rules(tmp_path):
    pack_path = tmp_path / "gri_requirement_pack.json"
    pack_path.write_text(
        json.dumps(
            {
                "requirements": [
                    {"canonical_disclosure_id": "302-1", "report_index_pdf_page": 73, "report_index_report_page": 72},
                    {"canonical_disclosure_id": "302-4", "report_index_pdf_page": 73, "report_index_report_page": 72},
                    {"canonical_disclosure_id": "303-1", "report_index_pdf_page": 73, "report_index_report_page": 72},
                    {"canonical_disclosure_id": "303-2", "report_index_pdf_page": 73, "report_index_report_page": 72},
                    {"canonical_disclosure_id": "303-3", "report_index_pdf_page": 73, "report_index_report_page": 72},
                    {"canonical_disclosure_id": "303-4", "report_index_pdf_page": 73, "report_index_report_page": 72},
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
        PageExtraction(report_id="report-1", page_number=16, text="水资源目标 行动路径。"),
        PageExtraction(report_id="report-1", page_number=22, text="废水分类收集 分质处理 排放水质达到法规限值。"),
        PageExtraction(report_id="report-1", page_number=23, text="节能改造 年节约用电约 9360 kWh。"),
        PageExtraction(report_id="report-1", page_number=25, text="水资源使用 WWF Water Risk Filter 水资源风险评估 取水 排水 耗水 循环水 雨水替代。"),
        PageExtraction(report_id="report-1", page_number=63, text="能源使用总量 节能措施促成节电量 总取水量 地表水总量 地下水总量 第三方取水总量 高水风险区域取水 总排水量 淡水排水量 其他水排水量。"),
        PageExtraction(
            report_id="report-1",
            page_number=73,
            text=(
                "302-1 组织内部的能源消耗 附录一：关键绩效数据表 62\n"
                "302-4 减少能源消耗 环境：远瞩绿能 智护地球 22 附录一：关键绩效数据表 62\n"
                "303-1 组织与水作为共有资源的相互影响 环境：远瞩绿能 智护地球 24\n"
                "303-2 管理与排水相关的影响 环境：远瞩绿能 智护地球 21\n"
                "303-3 取水 附录一：关键绩效数据表 62\n"
                "303-4 排水 附录一：关键绩效数据表 62"
            ),
        ),
    ]
    from src.domain.models import DisclosureTask

    tasks = [
        DisclosureTask(task_id="task-302-1-e", run_id="run-1", report_id="report-1", standard_id="GRI 302", standard_version="2016", disclosure_id="GRI 302-1", requirement_id="GRI 302-1-e", requirement_text="total energy consumption.", keywords=["能源使用总量"]),
        DisclosureTask(task_id="task-302-4-a", run_id="run-1", report_id="report-1", standard_id="GRI 302", standard_version="2016", disclosure_id="GRI 302-4", requirement_id="GRI 302-4-a", requirement_text="energy reductions.", keywords=["节电量"]),
        DisclosureTask(task_id="task-303-1-a", run_id="run-1", report_id="report-1", standard_id="GRI 303", standard_version="2018", disclosure_id="GRI 303-1", requirement_id="GRI 303-1-a", requirement_text="interactions with water.", keywords=["水资源"]),
        DisclosureTask(task_id="task-303-1-d", run_id="run-1", report_id="report-1", standard_id="GRI 303", standard_version="2018", disclosure_id="GRI 303-1", requirement_id="GRI 303-1-d", requirement_text="water-related goals.", keywords=["目标"]),
        DisclosureTask(task_id="task-303-2-a", run_id="run-1", report_id="report-1", standard_id="GRI 303", standard_version="2018", disclosure_id="GRI 303-2", requirement_id="GRI 303-2-a", requirement_text="effluent discharge standards.", keywords=["废水"]),
        DisclosureTask(task_id="task-303-3-a", run_id="run-1", report_id="report-1", standard_id="GRI 303", standard_version="2018", disclosure_id="GRI 303-3", requirement_id="GRI 303-3-a", requirement_text="water withdrawal.", keywords=["取水"]),
        DisclosureTask(task_id="task-303-4-a", run_id="run-1", report_id="report-1", standard_id="GRI 303", standard_version="2018", disclosure_id="GRI 303-4", requirement_id="GRI 303-4-a", requirement_text="water discharge.", keywords=["排水"]),
    ]

    enriched = workflow._attach_report_index_candidates(pages, tasks)

    assert enriched[0].candidate_pdf_pages == [63]
    assert enriched[1].candidate_pdf_pages == [23, 63]
    assert enriched[2].candidate_pdf_pages == [25, 63]
    assert enriched[3].candidate_pdf_pages == [16, 25]
    assert enriched[4].candidate_pdf_pages == [22]
    assert enriched[5].candidate_pdf_pages == [25, 63]
    assert enriched[6].candidate_pdf_pages == [22, 63]


def test_single_report_workflow_supplements_candidate_pages_for_ghg_350_rules(tmp_path):
    pack_path = tmp_path / "gri_requirement_pack.json"
    pack_path.write_text(
        json.dumps(
            {
                "requirements": [
                    {"canonical_disclosure_id": "305-1", "report_index_pdf_page": 74, "report_index_report_page": 73},
                    {"canonical_disclosure_id": "305-2", "report_index_pdf_page": 74, "report_index_report_page": 73},
                    {"canonical_disclosure_id": "304-4", "report_index_pdf_page": 74, "report_index_report_page": 73},
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
        PageExtraction(report_id="report-1", page_number=3, text="TCFD 气候相关财务信息披露工作组。"),
        PageExtraction(report_id="report-1", page_number=20, text="范围一排放量 范围二（基于位置）57,897.05 tCO2e 范围二（基于市场）绿色电力。"),
        PageExtraction(report_id="report-1", page_number=63, text="范围一温室气体排放量 范围二（基于位置） 范围二（基于市场） 温室气体 KPI。"),
        PageExtraction(report_id="report-1", page_number=64, text="温室气体核算方法 排放因子 全球变暖潜势 GWP。"),
        PageExtraction(report_id="report-1", page_number=74, text="304-4 受运营影响的栖息地中已被列入 远景能源因不适用而从略披露 /\n305-1 直接温室气体排放 附录一：关键绩效数据表 62\n305-2 能源间接温室气体排放 附录一：关键绩效数据表 62"),
    ]
    from src.domain.models import DisclosureTask

    tasks = [
        DisclosureTask(task_id="task-305-1-a", run_id="run-1", report_id="report-1", standard_id="GRI 305", standard_version="2016", disclosure_id="GRI 305-1", requirement_id="GRI 305-1-a", requirement_text="scope 1 emissions.", keywords=["范围一"]),
        DisclosureTask(task_id="task-305-1-e", run_id="run-1", report_id="report-1", standard_id="GRI 305", standard_version="2016", disclosure_id="GRI 305-1", requirement_id="GRI 305-1-e", requirement_text="emission factors.", keywords=["排放因子"]),
        DisclosureTask(task_id="task-305-1-g", run_id="run-1", report_id="report-1", standard_id="GRI 305", standard_version="2016", disclosure_id="GRI 305-1", requirement_id="GRI 305-1-g", requirement_text="standards and methodologies.", keywords=["核算方法"]),
        DisclosureTask(task_id="task-305-1-d", run_id="run-1", report_id="report-1", standard_id="GRI 305", standard_version="2016", disclosure_id="GRI 305-1", requirement_id="GRI 305-1-d", requirement_text="base year.", keywords=["基准年"]),
        DisclosureTask(task_id="task-305-2-a", run_id="run-1", report_id="report-1", standard_id="GRI 305", standard_version="2016", disclosure_id="GRI 305-2", requirement_id="GRI 305-2-a", requirement_text="location-based scope 2.", keywords=["范围二（基于位置）"]),
        DisclosureTask(task_id="task-305-2-b", run_id="run-1", report_id="report-1", standard_id="GRI 305", standard_version="2016", disclosure_id="GRI 305-2", requirement_id="GRI 305-2-b", requirement_text="market-based scope 2.", keywords=["范围二（基于市场）"]),
        DisclosureTask(task_id="task-305-2-c", run_id="run-1", report_id="report-1", standard_id="GRI 305", standard_version="2016", disclosure_id="GRI 305-2", requirement_id="GRI 305-2-c", requirement_text="gases included.", keywords=["温室气体种类"]),
        DisclosureTask(task_id="task-304-4-a", run_id="run-1", report_id="report-1", standard_id="GRI 304", standard_version="2016", disclosure_id="GRI 304-4", requirement_id="GRI 304-4-a", requirement_text="IUCN species.", keywords=["从略披露"]),
    ]

    enriched = workflow._attach_report_index_candidates(pages, tasks)

    assert enriched[0].candidate_pdf_pages == [20, 63]
    assert enriched[1].candidate_pdf_pages == [64]
    assert enriched[2].candidate_pdf_pages == [64]
    assert enriched[3].candidate_pdf_pages == []
    assert enriched[4].candidate_pdf_pages == [20, 63]
    assert enriched[5].candidate_pdf_pages == [20, 63]
    assert enriched[6].candidate_pdf_pages == []
    assert enriched[7].candidate_pdf_pages == [74]


def test_single_report_workflow_uses_contract_candidates_without_report_index_entry(tmp_path):
    pack_path = tmp_path / "pack.json"
    pack_path.write_text(
        json.dumps(
            {
                "requirements": [
                    {"canonical_disclosure_id": "2-1", "report_index_pdf_page": 71, "report_index_report_page": 70}
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
        PageExtraction(report_id="report-1", page_number=33, text="员工性别结构"),
        PageExtraction(report_id="report-1", page_number=65, text="员工性别结构 管理层年龄"),
        PageExtraction(report_id="report-1", page_number=66, text="同级别女性员工平均总时薪占男性员工平均总时薪的 100%"),
    ]
    from src.domain.models import DisclosureTask

    tasks = [
        DisclosureTask(
            task_id="task-405-2-a",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 405",
            standard_version="2016",
            disclosure_id="GRI 405-2",
            requirement_id="GRI 405-2-a",
            requirement_text="pay ratio.",
            keywords=["女性员工平均总时薪"],
        )
    ]

    enriched = workflow._attach_report_index_candidates(pages, tasks)

    assert enriched[0].candidate_pdf_pages == [33, 65, 66]
    assert enriched[0].candidate_report_pages == [32, 64, 65]
    assert enriched[0].report_index_pdf_page == 71
    assert enriched[0].report_index_report_page == 70
    assert enriched[0].candidate_pages == [33, 65, 66]
