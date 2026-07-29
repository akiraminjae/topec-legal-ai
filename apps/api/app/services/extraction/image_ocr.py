import io

import pytesseract
from PIL import Image, ImageOps

from app.services.extraction.base import ExtractedPage, ExtractionResult


def _preprocess(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)  # rotation correction from EXIF
    image = image.convert("L")  # grayscale for better contrast/OCR
    return image


def ocr_image_bytes(content: bytes, lang: str = "kor+eng") -> tuple[str, float]:
    image = Image.open(io.BytesIO(content))
    image = _preprocess(image)
    data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)
    words = [w for w in data.get("text", []) if w.strip()]
    confidences = [float(c) for c in data.get("conf", []) if c not in ("-1", -1)]
    text = " ".join(words)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return text, round(avg_confidence, 2)


def extract_image(content: bytes) -> ExtractionResult:
    text, confidence = ocr_image_bytes(content)
    page = ExtractedPage(page_number=1, text=text, ocr_used=True, ocr_confidence=confidence)
    warning = None
    if confidence < 50:
        warning = "OCR 신뢰도가 낮습니다. 추출된 텍스트를 반드시 원문과 대조해 주세요."
    return ExtractionResult(pages=[page], warning=warning)
