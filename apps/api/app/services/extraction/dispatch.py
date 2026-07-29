from app.services.extraction.base import ExtractedPage, ExtractionResult, ExtractionError
from app.services.extraction.docx_extract import extract_docx
from app.services.extraction.hwp_legacy import extract_hwp_legacy
from app.services.extraction.hwpx import extract_hwpx
from app.services.extraction.image_ocr import extract_image
from app.services.extraction.pdf import extract_pdf


def extract_text_by_extension(extension: str, content: bytes) -> ExtractionResult:
    extension = extension.lower()
    if extension == "pdf":
        return extract_pdf(content)
    if extension in ("jpg", "jpeg", "png"):
        return extract_image(content)
    if extension == "docx":
        return extract_docx(content)
    if extension == "hwpx":
        return extract_hwpx(content)
    if extension == "hwp":
        return extract_hwp_legacy(content)
    if extension == "txt":
        text = content.decode("utf-8", errors="ignore")
        return ExtractionResult(pages=[ExtractedPage(page_number=1, text=text, ocr_used=False)])
    raise ExtractionError(f"지원하지 않는 파일 형식입니다: {extension}")
