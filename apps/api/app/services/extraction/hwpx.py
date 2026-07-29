"""HWPX extraction.

HWPX is a ZIP container of XML parts (similar in spirit to OOXML). We parse the
`Contents/section*.xml` parts and pull text out of paragraph text runs (`<hp:t>`)
and table cells, matching by local tag name so we don't depend on exact namespace
prefixes used by different Hangul word processor versions.
"""
import io
import re
import zipfile
from xml.etree import ElementTree as ET

from app.services.extraction.base import ExtractedPage, ExtractionResult, ExtractionError


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _iter_text(elem: ET.Element) -> list[str]:
    texts: list[str] = []
    for node in elem.iter():
        if _local(node.tag) == "t" and node.text:
            texts.append(node.text)
    return texts


def extract_hwpx(content: bytes) -> ExtractionResult:
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ExtractionError("HWPX 파일 구조를 인식할 수 없습니다.") from exc

    section_names = sorted(
        [n for n in zf.namelist() if re.match(r"Contents/section\d+\.xml", n)]
    )
    if not section_names:
        raise ExtractionError("HWPX 문서에서 본문 섹션을 찾을 수 없습니다.")

    pages: list[ExtractedPage] = []
    for i, name in enumerate(section_names, start=1):
        try:
            root = ET.fromstring(zf.read(name))
        except ET.ParseError as exc:
            raise ExtractionError(f"HWPX 섹션({name}) XML 파싱에 실패했습니다.") from exc

        paragraphs: list[str] = []
        for para in root.iter():
            if _local(para.tag) == "p":
                text = "".join(_iter_text(para)).strip()
                if text:
                    paragraphs.append(text)

        if not paragraphs:
            # Fallback: grab any <t> text in document order if paragraph grouping failed
            paragraphs = [t.strip() for t in _iter_text(root) if t.strip()]

        pages.append(ExtractedPage(page_number=i, text="\n".join(paragraphs), ocr_used=False))

    zf.close()
    return ExtractionResult(pages=pages)
