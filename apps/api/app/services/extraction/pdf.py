
import fitz  # PyMuPDF

from app.services.extraction.base import ExtractedPage, ExtractionResult
from app.services.extraction.image_ocr import ocr_image_bytes

MIN_TEXT_CHARS_PER_PAGE = 20  # below this, treat page as scanned and fall back to OCR


def extract_pdf(content: bytes) -> ExtractionResult:
    pages: list[ExtractedPage] = []
    doc = fitz.open(stream=content, filetype="pdf")
    try:
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if len(text) >= MIN_TEXT_CHARS_PER_PAGE:
                pages.append(ExtractedPage(page_number=i, text=text, ocr_used=False))
                continue

            # Likely a scanned page — rasterize and OCR
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            ocr_text, confidence = ocr_image_bytes(img_bytes)
            pages.append(
                ExtractedPage(page_number=i, text=ocr_text, ocr_used=True, ocr_confidence=confidence)
            )
    finally:
        doc.close()

    low_confidence_pages = [p.page_number for p in pages if p.ocr_used and (p.ocr_confidence or 0) < 50]
    warning = None
    if low_confidence_pages:
        warning = f"OCR 신뢰도가 낮은 페이지가 있습니다: {low_confidence_pages}. 원문과 대조해 주세요."

    return ExtractionResult(pages=pages, warning=warning)
