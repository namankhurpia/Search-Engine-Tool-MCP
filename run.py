#!/usr/bin/env python
"""Dev entrypoint — runs the Insight Engine on http://127.0.0.1:8000."""
import sys
from pathlib import Path

# Ensure the src directory is on the path so uvicorn's reloader subprocess
# can find the `insight` package even without an editable install.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        "insight.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
