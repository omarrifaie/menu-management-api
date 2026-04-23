"""Launch the API under uvicorn using values from :class:`Settings`.

Mostly a convenience so "how do I run this?" has a single answer::

    python -m scripts.serve

The equivalent raw command is ``uvicorn app.main:app --host $APP_HOST
--port $APP_PORT``; this wrapper just reads those fields through the
settings object so a populated ``.env`` is enough.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import uvicorn  # noqa: E402

from app.config import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )


if __name__ == "__main__":
    main()
