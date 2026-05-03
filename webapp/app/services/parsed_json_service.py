import json
import logging

from ..config import PARSED_DOCS_DIR
from .storage import ElementData

logger = logging.getLogger(__name__)


def load_parsed_doc(arxiv_id: str) -> dict[int, list[ElementData]] | None:
    """Load pre-parsed elements from a Colab-generated JSON file.

    Returns a dict mapping page_number (1-indexed int) to a list of ElementData,
    or None if no matching file exists.

    JSON coordinates are normalised floats in [0, 1]; they are multiplied by 1000
    so that all stored coordinates use the per-mil (0–1000) convention.
    """
    print(f"Arix_id is {arxiv_id}")
    candidate = PARSED_DOCS_DIR / f"{arxiv_id}.json"
    print(f"Candidate path is {candidate}")
    if not candidate.exists():
        print("Candidate does not exist")
        return None

    try:
        raw = json.loads(candidate.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not read pre-parsed JSON %s: %s", candidate, exc)
        return None

    result: dict[int, list[ElementData]] = {}
    for page_str, page_data in raw.items():
        try:
            page_num = int(page_str)
        except ValueError:
            continue
        elements: list[ElementData] = []
        for elem in page_data.get("elements", []):
            coords = elem.get("coordinates", {})
            x0 = float(coords.get("x0", 0.0))
            y0 = float(coords.get("y0", 0.0))
            x1 = float(coords.get("x1", 1.0))
            y1 = float(coords.get("y1", 1.0))
            # JSON files store normalised [0, 1] floats; convert to per-mil integers.
            if x1 <= 1.0:
                x0, y0, x1, y1 = x0 * 1000, y0 * 1000, x1 * 1000, y1 * 1000
            elements.append(
                ElementData(
                    text=elem.get("text", ""),
                    classification=elem.get("classification"),
                    x0=x0,
                    y0=y0,
                    x1=x1,
                    y1=y1,
                )
            )
        result[page_num] = elements

    logger.info(
        "Loaded pre-parsed JSON for %s: %d pages", arxiv_id, len(result)
    )
    return result
