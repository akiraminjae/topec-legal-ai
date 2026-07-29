"""Best-effort extraction for legacy binary HWP (v5) files.

HWP v5's binary format is only partially documented. We attempt to open it as an
OLE compound file, locate BodyText/SectionN streams, zlib-inflate them, and pull
readable Hangul/ASCII text out of the record stream. This is a heuristic parser:
if any step fails or yields no usable text, we raise ExtractionError with a clear
message rather than inventing content, per the "no fabricated content" principle.
"""
import io
import re
import zlib

from app.services.extraction.base import ExtractedPage, ExtractionResult, ExtractionError

_TEXT_CHAR_RE = re.compile(r"[가-힣A-Za-z0-9 .,()%~\-·\n]{2,}")


def extract_hwp_legacy(content: bytes) -> ExtractionResult:
    try:
        import olefile
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError(
            "구형 HWP 문서의 자동 분석에 실패했습니다. PDF 또는 HWPX 형식으로 변환 후 다시 업로드해 주세요."
        ) from exc

    try:
        ole = olefile.OleFileIO(io.BytesIO(content))
    except Exception as exc:
        raise ExtractionError(
            "구형 HWP 문서의 자동 분석에 실패했습니다. PDF 또는 HWPX 형식으로 변환 후 다시 업로드해 주세요."
        ) from exc

    try:
        section_streams = sorted(
            [s for s in ole.listdir() if len(s) == 2 and s[0] == "BodyText" and s[1].startswith("Section")],
            key=lambda s: s[1],
        )
        if not section_streams:
            raise ExtractionError(
                "구형 HWP 문서의 자동 분석에 실패했습니다. PDF 또는 HWPX 형식으로 변환 후 다시 업로드해 주세요."
            )

        pages: list[ExtractedPage] = []
        any_text = False
        for i, stream_path in enumerate(section_streams, start=1):
            raw = ole.openstream(stream_path).read()
            try:
                data = zlib.decompress(raw, -15)
            except zlib.error:
                data = raw  # some sections may already be uncompressed

            decoded = data.decode("utf-16-le", errors="ignore")
            matches = _TEXT_CHAR_RE.findall(decoded)
            text = "\n".join(m.strip() for m in matches if m.strip())
            if text:
                any_text = True
            pages.append(ExtractedPage(page_number=i, text=text, ocr_used=False))

        if not any_text:
            raise ExtractionError(
                "구형 HWP 문서의 자동 분석에 실패했습니다. PDF 또는 HWPX 형식으로 변환 후 다시 업로드해 주세요."
            )

        return ExtractionResult(
            pages=pages,
            warning="구형 HWP 문서는 자동 추출 정확도가 낮을 수 있습니다. 반드시 원문과 대조해 주세요.",
        )
    finally:
        ole.close()
