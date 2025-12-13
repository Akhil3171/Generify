"""Planner module: Breaks down user goals into sub-tasks using Gemini API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables (try .env file, but env vars take precedence)
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Initialize Gemini client (lazy - only when needed)
def _get_api_key() -> str:
    """Get API key from environment variables (like ADK does)."""
    # Check environment variables first (works with global env vars)
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY not found in environment variables. "
            "Please set GOOGLE_API_KEY as an environment variable or create a .env file."
        )
    return api_key

def _configure_genai():
    """Configure Gemini API."""
    api_key = _get_api_key()
    genai.configure(api_key=api_key)


class Planner:
    """Breaks down user queries into structured sub-tasks."""

    def __init__(self, model: str = "gemini-2.0-flash-exp"):
        self.model = model

    def build_plan(self, user_input: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Analyze user input and create a structured plan.
        
        Args:
            user_input: User's query/question
            context: Optional context from memory
            
        Returns:
            Dictionary with plan structure:
            {
                "drug_name": str,
                "strength": str | None,
                "dosage_form": str | None,
                "tasks": List[str]  # Ordered list of sub-tasks
            }
        """
        planning_prompt = f"""You are a task planner for a drug cost comparison agent.

User query: "{user_input}"

Your job is to extract key information and create a step-by-step plan.

Extract:
1. Drug name (brand or generic)
2. Strength (if mentioned)
3. Dosage form (if mentioned)

Then create a plan with these steps:
1. Get latest Medicare year available
2. Match drug identity in Orange Book
3. Find therapeutic equivalents
4. Lookup Medicare costs for each equivalent
5. Rank by cost and generate response

Return a JSON object with this structure:
{{
    "drug_name": "extracted drug name",
    "strength": "extracted strength or null",
    "dosage_form": "extracted form or null",
    "tasks": [
        "task 1 description",
        "task 2 description",
        ...
    ]
}}

Only return valid JSON, no additional text."""

        try:
            _configure_genai()  # Ensure API is configured
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(planning_prompt)
            
            # Parse JSON response
            import json
            plan_text = response.text.strip()
            # Remove markdown code blocks if present
            if plan_text.startswith("```"):
                plan_text = plan_text.split("```")[1]
                if plan_text.startswith("json"):
                    plan_text = plan_text[4:]
            plan_text = plan_text.strip()
            
            plan = json.loads(plan_text)
            
            # Ensure required fields
            plan.setdefault("drug_name", "")
            plan.setdefault("strength", None)
            plan.setdefault("dosage_form", None)
            plan.setdefault("tasks", [])
            
            return plan
            
        except Exception as e:
            # Fallback: simple extraction without LLM
            return self._simple_plan(user_input)

    def _simple_plan(self, user_input: str) -> Dict[str, Any]:
        """Fallback planner that extracts basic info without LLM."""
        # Simple keyword extraction
        drug_name = user_input.strip()
        strength = None
        dosage_form = None
        
        # Try to extract strength (numbers with mg/mg/ml/etc)
        import re
        strength_match = re.search(r'(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|%|units?)', user_input, re.IGNORECASE)
        if strength_match:
            strength = strength_match.group(0)
        
        # Try to extract dosage form
        forms = ['tablet', 'capsule', 'injection', 'cream', 'ointment', 'solution', 'suspension']
        for form in forms:
            if form.lower() in user_input.lower():
                dosage_form = form
                break
        
        return {
            "drug_name": drug_name,
            "strength": strength,
            "dosage_form": dosage_form,
            "tasks": [
                "Get latest Medicare year",
                "Match drug identity",
                "Find equivalents",
                "Lookup costs",
                "Rank and respond"
            ]
        }


def build_plan(user_input: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Convenience function to create a plan."""
    planner = Planner()
    return planner.build_plan(user_input, context)

