import json
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..database import get_session
from ..models import Document, Page
from ..routers.documents import _delete_document_files
from ..tasks.pipeline import process_document
from ..templates import templates

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/")
def index(request: Request, session: Session = Depends(get_session)):
    docs = session.query(Document).order_by(Document.created_at.desc()).all()
    return templates.TemplateResponse(
        request, "index.html", {"documents": docs}
    )


@router.post("/upload")
async def upload_ui(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    parser: str = Form("docling"),
    session: Session = Depends(get_session),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return templates.TemplateResponse(
            request,
            "partials/upload_error.html",
            {"error": "Only PDF files are accepted"},
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
    return templates.TemplateResponse(
        request, "partials/document_card.html", {"doc": doc}
    )


@router.get("/documents/{doc_id}/status-badge")
def status_badge(
    doc_id: int, request: Request, session: Session = Depends(get_session)
):
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request, "partials/status_badge.html", {"doc": doc}
    )


@router.get("/documents/{doc_id}/view")
def view_document(
    doc_id: int,
    request: Request,
    page_num: int = 1,
    session: Session = Depends(get_session),
):
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    pages = (
        session.query(Page)
        .filter_by(document_id=doc_id)
        .order_by(Page.page_number)
        .all()
    )

    current_page = next((p for p in pages if p.page_number == page_num), None)
    if current_page is None and pages:
        current_page = pages[0]
        page_num = current_page.page_number

    elements_json = "[]"
    if current_page:
        elements_json = json.dumps(
            [
                {
                    "id": e.id,
                    "index": e.element_index,
                    "text": e.text,
                    "classification": e.classification or "text",
                    "x0": e.x0,
                    "y0": e.y0,
                    "x1": e.x1,
                    "y1": e.y1,
                }
                for e in current_page.elements
            ]
        )

    return templates.TemplateResponse(
        request,
        "document.html",
        {
            "document": doc,
            "pages": pages,
            "current_page": current_page,
            "page_num": page_num,
            "elements_json": elements_json,
        },
    )


@router.get("/documents/{doc_id}/page-data")
def page_data(
    doc_id: int,
    request: Request,
    page_num: int = 1,
    session: Session = Depends(get_session),
):
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    pages = (
        session.query(Page)
        .filter_by(document_id=doc_id)
        .order_by(Page.page_number)
        .all()
    )
    current_page = next((p for p in pages if p.page_number == page_num), None)
    if current_page is None and pages:
        current_page = pages[0]
        page_num = current_page.page_number

    elements = []
    if current_page:
        elements = [
            {
                "id": e.id,
                "index": e.element_index,
                "text": e.text,
                "classification": e.classification or "text",
                "x0": e.x0,
                "y0": e.y0,
                "x1": e.x1,
                "y1": e.y1,
            }
            for e in current_page.elements
        ]

    return {
        "page_num": page_num,
        "total_pages": doc.page_count or len(pages),
        "image_url": f"/pages/{current_page.id}/image" if current_page else None,
        "elements": elements,
    }


@router.delete("/documents/{doc_id}")
def delete_document_ui(
    doc_id: int,
    session: Session = Depends(get_session),
):
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    _delete_document_files(doc)
    session.delete(doc)
    session.commit()
    return Response(status_code=200)
