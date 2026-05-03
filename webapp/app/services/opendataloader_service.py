import json
import logging
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import fitz  # pymupdf
import opendataloader_pdf

from .storage import ElementData

logger = logging.getLogger(__name__)


def _convert_element(
    pdf_input: dict[str, Any], page_w: float, page_h: float
) -> ElementData | None:
    """Recursively convert an opendataloader element tree node to ElementData.

    Coordinates from opendataloader are in PDF points (origin bottom-left).
    This converts them to per-mil (0–1000) with origin top-left to match
    the webapp's storage convention.
    """
    kids = pdf_input.get("kids", [])
    if not kids:
        content = pdf_input.get("content", "")
        if not content:
            return None
        bbox = pdf_input.get("bounding box", [])
        if len(bbox) < 4:
            return None
        pdf_x0, pdf_y0, pdf_x1, pdf_y1 = bbox[:4]
        x0 = (pdf_x0 / page_w) * 1000
        x1 = (pdf_x1 / page_w) * 1000
        # Flip y-axis: PDF y=0 is bottom, image y=0 is top.
        # pdf_y1 is the top edge in PDF coords → top edge in screen coords.
        y0 = ((page_h - pdf_y1) / page_h) * 1000
        y1 = ((page_h - pdf_y0) / page_h) * 1000
        return ElementData(
            text=content,
            classification=pdf_input.get("type"),
            x0=x0, y0=y0, x1=x1, y1=y1,
        )

    children = [_convert_element(k, page_w, page_h) for k in kids]
    children = [c for c in children if c is not None]
    if not children:
        return None
    content = "\n".join(c.text for c in children)
    x0 = min(c.x0 for c in children)
    y0 = min(c.y0 for c in children)
    x1 = max(c.x1 for c in children)
    y1 = max(c.y1 for c in children)
    return ElementData(
        text=content,
        classification=pdf_input.get("type"),
        x0=x0, y0=y0, x1=x1, y1=y1,
    )


def parse_pdf(pdf_path: str) -> dict[int, list[ElementData]]:
    """Parse a PDF with opendataloader_pdf and return elements per page.

    Returns a dict mapping 1-indexed page_number to list of ElementData,
    with coordinates in per-mil (0–1000), origin top-left.
    """
    with tempfile.TemporaryDirectory() as tmp:
        filename = Path(pdf_path).stem
        opendataloader_pdf.convert(
            input_path=[pdf_path],
            output_dir=tmp,
            format="json",
            quiet=True,
        )

        json_path = Path(tmp) / f"{filename}.json"
        if not json_path.exists():
            logger.warning("opendataloader produced no output for %s", pdf_path)
            return {}

        raw = json.loads(json_path.read_text(encoding="utf-8"))

    if not isinstance(raw, dict) or "kids" not in raw:
        logger.warning("Unexpected opendataloader JSON structure for %s", pdf_path)
        return {}

    # Get per-page dimensions (in PDF points) so we can normalise coordinates.
    pdf_doc = fitz.open(pdf_path)
    page_dims: dict[int, tuple[float, float]] = {
        i: (page.rect.width, page.rect.height)
        for i, page in enumerate(pdf_doc, start=1)
    }
    pdf_doc.close()

    page2kids: dict[int, list] = defaultdict(list)
    for kid in raw.get("kids", []):
        page_n = kid.get("page number")
        if page_n is None:
            continue
        page2kids[int(page_n)].append(kid)

    result: dict[int, list[ElementData]] = {}
    for page_n, kids in page2kids.items():
        page_w, page_h = page_dims.get(page_n, (595.0, 842.0))
        elements = []
        for kid in kids:
            el = _convert_element(kid, page_w, page_h)
            if el is None or not el.text:
                continue
            elements.append(el)
        result[page_n] = elements

    logger.info("opendataloader parsed %d pages from %s", len(result), pdf_path)
    return result
