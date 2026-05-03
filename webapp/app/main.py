from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .database import SessionLocal, init_db
from .models import Document
from .routers import chat, documents, pages, ui

BASE_DIR = Path(__file__).parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _reset_stuck_documents()
    yield


def _reset_stuck_documents() -> None:
    session = SessionLocal()
    try:
        stuck = (
            session.query(Document)
            .filter(Document.status.in_(["pending", "processing"]))
            .all()
        )
        now = datetime.now(timezone.utc).isoformat()
        for doc in stuck:
            doc.status = "error"
            doc.error_message = "Interrupted: server was restarted during processing."
            doc.updated_at = now
        if stuck:
            session.commit()
    finally:
        session.close()


app = FastAPI(title="VAG Study Tool", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(ui.router)
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(pages.router, prefix="/pages", tags=["pages"])
app.include_router(chat.router, prefix="/documents", tags=["chat"])
