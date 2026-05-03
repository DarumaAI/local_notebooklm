import logging
from datetime import datetime, timezone

from ..config import PAGES_DIR, RASTER_DPI, UPLOAD_DIR
from ..database import SessionLocal
from ..models import Document
from ..services.docling_service import parse_page
from ..services.parsed_json_service import load_parsed_doc
from ..services.pdf_processor import rasterise
from ..services.storage import ElementData, PageData, persist_pages

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def process_document(document_id: int, parser: str = "docling") -> None:
    session = SessionLocal()
    try:
        doc = session.get(Document, document_id)
        doc.status = "processing"
        doc.updated_at = _now()
        session.commit()

        pdf_path = UPLOAD_DIR / doc.filename
        page_images = rasterise(
            str(pdf_path), document_id, PAGES_DIR, dpi=RASTER_DPI
        )

        if parser == "opendataloader":
            from ..services.opendataloader_service import parse_pdf
            parsed_doc = parse_pdf(str(pdf_path))
        else:
            parsed_doc = load_parsed_doc(doc.filename.replace(".pdf", ""))
            if parsed_doc is None:
                parsed_doc = dict()

        pages_data: list[PageData] = []
        for pi in page_images:
            page_number = int(pi.page_number)

            if page_number in parsed_doc:
                elements = parsed_doc[page_number]
            elif parser == "opendataloader":
                elements = []
            else:
                raw_elements = parse_page(pi.image_path)
                elements = [
                    ElementData(
                        text=e["text"],
                        classification=e.get("classification"),
                        x0=e["x0"],
                        y0=e["y0"],
                        x1=e["x1"],
                        y1=e["y1"],
                    )
                    for e in raw_elements
                ]
            pages_data.append(
                PageData(
                    page_number=pi.page_number,
                    image_path=pi.image_path,
                    elements=elements,
                )
            )

        persist_pages(session, document_id, pages_data)

        doc.status = "done"
        doc.updated_at = _now()
        session.commit()
        logger.info(
            "Document %d processed: %d pages", document_id, len(pages_data)
        )

    except Exception as exc:
        logger.exception("Pipeline failed for document %d", document_id)
        session.rollback()
        try:
            doc = session.get(Document, document_id)
            doc.status = "error"
            doc.error_message = str(exc)
            doc.updated_at = _now()
            session.commit()
        except Exception:
            logger.exception(
                "Could not write error status for document %d", document_id
            )
    finally:
        session.close()
