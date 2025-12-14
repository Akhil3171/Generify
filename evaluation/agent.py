# Minimal evaluation/agent.py — must expose a module-level symbol named `root_agent`.
# This loads the test_cases JSON (provided separately) and exposes it so the ADK loader
# finds `root_agent` and the process can continue.
#
# Replace or expand this with a real ADK Agent/Runner object later if required.

from pathlib import Path
import json

_here = Path(__file__).parent
_tests_path = _here / "test_cases.json"

if _tests_path.exists():
    with _tests_path.open("r", encoding="utf-8") as fh:
        test_suite = json.load(fh)
else:
    test_suite = {
        "name": "Generify Evaluation Set (placeholder)",
        "description": "No test_cases.json found in evaluation/ — replace with real tests.",
        "test_cases": []
    }

# The ADK loader looks for a top-level symbol named `root_agent`.
# For now we expose a plain dict containing the test suite. If the ADK requires a specific
# Agent/Runner class later, replace this dict with the appropriate object.
root_agent = {
    "name": test_suite.get("name", "evaluation"),
    "description": test_suite.get("description", ""),
    "test_suite": test_suite.get("test_cases", [])
}