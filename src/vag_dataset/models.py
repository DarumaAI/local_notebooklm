from typing import List, Optional, Union

from pydantic import BaseModel, model_validator


class Coordinates(BaseModel):
    x0: Union[float, int]
    y0: Union[float, int]
    x1: Union[float, int]
    y1: Union[float, int]

    @model_validator(mode="after")
    def check_uniform_type(self) -> "Coordinates":
        values = [self.x0, self.y0, self.x1, self.y1]
        types = set([type(v) for v in values])
        if len(types) > 1:
            raise ValueError(
                f"All coordinates must be the same type (float or int), got {types}"
            )
        return self


class Element(BaseModel):
    text: str
    id: int  # The sequential id in the page
    classification: Optional[str] = None
    coordinates: Coordinates
    page_n: int
    doc: str


class Citation(BaseModel):
    start_idx: int  # The characters start index in the original answer
    end_idx: int  # The characters end index in the original answer
    page: int  # The page number
    bbox: Coordinates  # The bounding box coordinates in the page


class AttributedAnswer(BaseModel):
    answer: str  # The answer string
    citations: List[Citation]  # The list of citations


class DocumentChunk(BaseModel):
    content: List[Element]
