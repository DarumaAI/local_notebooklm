import base64
import logging
import re
from pathlib import Path
from typing import Any

import httpx

from ..config import VLLM_BASE_URL, VLLM_MODEL, VLLM_TIMEOUT

logger = logging.getLogger(__name__)

# Matches one or more <loc_N> tags at the start of a line.
_LOC_HEADER = re.compile(r"^((?:<loc_\d+>)+)")
_LOC_NUM = re.compile(r"\d+")
_LOC_TAG = re.compile(r"<loc_\d+>")


_MAX_SIDE = 798  # match the notebook's thumbnail target


def _resize_png(path: Path, max_side: int) -> bytes:
    """Return PNG bytes scaled so the longest side ≤ max_side."""
    import io

    from PIL import Image

    img = Image.open(path)
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def parse_page(image_path: str) -> list[dict[str, Any]]:
    """Call Granite-Docling via vLLM and return a flat list of element dicts.

    Each dict has keys: text, classification, x0, y0, x1, y1.
    Returns [] if vLLM is unreachable or the response cannot be parsed.
    """
    b64 = base64.b64encode(_resize_png(Path(image_path), _MAX_SIDE)).decode()

    payload = {
        "model": VLLM_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                    {
                        "type": "text",
                        "text": "Convert this page to docling.",
                    },
                ],
            }
        ],
        "max_tokens": 4096,
        "temperature": 0.0,
    }

    try:
        resp = httpx.post(
            f"{VLLM_BASE_URL}/chat/completions",
            json=payload,
            timeout=VLLM_TIMEOUT,
        )
        if not resp.is_success:
            logger.warning(
                "vLLM %s for %s: %s", resp.status_code, image_path, resp.text
            )
            resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return _parse_response(content)
    except httpx.ConnectError:
        logger.warning(
            "vLLM not reachable at %s — page will have no elements",
            VLLM_BASE_URL,
        )
        return []
    except Exception as exc:
        logger.warning("Docling parse failed for %s: %s", image_path, exc)
        return []


def _parse_response(content: str) -> list[dict[str, Any]]:
    """Parse Granite-Docling plain-text output into a flat list of element dicts.

    The model emits one element per line in the form:
        <loc_X0><loc_Y0><loc_X1><loc_Y1>text content
    Coordinates are per-mil integers (0–1000).
    8-coordinate (polygon) lines are collapsed to their axis-aligned bbox.
    """
    elements = []
    coords: list[int] = []

    for i, line in enumerate(content.splitlines()):
        header = _LOC_HEADER.match(line)
        if header:
            coords = [int(n) for n in _LOC_NUM.findall(header.group(1))]

        text = _LOC_TAG.sub("", line).strip()
        if not text:
            continue

        if len(coords) == 4:
            x0, y0, x1, y1 = coords
        elif len(coords) == 8:
            xs = coords[0::2]
            ys = coords[1::2]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        else:
            x0, y0, x1, y1 = 0, 0, 1000, 1000

        elements.append(
            {
                "text": text,
                "classification": None,
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
            }
        )

    return elements
