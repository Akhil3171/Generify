"""Memory module: Stores and retrieves conversation context with session support."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import uuid


class SessionMemory:
    """Session-based memory storage with persistence to disk."""

    def __init__(self, storage_file: str | None = None):
        """
        Initialize session memory.
        
        Args:
            storage_file: Path to JSON file for persistence. If None, uses default.
        """
        if storage_file is None:
            # Default: store in Data/sessions.json
            repo_root = Path(__file__).resolve().parents[1]
            data_dir = repo_root / "Data"
            data_dir.mkdir(exist_ok=True)
            storage_file = str(data_dir / "sessions.json")
        
        self.storage_file = storage_file
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._load_sessions()

    def _load_sessions(self) -> None:
        """Load sessions from disk."""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    self.sessions = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.sessions = {}

    def _save_sessions(self) -> None:
        """Save sessions to disk."""
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self.sessions, f, indent=2, ensure_ascii=False)
        except IOError:
            pass  # Don't fail if save fails

    def get_or_create_session(self, session_id: str) -> Dict[str, Any]:
        """Get existing session or create a new one."""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "session_id": session_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "interactions": [],
            }
            self._save_sessions()
        return self.sessions[session_id]

    def store(
        self,
        session_id: str,
        user_input: str,
        results: Dict[str, Any],
        response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Store a conversation interaction in a session.
        
        Args:
            session_id: Unique session identifier
            user_input: User's query
            results: Execution results
            response: Final response text
            metadata: Optional additional metadata
        """
        session = self.get_or_create_session(session_id)
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "response": response,
            "drug_name": results.get("plan", {}).get("drug_name"),
            "identity": results.get("identity"),
            "cost_data": results.get("cost_data", [])[:5],  # Store top 5
            "metadata": metadata or {},
        }
        
        session["interactions"].append(entry)
        session["updated_at"] = datetime.now().isoformat()
        
        # Limit interactions per session
        max_interactions = 50
        if len(session["interactions"]) > max_interactions:
            session["interactions"] = session["interactions"][-max_interactions:]
        
        self._save_sessions()

    def get_session(self, session_id: str) -> Dict[str, Any] | None:
        """Get a specific session by ID."""
        return self.sessions.get(session_id)

    def list_sessions(self, limit: int = 50, last_24h_only: bool = False) -> List[Dict[str, Any]]:
        """
        List all sessions, sorted by most recent.
        
        Args:
            limit: Maximum number of sessions to return
            last_24h_only: If True, only include sessions with interactions in last 24 hours
            
        Returns:
            List of session summaries
        """
        cutoff_time = datetime.now() - timedelta(hours=24) if last_24h_only else None
        
        sessions_list = []
        for session_id, session_data in self.sessions.items():
            interactions = session_data.get("interactions", [])
            
            # Filter to last 24h if requested
            if last_24h_only and cutoff_time:
                recent_interactions = [
                    i for i in interactions
                    if i.get("timestamp") and datetime.fromisoformat(i.get("timestamp", "")) >= cutoff_time
                ]
                if not recent_interactions:
                    continue  # Skip sessions with no recent interactions
                interactions = recent_interactions
            
            if not interactions:
                continue
            
            sessions_list.append({
                "session_id": session_id,
                "created_at": session_data.get("created_at"),
                "updated_at": session_data.get("updated_at"),
                "interaction_count": len(interactions),
                "first_query": interactions[0].get("user_input", "") if interactions else "",
                "last_query": interactions[-1].get("user_input", "") if interactions else "",
            })
        
        # Sort by updated_at, most recent first
        sessions_list.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return sessions_list[:limit]

    def retrieve_from_session(self, session_id: str, user_input: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve relevant past interactions from a specific session within last 24 hours.
        
        Args:
            session_id: Session to search in
            user_input: Current user query
            limit: Maximum number of entries to return
            
        Returns:
            List of relevant past interactions from last 24 hours
        """
        session = self.get_session(session_id)
        if not session or not session.get("interactions"):
            return []
        
        # Filter to last 24 hours
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        # Simple keyword matching
        user_lower = user_input.lower()
        relevant = []
        
        interactions = session["interactions"]
        for entry in reversed(interactions):  # Most recent first
            # Check if entry is within last 24 hours
            entry_time_str = entry.get("timestamp", "")
            if entry_time_str:
                try:
                    entry_time = datetime.fromisoformat(entry_time_str)
                    if entry_time < cutoff_time:
                        continue  # Skip entries older than 24 hours
                except (ValueError, TypeError):
                    pass  # If timestamp parsing fails, include it anyway
            
            entry_input = entry.get("user_input", "").lower()
            drug_name = entry.get("drug_name", "").lower()
            
            # Check if any keywords match
            if any(word in entry_input or word in drug_name for word in user_lower.split() if len(word) > 3):
                relevant.append(entry)
                if len(relevant) >= limit:
                    break
        
        return relevant
    
    def get_recent_24h(self, session_id: str | None = None) -> List[Dict[str, Any]]:
        """
        Get all interactions from the last 24 hours.
        
        Args:
            session_id: Optional session ID. If None, returns from all sessions.
            
        Returns:
            List of all interactions from last 24 hours
        """
        cutoff_time = datetime.now() - timedelta(hours=24)
        recent_interactions = []
        
        if session_id:
            # Get from specific session
            session = self.get_session(session_id)
            if session:
                interactions = session.get("interactions", [])
                for entry in interactions:
                    entry_time_str = entry.get("timestamp", "")
                    if entry_time_str:
                        try:
                            entry_time = datetime.fromisoformat(entry_time_str)
                            if entry_time >= cutoff_time:
                                recent_interactions.append(entry)
                        except (ValueError, TypeError):
                            pass
        else:
            # Get from all sessions
            for session_data in self.sessions.values():
                interactions = session_data.get("interactions", [])
                for entry in interactions:
                    entry_time_str = entry.get("timestamp", "")
                    if entry_time_str:
                        try:
                            entry_time = datetime.fromisoformat(entry_time_str)
                            if entry_time >= cutoff_time:
                                recent_interactions.append(entry)
                        except (ValueError, TypeError):
                            pass
        
        # Sort by timestamp, most recent first
        recent_interactions.sort(
            key=lambda x: datetime.fromisoformat(x.get("timestamp", "1970-01-01")),
            reverse=True
        )
        
        return recent_interactions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._save_sessions()
            return True
        return False


# Global memory instance
_memory_instance: Optional[SessionMemory] = None


def get_memory() -> SessionMemory:
    """Get the global memory instance."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = SessionMemory()
    return _memory_instance


def store_session(
    session_id: str,
    user_input: str,
    results: Dict[str, Any],
    response: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Convenience function to store memory in a session."""
    get_memory().store(session_id, user_input, results, response, metadata)


def retrieve_from_session(session_id: str, user_input: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Convenience function to retrieve memory from a session (last 24 hours)."""
    return get_memory().retrieve_from_session(session_id, user_input, limit)


def get_recent_24h(session_id: str | None = None) -> List[Dict[str, Any]]:
    """Convenience function to get all interactions from last 24 hours."""
    return get_memory().get_recent_24h(session_id)


def get_session(session_id: str) -> Dict[str, Any] | None:
    """Get a specific session."""
    return get_memory().get_session(session_id)


def list_sessions(limit: int = 50, last_24h_only: bool = False) -> List[Dict[str, Any]]:
    """List all sessions. Set last_24h_only=True to filter to sessions with interactions in last 24 hours."""
    return get_memory().list_sessions(limit, last_24h_only)

