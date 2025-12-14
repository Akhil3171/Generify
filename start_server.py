"""
Start ADK web server for Generify Drug Cost Agent
Author: Claude.ai upon request for reversion and silencing extra logs by Yifon
"""

import logging
from pathlib import Path

# Configure logging - reduce noise
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Silence noisy loggers
logging.getLogger('aiosqlite').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

print("\n🚀 Importing runner...")
import runner

print("🚀 Creating FastAPI app...")
from google.adk.cli.fast_api import get_fast_api_app

app = get_fast_api_app(
    agents_dir=str(Path.cwd()),
    web=True
)

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting server on http://127.0.0.1:8000...")
    print("💊 Generify Drug Cost Agent ready!")
    print("📊 Use 'adk eval' for token tracking and evaluation\n")
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )