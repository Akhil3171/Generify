"""
Token Budget Tracker - Learns normal token usage and sets dynamic limits
Author: Claude.ai
"""

import logging
import json
from typing import Optional, Dict, List
from pathlib import Path
import statistics

from google.adk.plugins import BasePlugin
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse

logger = logging.getLogger(__name__)


class TokenBudgetTracker(BasePlugin):
    
    """
    Tracks token usage across requests and calculates dynamic limits
    based on observed normal range (excluding outliers)
    """
    
    def __init__(
        self, 
        history_file: str = "token_usage_history.json",
        buffer_multiplier: float = 1.5,
        percentile_threshold: float = 95.0
    ):
        # Call parent __init__ with name parameter
        super().__init__(name="token_budget_tracker")  # ✅ Add this line
        
        # Rest of your existing code...
        self.history_file = Path(history_file)
        self.buffer_multiplier = buffer_multiplier
        self.percentile_threshold = percentile_threshold

        """
        Args:
            history_file: Where to store token usage history
            buffer_multiplier: How much buffer to add (1.5 = 150% of P95)
            percentile_threshold: Percentile for "normal" range (95 = ignore top 5%)
        """

            # IMPORTANT: Call parent with name parameter
        super().__init__(name="token_budget_tracker")
    
        self.history_file = Path(history_file)
        self.buffer_multiplier = buffer_multiplier
        self.percentile_threshold = percentile_threshold
        
        # Load existing history
        self.token_history: List[Dict] = self._load_history()
        
        # Current session tracking
        self.session_tokens: Dict[str, List[int]] = {}
    
    def _load_history(self) -> List[Dict]:
        """Load token usage history from file"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                logger.info(f"📊 Loaded {len(data)} historical token records")
                return data
            except Exception as e:
                logger.warning(f"Could not load history: {e}")
                return []
        return []
    
    def _save_history(self):
        """Save token usage history to file"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.token_history, f, indent=2)
            logger.debug(f"💾 Saved token history to {self.history_file}")
        except Exception as e:
            logger.error(f"Failed to save history: {e}")
    
    def get_dynamic_limit(self, query_type: str = "default") -> int:
        """
        Calculate dynamic token limit based on historical data
        
        Args:
            query_type: Type of query (e.g., "simple", "complex", "image")
        
        Returns:
            Recommended token limit (P95 + buffer)
        """
        if not self.token_history:
            logger.warning("⚠️ No historical data, using default limit of 5000")
            return 5000
        
        # Filter by query type if specified
        relevant_tokens = [
            record["tokens"] 
            for record in self.token_history 
            if query_type == "default" or record.get("query_type") == query_type
        ]
        
        if not relevant_tokens:
            logger.warning(f"⚠️ No data for {query_type}, using all data")
            relevant_tokens = [r["tokens"] for r in self.token_history]
        
        # Calculate statistics
        mean = statistics.mean(relevant_tokens)
        median = statistics.median(relevant_tokens)
        stdev = statistics.stdev(relevant_tokens) if len(relevant_tokens) > 1 else 0
        
        # Calculate percentile (remove outliers)
        sorted_tokens = sorted(relevant_tokens)
        percentile_idx = int(len(sorted_tokens) * (self.percentile_threshold / 100))
        p95_value = sorted_tokens[min(percentile_idx, len(sorted_tokens) - 1)]
        
        # Add buffer
        dynamic_limit = int(p95_value * self.buffer_multiplier)
        
        logger.info(
            f"📊 Token Stats ({query_type}): "
            f"Mean={mean:.0f}, Median={median:.0f}, "
            f"P{self.percentile_threshold}={p95_value}, "
            f"Dynamic Limit={dynamic_limit} (P{self.percentile_threshold} × {self.buffer_multiplier})"
        )
        
        return dynamic_limit
    
    def get_statistics(self) -> Dict:
        """Get comprehensive token usage statistics"""
        if not self.token_history:
            return {"error": "No historical data"}
        
        all_tokens = [r["tokens"] for r in self.token_history]
        sorted_tokens = sorted(all_tokens)
        
        return {
            "total_requests": len(self.token_history),
            "mean": statistics.mean(all_tokens),
            "median": statistics.median(all_tokens),
            "min": min(all_tokens),
            "max": max(all_tokens),
            "stdev": statistics.stdev(all_tokens) if len(all_tokens) > 1 else 0,
            "p50": sorted_tokens[len(sorted_tokens) // 2],
            "p75": sorted_tokens[int(len(sorted_tokens) * 0.75)],
            "p90": sorted_tokens[int(len(sorted_tokens) * 0.90)],
            "p95": sorted_tokens[int(len(sorted_tokens) * 0.95)],
            "p99": sorted_tokens[int(len(sorted_tokens) * 0.99)],
            "recommended_limit": self.get_dynamic_limit()
        }
    
    async def after_model_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_response: LlmResponse
    ) -> Optional[LlmResponse]:
        """Track tokens after each LLM call"""
        
        if not llm_response.usage_metadata:
            return None
        
        tokens = llm_response.usage_metadata.total_token_count or 0
        session_id = callback_context.invocation_context.session.id
        
        # Track in current session
        if session_id not in self.session_tokens:
            self.session_tokens[session_id] = []
        self.session_tokens[session_id].append(tokens)
        
        # Determine query type (you can make this smarter)
        state = callback_context.invocation_context.state
        query_type = state.get("query_type", "default")
        
        # Add to history
        record = {
            "tokens": tokens,
            "query_type": query_type,
            "session_id": session_id,
            "agent_name": callback_context.invocation_context.agent.name,
            "timestamp": callback_context.invocation_context.session.updated_at.isoformat() if callback_context.invocation_context.session.updated_at else None
        }
        
        self.token_history.append(record)
        
        # Log current usage vs limit
        dynamic_limit = self.get_dynamic_limit(query_type)
        percentage = (tokens / dynamic_limit) * 100
        
        logger.info(
            f"🔢 Tokens: {tokens} "
            f"({percentage:.1f}% of dynamic limit {dynamic_limit})"
        )
        
        # Store in session state for agent to see
        if "token_tracking" not in callback_context.invocation_context.state:
            callback_context.invocation_context.state["token_tracking"] = {
                "total_tokens": 0,
                "request_count": 0,
                "dynamic_limit": dynamic_limit
            }
        
        tracking = callback_context.invocation_context.state["token_tracking"]
        tracking["total_tokens"] += tokens
        tracking["request_count"] += 1
        tracking["dynamic_limit"] = dynamic_limit
        
        return None
    
    async def after_run_callback(self, *, invocation_context) -> None:
        """Save history after each run"""
        self._save_history()
        
        # Log session summary
        tracking = invocation_context.state.get("token_tracking", {})
        if tracking:
            logger.info(
                f"📊 Session Complete: "
                f"{tracking['total_tokens']} tokens in {tracking['request_count']} requests "
                f"(Limit: {tracking.get('dynamic_limit', 'N/A')})"
            )
    
    def export_limits_for_evaluation(self, output_file: str = "evaluation_limits.json"):
        """Export calculated limits for use in evaluation config"""
        limits = {
            "default": self.get_dynamic_limit("default"),
            "simple": self.get_dynamic_limit("simple"),
            "complex": self.get_dynamic_limit("complex"),
            "image": self.get_dynamic_limit("image"),
            "statistics": self.get_statistics()
        }
        
        with open(output_file, 'w') as f:
            json.dump(limits, f, indent=2)
        
        logger.info(f"📄 Exported limits to {output_file}")
        return limits