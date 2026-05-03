import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..database import get_session

logger = logging.getLogger(__name__)
from ..models import Document
from ..schemas import DocumentListItem, DocumentOut, StatusOut
from ..tasks.pipeline import process_document

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    parser: str = Form("docling"),
    session: Session = Depends(get_session),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="Only PDF files are accepted"
        )

    # safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    safe_name = f"{file.filename}"
    dest = UPLOAD_DIR / safe_name
    dest.write_bytes(await file.read())

    now = _now()
    doc = Document(
        filename=safe_name,
        original_name=file.filename,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    background_tasks.add_task(process_document, doc.id, parser)
    return {"id": doc.id, "status": "pending"}


@router.get("", response_model=List[DocumentListItem])
def list_documents(session: Session = Depends(get_session)):
    docs = session.query(Document).order_by(Document.created_at.desc()).all()
    return [DocumentListItem.model_validate(d) for d in docs]


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: int, session: Session = Depends(get_session)):
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentOut.model_validate(doc)


@router.get("/{doc_id}/status", response_model=StatusOut)
def get_status(doc_id: int, session: Session = Depends(get_session)):
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return StatusOut(
        id=doc_id,
        status=doc.status,
        page_count=doc.page_count,
        error_message=doc.error_message,
    )


def _delete_document_files(doc) -> None:
    pdf_path = UPLOAD_DIR / doc.filename
    if pdf_path.exists():
        pdf_path.unlink()
        logger.info("Deleted PDF %s", pdf_path)
    for page in doc.pages:
        img = Path(page.image_path)
        if img.exists():
            img.unlink()
            logger.info("Deleted page image %s", img)


@router.delete("/{doc_id}")
def delete_document(doc_id: int, session: Session = Depends(get_session)):
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    _delete_document_files(doc)
    session.delete(doc)
    session.commit()
    return {"deleted": doc_id}
