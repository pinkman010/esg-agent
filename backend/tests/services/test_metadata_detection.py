from io import BytesIO

import src.services.metadata_detection as metadata_detection


class FakePage:
    def __init__(self, text: str):
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakeReader:
    def __init__(self, pages: list[FakePage]):
        self.pages = pages


def test_detects_company_year_and_language_from_cover_text(monkeypatch):
    pages = [
        FakePage("环境、社会及公司治理报告\n远景能源有限公司\nEnvision Energy Co., Ltd.\n2024 远景能源 ESG 报告"),
        FakePage("目录"),
    ] + [FakePage("") for _ in range(76)]
    monkeypatch.setattr(metadata_detection, "PdfReader", lambda _: FakeReader(pages))

    result = metadata_detection.detect_report_metadata("Envision Energy 2024-zh.pdf", b"pdf")

    assert result.page_count == 78
    assert result.metadata["company_name"] == "远景能源有限公司"
    assert result.metadata["report_year"] == 2024
    assert result.metadata["language"] == "zh-CN"


def test_uses_filename_for_year_and_language_when_cover_has_no_signals(monkeypatch):
    monkeypatch.setattr(metadata_detection, "PdfReader", lambda _: FakeReader([FakePage("Sustainability Report")]))

    result = metadata_detection.detect_report_metadata("report-2023-en.pdf", b"pdf")

    assert result.metadata["report_year"] == 2023
    assert result.metadata["language"] == "en"
    assert "company_name" not in result.metadata


def test_damaged_pdf_keeps_safe_filename_signals(monkeypatch):
    def fail(_: BytesIO):
        raise ValueError("damaged")

    monkeypatch.setattr(metadata_detection, "PdfReader", fail)

    result = metadata_detection.detect_report_metadata("report_2024_zh.pdf", b"damaged")

    assert result.page_count is None
    assert result.metadata["report_year"] == 2024
    assert result.metadata["language"] == "zh-CN"
    assert "company_name" not in result.metadata


def test_does_not_guess_company_without_organization_suffix(monkeypatch):
    monkeypatch.setattr(metadata_detection, "PdfReader", lambda _: FakeReader([FakePage("绿色未来\n2024 ESG报告")]))

    result = metadata_detection.detect_report_metadata("report.pdf", b"pdf")

    assert "company_name" not in result.metadata


def test_does_not_choose_when_cover_contains_multiple_company_candidates(monkeypatch):
    text = "远景能源有限公司\n示例咨询有限公司\n2024 ESG报告"
    monkeypatch.setattr(metadata_detection, "PdfReader", lambda _: FakeReader([FakePage(text)]))

    result = metadata_detection.detect_report_metadata("report-2024-zh.pdf", b"pdf")

    assert "company_name" not in result.metadata


def test_rejects_sentence_or_copyright_line_ending_with_company(monkeypatch):
    text = "版权所有，未经许可不得复制，最终解释权归发布公司\n2024 ESG报告"
    monkeypatch.setattr(metadata_detection, "PdfReader", lambda _: FakeReader([FakePage(text)]))

    result = metadata_detection.detect_report_metadata("report-2024-zh.pdf", b"pdf")

    assert "company_name" not in result.metadata


def test_filename_year_wins_when_cover_contains_multiple_years(monkeypatch):
    text = "成立于2007年\n2023年度回顾\n2024 ESG报告"
    monkeypatch.setattr(metadata_detection, "PdfReader", lambda _: FakeReader([FakePage(text)]))

    result = metadata_detection.detect_report_metadata("Company ESG Report 2024-en.pdf", b"pdf")

    assert result.metadata["report_year"] == 2024
