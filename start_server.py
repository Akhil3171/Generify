"""
Start ADK web server with custom runner
Author: Claude.ai and debugged with input from Yifon and Claude.ai
"""

import uvicorn
from pathlib import Path

# Import runner to ensure it's loaded
print("🚀 Loading custom runner...")
from runner import runner

# Get the FastAPI app
from google.adk.cli.fast_api import get_fast_api_app

print("🚀 Creating FastAPI app...")
app = get_fast_api_app(
    agents_dir=str(Path.cwd()),  # Current directory
    web=True,  # Enable web interface
    reload_agents=True  # Hot reload during development
)

if __name__ == "__main__":
    print("🚀 Starting server on http://127.0.0.1:8000...")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )