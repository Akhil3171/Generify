"""Executor module: Executes planned tasks by calling tools and using Gemini for synthesis."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
import google.generativeai as genai

from src.tools_medicare import medicare_latest_year, medicare_lookup_costs
from src.tools_ob import (
    ob_find_equivalents,
    ob_ingredient_to_generic_candidates,
    ob_match_identity,
)

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


class Executor:
    """Executes planned tasks by orchestrating tool calls and LLM synthesis."""

    def __init__(self, model: str = "gemini-2.0-flash-exp"):
        self.model = model

    def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the planned tasks.
        
        Args:
            plan: Plan dictionary from planner with drug_name, strength, tasks, etc.
            
        Returns:
            Dictionary with execution results
        """
        drug_name = plan.get("drug_name", "")
        strength = plan.get("strength") or ""
        dosage_form = plan.get("dosage_form")
        
        results = {
            "plan": plan,
            "latest_year": None,
            "identity": None,
            "equivalents": [],
            "costs": {},
            "final_response": None,
        }
        
        try:
            # Step 1: Get latest Medicare year
            year_result = medicare_latest_year()
            if year_result.get("ok"):
                latest_year = year_result["latest_year"]
                results["latest_year"] = latest_year
            else:
                return self._error_response("Could not retrieve Medicare year data")
            
            # Step 2: Match drug identity
            identity_result = ob_match_identity(drug_name, strength)
            if not identity_result.get("ok"):
                return self._error_response(
                    f"Could not find drug '{drug_name}' in Orange Book. "
                    f"Error: {identity_result.get('error', 'Unknown error')}"
                )
            
            identity = identity_result["best"]
            results["identity"] = identity
            
            # Step 3: Find equivalents
            ingredient = identity.get("ingredient", "")
            strength_val = identity.get("strength", strength)
            form = identity.get("dosage_form", dosage_form or "")
            route = identity.get("route", "")
            
            equiv_result = ob_find_equivalents(
                ingredient=ingredient,
                strength=strength_val,
                dosage_form=form,
                route=route,
                te_a_only=True,
                limit=50,
            )
            
            if not equiv_result.get("ok") or not equiv_result.get("items"):
                return self._error_response("Could not find therapeutic equivalents")
            
            equivalents = equiv_result["items"]
            results["equivalents"] = equivalents
            
            # Step 4: Lookup costs for each equivalent
            cost_data = []
            for equiv in equivalents:
                trade_name = equiv.get("trade_name", "")
                if not trade_name:
                    continue
                
                cost_result = medicare_lookup_costs(trade_name, year=latest_year, limit=5)
                if cost_result.get("ok") and cost_result.get("items"):
                    costs = cost_result["items"]
                    # Get lowest cost
                    if costs:
                        lowest = min(costs, key=lambda x: x.get("avg_spend_per_dose", float("inf")))
                        cost_data.append({
                            "trade_name": trade_name,
                            "is_generic": equiv.get("is_generic", False),
                            "cost": lowest.get("avg_spend_per_dose"),
                            "manufacturer": lowest.get("manufacturer"),
                            "details": lowest,
                        })
                        results["costs"][trade_name] = lowest
            
            # If no costs found, try generic candidates fallback
            if not cost_data:
                generic_result = ob_ingredient_to_generic_candidates(ingredient)
                if generic_result.get("ok") and generic_result.get("candidates"):
                    for candidate in generic_result["candidates"][:5]:
                        cost_result = medicare_lookup_costs(candidate, year=latest_year, limit=5)
                        if cost_result.get("ok") and cost_result.get("items"):
                            costs = cost_result["items"]
                            if costs:
                                lowest = min(costs, key=lambda x: x.get("avg_spend_per_dose", float("inf")))
                                cost_data.append({
                                    "trade_name": candidate,
                                    "is_generic": True,
                                    "cost": lowest.get("avg_spend_per_dose"),
                                    "manufacturer": lowest.get("manufacturer"),
                                    "details": lowest,
                                })
            
            if not cost_data:
                return self._error_response(
                    f"Found equivalents but no Medicare cost data available for year {latest_year}"
                )
            
            # Step 5: Rank by cost and generate final response using Gemini
            results["cost_data"] = cost_data
            results["final_response"] = self._synthesize_response(
                drug_name=drug_name,
                identity=identity,
                cost_data=cost_data,
                latest_year=latest_year,
            )
            
            return results
            
        except Exception as e:
            return self._error_response(f"Execution error: {str(e)}")

    def _synthesize_response(
        self,
        drug_name: str,
        identity: Dict[str, Any],
        cost_data: List[Dict[str, Any]],
        latest_year: int,
    ) -> str:
        """Use Gemini to synthesize a natural language response."""
        # Sort by cost
        sorted_costs = sorted(cost_data, key=lambda x: x.get("cost", float("inf")))
        
        synthesis_prompt = f"""You are a helpful drug cost comparison assistant.

User asked about: {drug_name}
Original drug identity: {identity.get('trade_name', 'N/A')} ({identity.get('ingredient', 'N/A')}, {identity.get('strength', 'N/A')})

I found {len(sorted_costs)} therapeutic equivalent options with Medicare Part D cost data for year {latest_year}.

Cost data (sorted by lowest cost):
"""
        for i, item in enumerate(sorted_costs[:10], 1):
            cost = item.get("cost", 0)
            trade_name = item.get("trade_name", "N/A")
            is_generic = item.get("is_generic", False)
            manufacturer = item.get("manufacturer", "N/A")
            synthesis_prompt += f"{i}. {trade_name} ({'Generic' if is_generic else 'Brand'}) - ${cost:.2f} per dose unit (Manufacturer: {manufacturer})\n"

        synthesis_prompt += f"""

Generate a clear, helpful response that:
1. Confirms the drug identity found
2. Lists the top 3-5 cheapest options with their costs
3. Mentions that this is Medicare Part D program-level data for {latest_year}
4. Notes that actual copay may differ
5. Suggests consulting a pharmacist for specific alternatives

Be concise but informative. Format nicely."""

        try:
            _configure_genai()  # Ensure API is configured
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(synthesis_prompt)
            return response.text.strip()
        except Exception as e:
            # Fallback to simple text response
            return self._simple_response(sorted_costs, latest_year)

    def _simple_response(
        self, cost_data: List[Dict[str, Any]], latest_year: int
    ) -> str:
        """Fallback simple text response without LLM."""
        sorted_costs = sorted(cost_data, key=lambda x: x.get("cost", float("inf")))
        
        response = f"Found {len(sorted_costs)} therapeutic equivalent options (Medicare Part D, {latest_year}):\n\n"
        for i, item in enumerate(sorted_costs[:5], 1):
            cost = item.get("cost", 0)
            trade_name = item.get("trade_name", "N/A")
            is_generic = item.get("is_generic", False)
            response += f"{i}. {trade_name} ({'Generic' if is_generic else 'Brand'}) - ${cost:.2f} per dose unit\n"
        
        response += f"\nNote: This is program-level Medicare Part D data for {latest_year}. Actual copay may differ. Consult your pharmacist."
        return response

    def _error_response(self, error_msg: str) -> Dict[str, Any]:
        """Create an error response structure."""
        return {
            "ok": False,
            "error": error_msg,
            "final_response": f"I encountered an error: {error_msg}. Please check the drug name and try again, or provide more details like strength or dosage form.",
        }


def execute_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to execute a plan."""
    executor = Executor()
    return executor.execute(plan)

