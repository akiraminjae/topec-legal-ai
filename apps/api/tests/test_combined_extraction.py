"""Multi-file combined analysis input (document_pipeline.extract_all_document_files).

The pipeline used to extract only the first-uploaded file; every other
attachment was stored but never read by the AI. Now all attached files are
extracted and combined — the primary keeps its 12,000-char budget, and each
attachment gets its own per-file budget so a long primary file cannot crowd
attachments out of the prompt truncation window.
"""
import uuid

import pytest

from app.models.document import Document, DocumentFile
from app.models.enums import DocumentCategory
from app.services.document_pipeline import (
    ATTACHMENT_MIN_AI_CHARS,
    PRIMARY_FILE_AI_CHARS,
    PipelineError,
    extract_all_document_files,
)


class _DictStorage:
    def __init__(self, objects: dict[str, bytes]):
        self._objects = objects

    def get_object(self, key: str) -> bytes:
        return self._objects[key]


def _make_document(db, owner, title="결합추출 테스트") -> Document:
    doc = Document(title=title, document_category=DocumentCategory.LITIGATION, owner_id=owner.id)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _attach(db, document, filename: str, key: str, extension: str = "txt") -> DocumentFile:
    f = DocumentFile(
        document_id=document.id,
        original_filename=filename,
        stored_key=key,
        content_type="text/plain",
        extension=extension,
        size_bytes=1,
        sha256_hash=uuid.uuid4().hex * 2,
    )
    db.add(f)
    db.commit()
    return f


def test_single_file_keeps_previous_behavior(db_session, make_user):
    owner, _ = make_user()
    doc = _make_document(db_session, owner)
    _attach(db_session, doc, "only.txt", "k1")
    storage = _DictStorage({"k1": "단일 파일 내용".encode()})

    result = extract_all_document_files(db_session, doc, storage)

    assert result.full_text == "단일 파일 내용"
    assert result.ai_text == "단일 파일 내용"
    assert "=====" not in result.full_text  # no section headers for a lone file
    assert result.file_count == 1


def test_all_attachments_are_included_with_headers(db_session, make_user):
    owner, _ = make_user()
    doc = _make_document(db_session, owner)
    _attach(db_session, doc, "primary.txt", "k1")
    _attach(db_session, doc, "annex-a.txt", "k2")
    _attach(db_session, doc, "annex-b.txt", "k3")
    storage = _DictStorage(
        {"k1": "주 파일 본문".encode(), "k2": "첨부A 본문".encode(), "k3": "첨부B 본문".encode()}
    )

    result = extract_all_document_files(db_session, doc, storage)

    for expected in ("주 파일 본문", "첨부A 본문", "첨부B 본문", "primary.txt", "annex-a.txt", "annex-b.txt"):
        assert expected in result.full_text
        assert expected in result.ai_text
    assert "[주 파일(분석대상)]" in result.ai_text
    assert "[첨부 1/2]" in result.ai_text and "[첨부 2/2]" in result.ai_text
    # pages renumbered sequentially across files (each txt is 1 page)
    assert [p.page_number for p in result.pages] == [1, 2, 3]


def test_long_primary_does_not_crowd_out_attachments(db_session, make_user):
    owner, _ = make_user()
    doc = _make_document(db_session, owner)
    _attach(db_session, doc, "huge-primary.txt", "k1")
    _attach(db_session, doc, "small-annex.txt", "k2")
    storage = _DictStorage({"k1": (b"A" * (PRIMARY_FILE_AI_CHARS * 3)), "k2": "핵심 첨부 내용".encode()})

    result = extract_all_document_files(db_session, doc, storage)

    # the primary is trimmed to its budget, the annex still fully present
    assert "핵심 첨부 내용" in result.ai_text
    assert "…(이하 생략)…" in result.ai_text
    assert len(result.ai_text) < PRIMARY_FILE_AI_CHARS * 2
    # full_text (clause splitting / page storage) is NOT trimmed
    assert "A" * (PRIMARY_FILE_AI_CHARS * 3) in result.full_text


def test_failed_attachment_is_skipped_but_failed_primary_raises(db_session, make_user):
    owner, _ = make_user()
    doc = _make_document(db_session, owner)
    _attach(db_session, doc, "primary.txt", "k1")
    _attach(db_session, doc, "broken.xyz", "k2", extension="xyz")  # unsupported → ExtractionError
    storage = _DictStorage({"k1": "본문".encode(), "k2": b"whatever"})

    result = extract_all_document_files(db_session, doc, storage)
    assert result.failed_filenames == ["broken.xyz"]
    assert result.warning and "broken.xyz" in result.warning
    assert "본문" in result.full_text

    doc2 = _make_document(db_session, owner, title="주 파일 실패")
    _attach(db_session, doc2, "broken-primary.xyz", "k3", extension="xyz")
    storage2 = _DictStorage({"k3": b"whatever"})
    with pytest.raises(PipelineError):
        extract_all_document_files(db_session, doc2, storage2)


def test_many_attachments_each_keep_a_minimum_budget(db_session, make_user):
    owner, _ = make_user()
    doc = _make_document(db_session, owner)
    _attach(db_session, doc, "primary.txt", "k0")
    objects = {"k0": "주 파일".encode()}
    for i in range(1, 41):  # 40 attachments → per-file budget bottoms out at the floor
        _attach(db_session, doc, f"annex-{i}.txt", f"k{i}")
        objects[f"k{i}"] = f"첨부{i}내용 ".encode() * 10

    result = extract_all_document_files(db_session, doc, _DictStorage(objects))

    assert result.file_count == 41
    for i in (1, 20, 40):
        assert f"첨부{i}내용" in result.ai_text
    assert ATTACHMENT_MIN_AI_CHARS >= 2000  # guard: floor stays meaningful
