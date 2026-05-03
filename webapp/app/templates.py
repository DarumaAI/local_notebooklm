import time
from pathlib import Path

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
templates.env.globals["static_v"] = str(int(time.time()))
