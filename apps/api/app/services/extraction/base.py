from dataclasses import dataclass


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    ocr_used: bool = False
    ocr_confidence: float | None = None


@dataclass
class ExtractionResult:
    pages: list[ExtractedPage]
    warning: str | None = None

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages)


class ExtractionError(Exception):
    """Raised when a document cannot be reliably extracted; never fabricate content on failure."""
