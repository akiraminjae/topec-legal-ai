import httpx

from app.core.config import get_settings

settings = get_settings()


class PdfConversionError(Exception):
    pass


def convert_docx_to_pdf(docx_bytes: bytes, filename: str) -> bytes:
    try:
        with httpx.Client(timeout=90) as client:
            response = client.post(
                f"{settings.LIBREOFFICE_BASE_URL.rstrip('/')}/convert",
                files={"file": (filename, docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            )
        response.raise_for_status()
        return response.content
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        raise PdfConversionError(f"PDF 변환 서비스 호출에 실패했습니다: {exc}") from exc
