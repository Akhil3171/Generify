"""
Generify Custom Runner with LoggingPlugin
Author: 2 files by Claude.ai combined into one by Yifon, debugged with Claude.ai
"""

import logging

# Configure logging FIRST - before any other imports
# Configure logging - SILENCE noisy loggers
logging.basicConfig(
    level=logging.INFO,  # Changed from DEBUG to INFO
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Silence specific noisy loggers
logging.getLogger('aiosqlite').setLevel(logging.WARNING)  # ← Silence SQLite
logging.getLogger('httpcore').setLevel(logging.WARNING)   # ← Silence HTTP
logging.getLogger('httpx').setLevel(logging.WARNING)      # ← Silence HTTP
logging.getLogger('google_adk.google.adk.cli').setLevel(logging.INFO)  # ← Less verbose

# Your loggers stay at INFO
logger = logging.getLogger(__name__)

from google.adk.runners import InMemoryRunner
# from google.adk.sessions import InMemorySessionService
# from google.adk.artifacts import InMemoryArtifactService

# Import from Google ADK their agent-level observability plugin
from google.adk.plugins import LoggingPlugin

# Import your agent
from drug_cost_agent.agent import root_agent

# Optional: Add token counter plugin
from google.adk.plugins import BasePlugin
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from typing import Optional

from src.plugins.token_budget_tracker import TokenBudgetTracker

class TokenCounterPlugin(BasePlugin):
    """Simple token counter"""
    def __init__(self):
        super().__init__(name="token_counter")  # ✅ Add name parameter
        print("🔢 TokenCounterPlugin initialized!")

    
    async def after_model_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_response: LlmResponse
    ) -> Optional[LlmResponse]:
        print("🔢 TokenCounterPlugin.after_model_callback CALLED!")  # Debug

        if llm_response.usage_metadata:
            tokens = llm_response.usage_metadata.total_token_count or 0
            print(f"🔢 Tokens used: {tokens}")  # Use print, not logger
            logger.info(f"🔢 Tokens used: {tokens}")
        return None

print("🚀 CUSTOM RUNNER.PY IS LOADING!")

def create_runner():
    """
    Create and configure the runner with plugins
    This function is called by ADK web interface
    """

    print("🔧 Creating custom runner with plugins...")   

    # Create plugins FIRST (before using them!)
    logging_plugin = LoggingPlugin()
    print(f"✅ LoggingPlugin created: {logging_plugin}")

    token_counter = TokenCounterPlugin()
    print(f"✅ TokenCounterPlugin created: {token_counter}")

    token_tracker = TokenBudgetTracker(
        history_file="data/token_usage_history.json",
        buffer_multiplier=1.5,
        percentile_threshold=95
    )
    print(f"✅ TokenBudgetTracker created: {token_tracker}")

    
    print("✅ Plugins created")

    # Create runner (simpler API in your ADK version)
    runner = InMemoryRunner(
        agent=root_agent,
        plugins=[logging_plugin, token_counter, token_tracker]  # ✅ Pass plugins here
    )
    print(f"✅ Runner created with {len([logging_plugin, token_counter, token_tracker])} plugins")

    # Initialize services
#    session_service = InMemorySessionService()
#    artifact_service = InMemoryArtifactService()
    
    # Create runner
#    runner = InMemoryRunner(
#        agent=root_agent,
#        session_service=session_service,
#        artifact_service=artifact_service
#    )
    
    # Register LoggingPlugin
#    logging_plugin = LoggingPlugin()
#    runner.register_plugin(logging_plugin)

#    print("✅ LoggingPlugin registered")

    # Register token counter
#    token_counter = TokenCounterPlugin()
#    runner.register_plugin(token_counter)
    
#    print("✅ TokenCounter registered")
    
    return runner

# ADK looks for this
runner = create_runner()

# Also export as __all__ for explicit discovery
__all__ = ['runner']

print("✅ Custom runner created and exported!") 