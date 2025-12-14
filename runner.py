"""
Generify Custom Runner with LoggingPlugin
This file is used by: adk web --runner runner.py
Author: 2 files by Claude.ai combined into one by Yifon
"""

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
import logging

logger = logging.getLogger(__name__)

class TokenCounterPlugin(BasePlugin):
    """Simple token counter"""
    def __init__(self):
        super().__init__(name="token_counter")  # ✅ Add name parameter
    
    async def after_model_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_response: LlmResponse
    ) -> Optional[LlmResponse]:
        if llm_response.usage_metadata:
            tokens = llm_response.usage_metadata.total_token_count or 0
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
    token_counter = TokenCounterPlugin()
    
    print("✅ Plugins created")

    # Create runner (simpler API in your ADK version)
    runner = InMemoryRunner(
        agent=root_agent,
        plugins=[logging_plugin, token_counter]  # ✅ Pass plugins here
    )

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

print("✅ Custom runner created and exported!") 