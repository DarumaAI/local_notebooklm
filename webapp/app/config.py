import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
PAGES_DIR = Path(os.getenv("PAGES_DIR", "pages"))
DB_PATH = os.getenv("DB_PATH", "app.db")
RASTER_DPI = int(os.getenv("RASTER_DPI", "150"))
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
VLLM_MODEL = os.getenv("VLLM_MODEL", "ibm-granite/granite-docling-258M")
VLLM_TIMEOUT = float(os.getenv("VLLM_TIMEOUT", "120.0"))
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Directory of pre-parsed JSON files from Colab (keyed by arXiv ID, e.g. "2602.05143v1.json")
_default_parsed = Path(__file__).parent.parent.parent.parent / "data" / "parsed_documents"
PARSED_DOCS_DIR = Path(os.getenv("PARSED_DOCS_DIR", str(_default_parsed)))

UPLOAD_DIR.mkdir(exist_ok=True)
PAGES_DIR.mkdir(exist_ok=True)
