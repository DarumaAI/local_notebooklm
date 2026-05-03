# PLAN.md — VAG Study Tool Web Interface

A NotebookLM-style study tool: upload PDFs, rasterise pages, run Granite-Docling OCR, browse extracted text with bounding-box overlays.

---

## 1. High-level Architecture

```
Browser (HTMX)
    │
    ▼
FastAPI (app/)
    ├── Routers        — HTTP endpoints
    ├── Services       — pdf_processor, docling_service, storage
    ├── Background Tasks — pipeline orchestration
    └── Templates      — Jinja2 + HTMX partials
    │
    ▼
SQLite (app.db)        — documents, pages, elements
    │
Filesystem
    ├── uploads/       — original PDFs
    └── pages/         — rasterised PNGs (one per page)
```

---

## 2. Repository Layout

```
webapp/
├── app/
│   ├── main.py                     # app factory, lifespan, router mounts
│   ├── config.py                   # Settings: paths, DPI, vLLM base URL
│   ├── database.py                 # SQLite engine + session factory
│   ├── models.py                   # SQLAlchemy ORM tables
│   ├── schemas.py                  # Pydantic response schemas
│   ├── routers/
│   │   ├── documents.py            # upload / list / get / status
│   │   ├── pages.py                # serve page image, elements
│   │   └── ui.py                   # HTML routes for HTMX
│   ├── services/
│   │   ├── pdf_processor.py        # PyMuPDF: PDF → PNG per page
│   │   ├── docling_service.py      # vLLM call → structured JSON
│   │   └── storage.py              # write Page + Element rows to DB
│   ├── tasks/
│   │   └── pipeline.py             # orchestrates the 3 services above
│   └── templates/
│       ├── base.html
│       ├── index.html              # upload form + document list
│       ├── document.html           # page viewer + element sidebar
│       └── partials/
│           ├── document_card.html  # single document row (status badge)
│           ├── status_badge.html   # polled by HTMX until "done"
│           └── page_viewer.html    # canvas + bbox overlay
├── static/
│   ├── css/style.css
│   └── js/bbox.js                  # draws bboxes on <canvas>
├── uploads/                        # git-ignored
├── pages/                          # git-ignored
├── requirements.txt
└── PLAN.md                         # this file
```

---

## 3. Database Schema

### `documents`
| column        | type    | notes                                      |
|---------------|---------|--------------------------------------------|
| id            | INTEGER | primary key                                |
| filename      | TEXT    | UUID-prefixed name on disk                 |
| original_name | TEXT    | user-facing filename                       |
| status        | TEXT    | pending → processing → done / error        |
| page_count    | INTEGER | filled after rasterisation                 |
| error_message | TEXT    | nullable                                   |
| created_at    | TEXT    | ISO-8601                                   |
| updated_at    | TEXT    | ISO-8601                                   |

### `pages`
| column      | type    | notes                        |
|-------------|---------|------------------------------|
| id          | INTEGER | primary key                  |
| document_id | INTEGER | FK → documents.id            |
| page_number | INTEGER | 1-indexed                    |
| image_path  | TEXT    | relative path to PNG         |

### `elements`
| column         | type    | notes                                        |
|----------------|---------|----------------------------------------------|
| id             | INTEGER | primary key                                  |
| page_id        | INTEGER | FK → pages.id                                |
| element_index  | INTEGER | order within page                            |
| text           | TEXT    |                                              |
| classification | TEXT    | e.g. "text", "title", "figure", "table"      |
| x0, y0, x1, y1 | REAL   | normalised [0, 1] floats (relative to page)  |

SQLite is opened in WAL mode so reads do not block the background writer.

---

## 4. API Endpoints

| Method | Path                         | Description                                 |
|--------|------------------------------|---------------------------------------------|
| GET    | `/`                          | Main UI (document list + upload form)       |
| POST   | `/documents/upload`          | Accept PDF multipart, enqueue pipeline      |
| GET    | `/documents`                 | JSON list of all documents                  |
| GET    | `/documents/{id}`            | JSON: document + pages + elements           |
| GET    | `/documents/{id}/status`     | HTMX partial: current status badge         |
| GET    | `/documents/{id}/view`       | HTML: full document viewer page             |
| GET    | `/pages/{page_id}/image`     | Serve rasterised PNG                        |
| GET    | `/pages/{page_id}/elements`  | JSON: elements for one page                 |

---

## 5. Background Pipeline (`tasks/pipeline.py`)

```
process_document(document_id)
    │
    ├─ 1. pdf_processor.rasterise(pdf_path, out_dir, dpi=150)
    │       → List[PageImage]  (page_number, image_path)
    │       update Document.page_count, status="processing"
    │
    ├─ 2. for each PageImage:
    │       docling_service.parse(image_path)
    │       → List[ElementData]  (text, classification, bbox)
    │
    ├─ 3. storage.persist(document_id, pages_with_elements)
    │       → insert Page + Element rows
    │
    └─ 4. update Document.status = "done"
         (or "error" + error_message on any exception)
```

FastAPI `BackgroundTasks` is used to enqueue `process_document` at upload time. No external queue is required for a single-server setup.

---

## 6. Services

### `pdf_processor.py`
- Uses `pymupdf` (`fitz`).
- Renders each page at `config.RASTER_DPI` (default 150).
- Saves `pages/{document_id}/{page_number:04d}.png`.
- Returns `List[PageImage]`.

### `docling_service.py`
- Sends each PNG to the Granite-Docling vLLM endpoint via HTTP.
- Endpoint: `config.VLLM_BASE_URL` (e.g. `http://localhost:8000/v1`).
- Model: `ibm-granite/granite-docling-258M`.
- Parses the response into `List[ElementData]`.
- Coordinates are expected in normalised [0, 1] space; a helper converts if needed.

### `storage.py`
- Takes `(document_id, List[PageResult])` and bulk-inserts rows.
- Uses a single transaction per document for atomicity.

---

## 7. Frontend (HTMX + Jinja2)

### `index.html` — Upload + Document List
- Drag-and-drop PDF upload form (`hx-post="/documents/upload"`, `hx-target="#doc-list"`).
- Document list renders status badges.
- Each badge polls itself: `hx-get="/documents/{id}/status"` `hx-trigger="every 2s"` while status is not `done` or `error`.

### `document.html` — Viewer
- Left panel: page thumbnails (click to navigate).
- Centre panel: full-size page image inside a `<div>` with an absolutely-positioned `<canvas>` overlay.
- Right panel: text element list; hovering an element highlights its bbox on the canvas.
- `static/js/bbox.js` receives element data as a JSON blob embedded in the page and draws semi-transparent rectangles on the canvas.

---

## 8. Configuration (`config.py`)

```python
UPLOAD_DIR   = "uploads/"
PAGES_DIR    = "pages/"
DB_PATH      = "app.db"
RASTER_DPI   = 150
VLLM_BASE_URL = "http://localhost:8000/v1"
VLLM_MODEL   = "ibm-granite/granite-docling-258M"
```

All values overridable via environment variables / `.env`.

---

## 9. `requirements.txt` (additions to existing deps)

```
fastapi
uvicorn[standard]
python-multipart       # file uploads
sqlalchemy
pymupdf                # PDF rasterisation
httpx                  # async HTTP to vLLM
jinja2
python-dotenv
```

---

## 10. Implementation Order

1. **Scaffold** — `main.py`, `config.py`, `database.py`, `models.py`
2. **Storage service** — ORM models + `storage.py`
3. **PDF processor** — `pdf_processor.py` + unit test with a sample PDF
4. **Docling service** — `docling_service.py` + mock/stub for offline testing
5. **Pipeline task** — wire the three services in `pipeline.py`
6. **API routers** — `documents.py`, `pages.py`
7. **Base UI** — `base.html`, `index.html`, upload + list flow
8. **Document viewer** — `document.html`, `bbox.js`, bbox overlay
9. **Polish** — error states, loading spinners, status badges
10. **Integration test** — upload a real arXiv PDF end-to-end

---

## 11. Key Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Task queue | FastAPI `BackgroundTasks` | Zero extra infrastructure; single server |
| DB | SQLite (WAL mode) | Simple, file-based, no server needed |
| Coordinates | normalised [0, 1] floats | Consistent with existing `src/vag_dataset/models.py` |
| DPI | 150 | Good OCR accuracy; ~1 MB/page PNG |
| Polling | HTMX `every 2s` | No WebSocket complexity; stops when done |
| Bbox overlay | `<canvas>` via JS | No external mapping libs required |
