from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import Page
from ..schemas import ElementOut

router = APIRouter()


@router.get("/{page_id}/image")
def get_page_image(page_id: int, session: Session = Depends(get_session)):
    page = session.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(page.image_path, media_type="image/png")


@router.get("/{page_id}/elements", response_model=List[ElementOut])
def get_page_elements(page_id: int, session: Session = Depends(get_session)):
    page = session.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return [ElementOut.model_validate(e) for e in page.elements]
