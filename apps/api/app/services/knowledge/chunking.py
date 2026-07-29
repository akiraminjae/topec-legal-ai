def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    """Simple sliding-window chunker over paragraph boundaries.

    Good enough for statutes/case law/checklists which are already reasonably
    structured; avoids splitting mid-sentence where possible by preferring
    paragraph breaks near the max_chars boundary.
    """
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 1 <= max_chars:
            current = f"{current}\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            if len(para) > max_chars:
                for i in range(0, len(para), max_chars - overlap):
                    chunks.append(para[i : i + max_chars])
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks or ([text] if text.strip() else [])
