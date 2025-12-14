"""Agent Core: Main workflow orchestrator following the agent architecture pattern."""

from __future__ import annotations

from typing import Any, Dict

from src.executor import Executor
from src.memory import (
    get_memory,
    retrieve_from_session,
    store_session,
)
from src.planner import Planner


class AgentCore:
    """Core agent that orchestrates the workflow: Plan → Execute → Respond."""

    def __init__(self, use_memory: bool = True):
        self.planner = Planner()
        self.executor = Executor()
        self.use_memory = use_memory
        self.memory = get_memory() if use_memory else None

    def process_user_input(self, user_input: str, session_id: str | None = None) -> str:
        """
        Main entry point: Process user input through the agent workflow.
        
        Workflow:
        1. Receive user input
        2. (Optional) Retrieve relevant memory
        3. Plan sub-tasks
        4. Execute plan (call tools/APIs)
        5. Generate final response
        6. (Optional) Store in memory
        
        Args:
            user_input: User's query/question
            session_id: Optional session ID for session-based memory
            
        Returns:
            Final response string
        """
        # Step 1: Receive user input (already done)
        
        # Step 2: Retrieve relevant memory (optional)
        context = None
        if self.use_memory and self.memory and session_id:
            past_interactions = retrieve_from_session(session_id, user_input, limit=3)
            if past_interactions:
                context = {
                    "past_interactions": past_interactions,
                    "similar_queries": [p.get("user_input") for p in past_interactions],
                }
        
        # Step 3: Plan sub-tasks
        try:
            plan = self.planner.build_plan(user_input, context)
        except Exception as e:
            return f"I encountered an error while planning: {str(e)}. Please try rephrasing your query."
        
        # Step 4: Execute plan (call tools/APIs)
        try:
            results = self.executor.execute(plan)
        except Exception as e:
            return f"I encountered an error while executing: {str(e)}. Please check your query and try again."
        
        # Step 5: Generate final response
        if results.get("ok") is False:
            return results.get("final_response", "I encountered an error processing your request.")
        
        final_response = results.get("final_response")
        if not final_response:
            final_response = "I processed your request but couldn't generate a response. Please try again."
        
        # Step 6: Store in memory (optional)
        if self.use_memory and self.memory and session_id:
            try:
                store_session(session_id, user_input, results, final_response)
            except Exception:
                pass  # Don't fail if memory storage fails
        
        return final_response


def process_user_input(user_input: str, session_id: str | None = None, use_memory: bool = True) -> str:
    """
    Convenience function to process user input.
    
    Args:
        user_input: User's query
        session_id: Optional session ID for session-based memory
        use_memory: Whether to use memory (default: True)
        
    Returns:
        Agent's response
    """
    agent = AgentCore(use_memory=use_memory)
    return agent.process_user_input(user_input, session_id=session_id)

