import logging
from dataclasses import dataclass
from pathlib import Path

import fitz  # pymupdf

logger = logging.getLogger(__name__)


@dataclass
class PageImage:
    page_number: int
    image_path: str


def rasterise(pdf_path: str, document_id: int, pages_dir: Path, dpi: int = 150) -> list[PageImage]:
    out_dir = pages_dir / str(document_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    results: list[PageImage] = []

    for page_num, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=mat)
        img_path = out_dir / f"{page_num:04d}.png"
        pix.save(str(img_path))
        results.append(PageImage(page_number=page_num, image_path=str(img_path)))
        logger.debug("Rasterised page %d → %s", page_num, img_path)

    doc.close()
    logger.info("Rasterised %d pages for document %d", len(results), document_id)
    return results
