OCR_ERROR_MESSAGES = {
    "ocr_feature_disabled": "OCR 功能当前未启用。",
    "ocr_page_out_of_range": "OCR 页码超出报告范围。",
    "ocr_page_limit_exceeded": "OCR 页数超过单报告处理上限。",
    "ocrmypdf_missing": "OCRmyPDF 不可用。",
    "ghostscript_missing": "Ghostscript 不可用。",
    "tesseract_missing": "Tesseract 不可用。",
    "tesseract_language_missing": "OCR 所需语言包不完整。",
    "ocr_execution_timeout": "OCR 执行超时。",
    "ocr_execution_failed": "OCR 执行失败。",
}


class OcrError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(OCR_ERROR_MESSAGES[code])


class OcrPreflightError(OcrError):
    pass


class OcrExecutionError(OcrError):
    pass
