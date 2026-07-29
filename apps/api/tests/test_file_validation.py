import io

import pytest
from fastapi import HTTPException, UploadFile

from app.services.file_validation import normalize_filename, validate_upload


def _upload_file(filename: str, content_type: str) -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(b"dummy"), headers={"content-type": content_type})


def test_normalize_filename_strips_path_traversal():
    assert normalize_filename("../../etc/passwd") == "passwd"
    assert normalize_filename("..\\..\\windows\\system32\\config") == "config"


def test_normalize_filename_keeps_korean_and_safe_chars():
    result = normalize_filename("하도급 계약서(최종).pdf")
    assert result.endswith(".pdf")
    assert "/" not in result and "\\" not in result


def test_validate_upload_rejects_empty_file():
    file = _upload_file("empty.pdf", "application/pdf")
    with pytest.raises(HTTPException):
        validate_upload(file, b"")


def test_validate_upload_rejects_disallowed_extension():
    file = _upload_file("malware.exe", "application/octet-stream")
    with pytest.raises(HTTPException):
        validate_upload(file, b"binary content")


def test_validate_upload_rejects_mime_extension_mismatch():
    file = _upload_file("fake.pdf", "image/png")
    with pytest.raises(HTTPException):
        validate_upload(file, b"not really a pdf")


def test_validate_upload_accepts_matching_pdf():
    file = _upload_file("contract.pdf", "application/pdf")
    result = validate_upload(file, b"%PDF-1.4 fake pdf content")
    assert result.extension == "pdf"
    assert len(result.sha256_hash) == 64
