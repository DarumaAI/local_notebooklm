from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..models import Document, Element, Page


@dataclass
class ElementData:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    classification: Optional[str] = None


@dataclass
class PageData:
    page_number: int
    image_path: str
    elements: list[ElementData] = field(default_factory=list)


def persist_pages(session: Session, document_id: int, pages: list[PageData]) -> None:
    for page_data in pages:
        page = Page(
            document_id=document_id,
            page_number=page_data.page_number,
            image_path=page_data.image_path,
        )
        session.add(page)
        session.flush()

        for idx, elem in enumerate(page_data.elements):
            session.add(
                Element(
                    page_id=page.id,
                    element_index=idx,
                    text=elem.text,
                    classification=elem.classification,
                    x0=elem.x0,
                    y0=elem.y0,
                    x1=elem.x1,
                    y1=elem.y1,
                )
            )

    doc = session.get(Document, document_id)
    doc.page_count = len(pages)
    doc.updated_at = datetime.now(timezone.utc).isoformat()
