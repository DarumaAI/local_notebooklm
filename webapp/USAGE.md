# USAGE — VAG Study Tool

## Load Granite Docling

To use the system with Granite Docling

```bash
python scripts/serve_docling.py
```

Then, update the .env file in the webapp folder:

```
VLLM_BASE_URL=http://localhost:8000/v1
VLLM_MODEL=ibm-granite/granite-docling-258M
```

## Starting and stopping

Run everything from the `webapp/` directory.

```bash
cd webapp
python3 -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` in your browser.

To stop the server press `Ctrl+C` in the terminal.

`--reload` watches for code changes and restarts automatically — remove it in production.
To bind to a different port: `--port 8080`.

---

## First-time setup

Install dependencies once into your Python environment:

```bash
cd webapp
pip install -r requirements.txt
```

The app creates two directories and the SQLite database on first start:

| Path (relative to `webapp/`) | Purpose |
|---|---|
| `uploads/` | Original PDFs saved on upload |
| `pages/` | Rasterised PNG per page (`pages/{doc_id}/{page_num:04d}.png`) |
| `app.db` | SQLite database (documents, pages, elements) |

---

## Configuration

All settings can be overridden via environment variables or the `.env` file at the repo root.

| Variable | Default | Description |
|---|---|---|
| `UPLOAD_DIR` | `uploads` | Where uploaded PDFs are stored |
| `PAGES_DIR` | `pages` | Where rasterised PNGs are stored |
| `DB_PATH` | `app.db` | SQLite database file |
| `RASTER_DPI` | `150` | DPI used when converting PDF pages to PNG |
| `VLLM_BASE_URL` | `http://localhost:8000/v1` | OpenAI-compatible vLLM endpoint |
| `VLLM_MODEL` | `ibm-granite/granite-docling-258M` | Model name sent to vLLM |
| `VLLM_TIMEOUT` | `120.0` | Per-request timeout in seconds for vLLM calls |

---

## How the app works

### Upload and processing pipeline

1. You upload a PDF via the browser form.
2. The server saves the file to `uploads/` and inserts a `Document` row with `status = "pending"`.
3. A FastAPI background task fires immediately and runs three steps in sequence:
   - **`pdf_processor`** — PyMuPDF renders each PDF page to a PNG at `RASTER_DPI`.
   - **`docling_service`** — each PNG is sent to the Granite-Docling model via vLLM; the response is parsed into text blocks with normalised bounding boxes (`[0, 1]` floats relative to page size).
   - **`storage`** — `Page` and `Element` rows are written to SQLite in a single transaction.
4. `Document.status` is set to `"done"` (or `"error"` with a message if any step fails).
5. The browser polls `GET /documents/{id}/status-badge` every 2 seconds via HTMX until the status is terminal, then shows an **Open** link.

If vLLM is not running the pipeline still completes: pages are rasterised and stored, but elements will be empty. You can re-upload the same PDF later once vLLM is available.

### Document viewer

Clicking **Open** navigates to `/documents/{id}/view`. The viewer has three panels:

- **Left** — scrollable thumbnail strip; click any thumbnail to jump to that page.
- **Centre** — full-resolution page image. A `<canvas>` is layered on top and draws semi-transparent coloured rectangles for each extracted element.
- **Right** — the element list. Hovering an item highlights its bounding box on the canvas in the centre panel.

Colours by element type: blue = text, green = title, yellow = figure, red = table, grey = other.

---

## Main components

```
webapp/
├── app/
│   ├── config.py           — all settings, reads .env
│   ├── database.py         — SQLite engine (WAL mode), session factory
│   ├── models.py           — SQLAlchemy ORM: Document, Page, Element
│   ├── schemas.py          — Pydantic response schemas
│   ├── main.py             — FastAPI app, mounts static files, registers routers
│   ├── routers/
│   │   ├── documents.py    — JSON API for documents (upload, list, get, status, delete)
│   │   ├── pages.py        — serve page images and element JSON
│   │   └── ui.py           — HTML routes (index, upload form, viewer, status badge)
│   ├── services/
│   │   ├── pdf_processor.py   — PyMuPDF: PDF → PNG per page
│   │   ├── docling_service.py — vLLM HTTP call → list of element dicts
│   │   └── storage.py         — insert Page + Element rows into DB
│   └── tasks/
│       └── pipeline.py     — orchestrates the three services above
├── templates/              — Jinja2 HTML (base, index, document, partials)
├── static/
│   ├── css/style.css       — layout and component styles
│   └── js/bbox.js          — canvas bbox drawing and element-list hover logic
└── requirements.txt
```

---

## REST API reference

The JSON API is separate from the HTML routes so you can drive the app programmatically (e.g. from a notebook or an LLM agent).

### Documents

| Method | Path | Description |
|---|---|---|
| `POST` | `/documents/upload` | Upload a PDF (`multipart/form-data`, field `file`). Returns `{"id": N, "status": "pending"}`. |
| `GET` | `/documents` | List all documents (summary, no pages). |
| `GET` | `/documents/{id}` | Full document: metadata + all pages + all elements. |
| `GET` | `/documents/{id}/status` | Lightweight status check: `{id, status, page_count, error_message}`. |
| `DELETE` | `/documents/{id}` | Delete document and all its pages and elements from the DB. |

### Pages

| Method | Path | Description |
|---|---|---|
| `GET` | `/pages/{page_id}/image` | Returns the rasterised PNG for that page. |
| `GET` | `/pages/{page_id}/elements` | Returns a JSON array of all elements on the page. |

Each element in the array:

```json
{
  "id": 12,
  "element_index": 3,
  "text": "Introduction",
  "classification": "title",
  "x0": 0.07, "y0": 0.12, "x1": 0.45, "y1": 0.16
}
```

Coordinates are normalised to `[0, 1]` relative to the page image dimensions.

### Interactive docs

FastAPI generates OpenAPI docs automatically:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## Interfacing with LLMs

The REST API is the integration point. A typical pattern from a notebook or script:

### 1. Upload a document

```python
import httpx

BASE = "http://127.0.0.1:8000"

with open("paper.pdf", "rb") as f:
    resp = httpx.post(f"{BASE}/documents/upload", files={"file": ("paper.pdf", f, "application/pdf")})
doc_id = resp.json()["id"]
```

### 2. Wait for processing to finish

```python
import time

while True:
    status = httpx.get(f"{BASE}/documents/{doc_id}/status").json()
    if status["status"] in ("done", "error"):
        break
    time.sleep(2)
```

### 3. Retrieve structured content

```python
doc = httpx.get(f"{BASE}/documents/{doc_id}").json()

# Flatten all elements across all pages
elements = [
    {"page": page["page_number"], **elem}
    for page in doc["pages"]
    for elem in page["elements"]
]
```

### 4. Feed to an LLM

Each element already has its text and bounding box. You can build a context string and ask the model to cite element IDs, then map citations back to bounding boxes — which is exactly the VAG pipeline in `src/vag_dataset/`.

```python
context = "\n".join(
    f"[{e['element_index']} p{e['page']}] {e['text']}"
    for e in elements
)
# Pass `context` as part of your LLM prompt.
# The model cites element indices; map them back to (page, bbox) using `elements`.
```

### 5. Retrieve a page image for a multimodal model

```python
img_bytes = httpx.get(f"{BASE}/pages/{page_id}/image").content
# Encode as base64 and pass to a vision model.
```
