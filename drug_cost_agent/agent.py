from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import Agent

from src.tools.tools_ob import ob_match_identity, ob_find_equivalents, ob_ingredient_to_generic_candidates
from src.tools.tools_medicare import medicare_latest_year, medicare_lookup_costs
from src.tools.memory_tools import (
    remember_drug_query,
    recall_drug_query,
    get_recent_queries
)

# Load environment variables from .env file if it exists (optional)
# ADK will automatically read GOOGLE_API_KEY from environment variables
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(env_path)

root_agent = Agent(
    name="drug_cost_agent",
    model="gemini-2.5-flash",
    description="Find equivalent drugs and rank by Medicare Part D avg spend per dosage unit (latest year available).",
    instruction=(
        "You are a tool-using agent.\n"
        "Goal: user gives a drug (name, maybe strength). Identify if brand or generic, find TE-equivalent options, "
        "then rank by lowest Medicare Part D avg spend per dosage unit.\n\n"

        "NEW CAPABILITY - Memory:\n"
        "- Use recall_drug_query() at the START of each query to check if we've looked up this drug before\n"
        "- Use remember_drug_query() at the END to save findings for future reference\n"
        "- Use get_recent_queries() to see what the user has been researching\n\n"

        "Workflow:\n"
        "1) Check memory: recall_drug_query(drug_name, strength) - if found, mention we've looked this up before\n"
        "2) Call medicare_latest_year to know which year is available (use that year only).\n"
        "3) Call ob_match_identity(drug_name, strength?) to get the best Orange Book identity.\n"
        "4) Call ob_find_equivalents using the identity's ingredient/strength/dosage_form/route (TE A* only).\n"
        "5) For each equivalent trade_name, call medicare_lookup_costs(trade_name, year=latest_year).\n"
        "   - If no Medicare rows are found for a trade_name, YOU decide whether to try fallback:\n"
        "     a) Call ob_ingredient_to_generic_candidates(ingredient) to get generic candidates, then\n"
        "     b) Call medicare_lookup_costs(candidate, year=latest_year) for candidates.\n"
        "6) Save to memory: remember_drug_query(drug_name, strength, summary_of_findings)\n"
        "7) Choose the lowest avg_spend_per_dose across candidates and explain clearly.\n\n"

        "If the Orange Book match is uncertain or user didn't provide strength and there are multiple plausible matches, "
        "ask for strength/dosage form.\n"
        "Always disclose the year used (latest available) and that this metric is program-level and may not equal copay."
    ),
    tools=[
        # Original tools
        medicare_latest_year,
        medicare_lookup_costs,
        ob_match_identity,
        ob_find_equivalents,
        ob_ingredient_to_generic_candidates,
        # NEW: Memory tools
        remember_drug_query,
        recall_drug_query,
        get_recent_queries
    ]
)
