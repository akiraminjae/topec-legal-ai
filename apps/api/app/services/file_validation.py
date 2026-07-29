import hashlib
import re
import uuid

from fastapi import HTTPException, UploadFile

from app.core.config import get_settings

settings = get_settings()

_MIME_BY_EXTENSION = {
    "pdf": {"application/pdf"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "png": {"image/png"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "hwpx": {"application/hwp+zip", "application/zip", "application/octet-stream"},
    "hwp": {"application/x-hwp", "application/octet-stream"},
    "txt": {"text/plain"},
}

_DANGEROUS_EXTENSIONS = {"exe", "bat", "cmd", "sh", "ps1", "js", "vbs", "msi", "dll", "com", "scr"}

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._\-가-힣 ]+")


class FileValidationResult:
    def __init__(self, safe_filename: str, extension: str, sha256_hash: str, size_bytes: int):
        self.safe_filename = safe_filename
        self.extension = extension
        self.sha256_hash = sha256_hash
        self.size_bytes = size_bytes


def normalize_filename(filename: str) -> str:
    """Strip path components and disallowed characters to prevent path traversal / injection."""
    base = filename.replace("\\", "/").split("/")[-1]
    base = _SAFE_FILENAME_RE.sub("_", base).strip()
    return base or f"file_{uuid.uuid4().hex}"


def validate_upload(file: UploadFile, content: bytes) -> FileValidationResult:
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일은 업로드할 수 없습니다.")

    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"파일 크기가 제한({settings.MAX_UPLOAD_SIZE_MB}MB)을 초과했습니다.",
        )

    safe_filename = normalize_filename(file.filename or "")
    extension = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""

    if extension in _DANGEROUS_EXTENSIONS:
        raise HTTPException(status_code=400, detail="허용되지 않는 파일 형식입니다.")

    if extension not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. 허용 형식: {', '.join(settings.allowed_extensions_list)}",
        )

    declared_mime = (file.content_type or "").lower().split(";")[0].strip()
    allowed_mimes = _MIME_BY_EXTENSION.get(extension, set())
    if allowed_mimes and declared_mime not in allowed_mimes:
        # MIME/확장자 불일치 — 확장자 위조 가능성. 차단하지 않고 경고성 상태로만 기록할 수도 있으나
        # 여기서는 이중검증 원칙에 따라 명확히 차단한다.
        raise HTTPException(
            status_code=400,
            detail="파일 확장자와 실제 형식(MIME type)이 일치하지 않습니다.",
        )

    sha256_hash = hashlib.sha256(content).hexdigest()

    return FileValidationResult(
        safe_filename=safe_filename,
        extension=extension,
        sha256_hash=sha256_hash,
        size_bytes=len(content),
    )


def scan_for_virus(content: bytes) -> str:
    """Virus scan interface. Returns a status string.

    Without a configured ClamAV instance this returns NOT_CONFIGURED rather than
    pretending a scan happened — the UI must surface this honestly.
    """
    if not settings.CLAMAV_HOST:
        return "NOT_CONFIGURED"
    try:
        import clamd  # type: ignore

        cd = clamd.ClamdNetworkSocket(host=settings.CLAMAV_HOST, port=settings.CLAMAV_PORT)
        result = cd.instream(content)
        status = result.get("stream", ("ERROR", None))[0]
        return "INFECTED" if status == "FOUND" else "CLEAN"
    except Exception:
        return "SCAN_FAILED"
