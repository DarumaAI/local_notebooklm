from typing import List, Optional

from pydantic import BaseModel


class ElementOut(BaseModel):
    id: int
    element_index: int
    text: str
    classification: Optional[str]
    x0: float
    y0: float
    x1: float
    y1: float

    model_config = {"from_attributes": True}


class PageOut(BaseModel):
    id: int
    page_number: int
    elements: List[ElementOut] = []

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: int
    original_name: str
    status: str
    page_count: Optional[int]
    error_message: Optional[str]
    created_at: str
    updated_at: str
    pages: List[PageOut] = []

    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    id: int
    original_name: str
    status: str
    page_count: Optional[int]
    created_at: str

    model_config = {"from_attributes": True}


class StatusOut(BaseModel):
    id: int
    status: str
    page_count: Optional[int]
    error_message: Optional[str]
