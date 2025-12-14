"""
Memory tools for drug query tracking
Author: Claude.ai at Yifon request after Plugin idea not trustable due to Google ADK ignoring custom runner
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Simple file-based storage
# Use Data folder (consistent with other data files)
_repo_root = Path(__file__).resolve().parents[2]
MEMORY_FILE = _repo_root / "Data" / "drug_memory.json"

def _load_memory() -> Dict:
    """Load memory from file"""
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    return {"queries": [], "drugs": {}}

def _save_memory(memory: Dict):
    """Save memory to file"""
    # Ensure Data directory exists
    MEMORY_FILE.parent.mkdir(exist_ok=True)
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)

def remember_drug_query(drug_name: str, dosage: str, result: str) -> Dict:
    """
    Remember a drug query for future reference.
    
    Args:
        drug_name: Name of the drug queried
        dosage: Dosage strength (e.g., "20mg")
        result: Summary of findings
    
    Returns:
        Confirmation of saved memory
    """
    memory = _load_memory()
    
    timestamp = datetime.now().isoformat()
    query_key = f"{drug_name.lower()}_{dosage}"
    
    # Add to queries list
    memory["queries"].append({
        "timestamp": timestamp,
        "drug": drug_name,
        "dosage": dosage,
        "result": result
    })
    
    # Update drug-specific memory
    if query_key not in memory["drugs"]:
        memory["drugs"][query_key] = {
            "first_queried": timestamp,
            "query_count": 0,
            "last_result": None
        }
    
    memory["drugs"][query_key].update({
        "query_count": memory["drugs"][query_key]["query_count"] + 1,
        "last_queried": timestamp,
        "last_result": result
    })
    
    _save_memory(memory)
    
    return {
        "ok": True,
        "message": f"Remembered query for {drug_name} {dosage}",
        "query_count": memory["drugs"][query_key]["query_count"]
    }

def recall_drug_query(drug_name: str, dosage: str) -> Dict:
    """
    Recall previous information about a drug query.
    
    Args:
        drug_name: Name of the drug
        dosage: Dosage strength
    
    Returns:
        Previous query information if available
    """
    memory = _load_memory()
    query_key = f"{drug_name.lower()}_{dosage}"
    
    if query_key in memory["drugs"]:
        drug_info = memory["drugs"][query_key]
        return {
            "ok": True,
            "found": True,
            "drug": drug_name,
            "dosage": dosage,
            "query_count": drug_info["query_count"],
            "last_queried": drug_info["last_queried"],
            "last_result": drug_info["last_result"]
        }
    else:
        return {
            "ok": True,
            "found": False,
            "message": f"No previous queries for {drug_name} {dosage}"
        }

def get_recent_queries(limit: int = 10) -> Dict:
    """
    Get recent drug queries for context.
    
    Args:
        limit: Maximum number of recent queries to return
    
    Returns:
        List of recent queries
    """
    memory = _load_memory()
    recent = memory["queries"][-limit:]
    
    return {
        "ok": True,
        "count": len(recent),
        "queries": recent
    }