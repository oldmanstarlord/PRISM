"""FastAPI application package."""

import sys
from pathlib import Path

# Support `uvicorn app.main:app` when the working directory is backend/.
# All internal imports continue to use the canonical backend.app package.
if __name__ == "app":
    project_root = str(Path(__file__).resolve().parents[2])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
