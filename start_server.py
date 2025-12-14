"""
Start ADK web server - relies on auto-discovery of runner.py
Author: Claude.ai
"""

import logging
from pathlib import Path

# Reduce log noise
logging.getLogger('aiosqlite').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

print("\n🚀 Importing runner to ensure it's loaded...")
# This import triggers runner.py to execute and create the runner
import runner  # ← Just import the module

print("🚀 Creating FastAPI app...")
from google.adk.cli.fast_api import get_fast_api_app

app = get_fast_api_app(
    agents_dir=str(Path.cwd()),
    web=True
)

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting server on http://127.0.0.1:8000...\n")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )