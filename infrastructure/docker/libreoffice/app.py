"""Minimal HTTP wrapper around LibreOffice headless for DOCX -> PDF conversion.

Internal-only service (no auth) intended to be reachable only from the api/worker
containers on the docker-compose internal network.
"""
import subprocess
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

app = FastAPI(title="TOPEC LibreOffice Conversion Service")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/convert")
async def convert(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".docx", ".doc", ".odt")):
        raise HTTPException(status_code=400, detail="지원하지 않는 입력 형식입니다.")

    work_dir = Path(tempfile.mkdtemp(prefix="conv_"))
    input_path = work_dir / f"{uuid.uuid4().hex}_{file.filename}"
    input_path.write_bytes(await file.read())

    try:
        result = subprocess.run(
            [
                "soffice",
                "--headless",
                "--norestore",
                "--convert-to",
                "pdf",
                "--outdir",
                str(work_dir),
                str(input_path),
            ],
            capture_output=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="PDF 변환 시간이 초과되었습니다.")

    output_path = input_path.with_suffix(".pdf")
    if result.returncode != 0 or not output_path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"PDF 변환에 실패했습니다: {result.stderr.decode(errors='ignore')[:300]}",
        )

    return FileResponse(output_path, media_type="application/pdf", filename=output_path.name)
