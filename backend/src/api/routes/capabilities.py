from fastapi import APIRouter

from src.api.schemas import OcrCapabilityResponse
from src.config.settings import get_settings
from src.services.ocr_capability import inspect_ocr_capability


router = APIRouter(prefix="/api/capabilities", tags=["capabilities"])


@router.get("/ocr", response_model=OcrCapabilityResponse)
def ocr_capability() -> OcrCapabilityResponse:
    capability = inspect_ocr_capability(get_settings())
    return OcrCapabilityResponse(
        enabled=capability.enabled,
        available=capability.available,
        dependency_codes=list(capability.dependency_codes),
        language=capability.language,
        max_pages=capability.max_pages,
    )
