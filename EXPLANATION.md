# Technical Explanation

## 1. Agent's Reasoning Process

The ADK agent (`drug_cost_agent/agent.py`) uses **instruction-based reasoning** where Gemini 2.5 Flash reads structured instructions and autonomously decides which tools to call and when. The agent processes user queries through the following reasoning workflow:

1. **Memory Check**: Agent calls `recall_drug_query()` to check if this drug was queried before, providing context from past searches.

2. **Data Year Discovery**: Agent calls `medicare_latest_year()` to determine the latest available Medicare Part D data year.

3. **Drug Identity Matching**: Agent calls `ob_match_identity()` to find the drug in the FDA Orange Book, identifying brand vs. generic and extracting ingredient, strength, dosage form, and route.

4. **Find Equivalents**: Agent calls `ob_find_equivalents()` using the identity details to find all therapeutic equivalents (TE Code A* only).

5. **Cost Lookup**: Agent calls `medicare_lookup_costs()` for each equivalent trade name. **This is the non-deterministic step**: If no Medicare rows are found for a trade name, the agent autonomously decides whether to try the fallback strategy (using `ob_ingredient_to_generic_candidates()` and then looking up costs for generic candidates).

6. **Memory Storage**: Agent calls `remember_drug_query()` to save findings for future reference.

7. **Response Synthesis**: Gemini synthesizes a natural language response ranking drugs by lowest cost, including disclaimers about data source and year.

The agent uses **only `src/tools/memory_tools.py`** for memory (not `src/memory.py`). Memory is stored in `Data/drug_memory.json` as a JSON file, providing long-term persistence across server restarts.

## 2. Memory Usage

The agent uses **only `src/tools/memory_tools.py`** for memory (not `src/memory.py`). Memory is implemented as agent tools that the LLM autonomously calls:

- **`recall_drug_query(drug_name, dosage)`**: Checks if a drug was queried before and retrieves past findings
- **`remember_drug_query(drug_name, dosage, result)`**: Saves drug lookup results for future reference
- **`get_recent_queries(limit)`**: Provides recent query history for context

**Storage**: Memory writes to a JSON file (`Data/drug_memory.json`) and provides **long-term memory across server restarts**. The file persists all drug queries, tracking query frequency per drug and storing the last result for each drug.

**Features**:
- Tracks specific drug queries (not full conversations)
- Persists across server restarts
- Provides context from past searches to enhance responses
- Agent autonomously decides when to use memory tools based on the query

## 3. Planning Style

The agent's planning style is **deterministic** except for **one step** in the workflow:

**Deterministic Steps** (always executed in order):
1. Check memory: `recall_drug_query()`
2. Get latest Medicare year: `medicare_latest_year()`
3. Match drug identity: `ob_match_identity()`
4. Find equivalents: `ob_find_equivalents()`
5. Lookup costs: `medicare_lookup_costs()` for each equivalent
6. Save to memory: `remember_drug_query()`
7. Synthesize response

**Non-Deterministic Step** (Step 5 - Fallback Decision):
- When no Medicare rows are found for a trade name, the agent **autonomously decides** whether to try the fallback strategy:
  - Call `ob_ingredient_to_generic_candidates()` to get generic candidates
  - Then call `medicare_lookup_costs()` for those candidates
- This decision is made by Gemini based on the context and tool results, not by a fixed rule

The agent uses **instruction-based planning** where Gemini reads structured instructions and decides the tool sequence. There is no explicit planner module - the agent follows the workflow defined in its instructions, with the exception of the fallback decision step.

## 4. Tool Integration

### Google Gemini API

**Usage in ADK Agent** (`drug_cost_agent/agent.py`):
- **Model**: `gemini-2.5-flash`
- **Purpose**: 
  - Reads instructions and autonomously decides which tools to call
  - Synthesizes natural language response from tool results
  - Handles planning, tool selection, and response generation in a single workflow
- **Framework**: Google ADK (handles API calls automatically)
- **Planning Style**: Instruction-based - Gemini reads instructions and decides tool sequence autonomously

**API Key Management**:
- Reads `GOOGLE_API_KEY` from environment variables
- Supports global environment variables (like ADK)
- Optional `.env` file fallback
- Lazy initialization (only configures when needed)

The agent integrates three categories of tools:

### Orange Book Tools (`src/tools/tools_ob.py`)

**Tool 1**: `ob_match_identity(drug_name, strength)`
- **Purpose**: Find drug in FDA Orange Book database
- **How it works**: 
  - Direct SQLite query to `products.db`
  - Multi-stage matching algorithm:
    1. Exact normalized match first
    2. Prefix matching fallback
    3. Fuzzy matching with `rapidfuzz` library for scoring
    4. Strength matching bonus (if strength provided)
- **Returns**: Best match + alternates with classification (brand/generic)
- **Database**: Queries `products.db` which contains FDA Orange Book data with drug identities, ingredients, strengths, dosage forms, routes, and therapeutic equivalence codes

**Tool 2**: `ob_find_equivalents(ingredient, strength, form, route)`
- **Purpose**: Find therapeutic equivalents for a given drug identity
- **How it works**: 
  - SQLite query filtering by normalized ingredient/strength/form/route
  - Filters for TE code starting with "A" (therapeutic equivalence)
  - Returns all products with matching identity characteristics
- **Returns**: List of equivalent products with trade names, manufacturers, and TE codes
- **Use case**: After matching a drug identity, find all equivalent options for cost comparison

**Tool 3**: `ob_ingredient_to_generic_candidates(ingredient)`
- **Purpose**: Generate generic name candidates for fallback strategy
- **Algorithm**: Removes salt suffixes (HCl, sodium, etc.) from ingredient name to create candidate generic names
- **Returns**: List of candidate generic names
- **Use case**: When no Medicare data found for a trade name, generate generic candidates to search for cost data

### Medicare Tools (`src/tools/tools_medicare.py`)

**Tool 1**: `medicare_latest_year()`
- **Purpose**: Get latest available year with Medicare Part D data
- **How it works**: SQLite query `SELECT MAX(year) FROM cms_partd_costs_slim`
- **Returns**: Latest available year (typically 2023)
- **Use case**: Determine which year's data to use for all cost comparisons

**Tool 2**: `medicare_lookup_costs(name, year)`
- **Purpose**: Lookup cost per dose unit for a drug
- **How it works**: 
  - SQLite query to `medicare.db`
  - Searches by normalized brand name OR generic name
  - Filters by year (or uses latest if not specified)
  - Sorts by `avg_spend_per_dose` (ascending - cheapest first)
- **Returns**: List of cost records with manufacturer info, sorted by cost
- **Use case**: Get cost data for each equivalent drug to rank by price

### Medicare Part D Data Information

**Data Source**: CMS (Centers for Medicare & Medicaid Services) Part D Prescription Drug Event (PDE) data

**Database**: `medicare.db` → `cms_partd_costs_slim` table

**Available Years**: 2019, 2020, 2021, 2022, 2023 (latest available year is determined dynamically)

**Data Fields**:
- **`brand_name`**: Brand/trade name of the drug
- **`generic_name`**: Generic/ingredient name of the drug
- **`manufacturer`**: Manufacturer name
- **`tot_mftr`**: Total number of manufacturers for this drug
- **`year`**: Year of the data (2019-2023)
- **`avg_spend_per_dose`**: Weighted average spending per dosage unit (in dollars) - **This is the primary metric used for cost comparison**
- **`outlier_flag`**: Boolean flag indicating if this is an outlier (1) or not (0)
- **`brand_name_n`**: Normalized brand name (for matching)
- **`generic_name_n`**: Normalized generic name (for matching)

**What the Data Represents**:
- **Program-level averages**: The `avg_spend_per_dose` reflects Medicare Part D program-level average spending per dosage unit, weighted across all beneficiaries
- **Not individual copays**: This metric does NOT represent individual patient copayments or out-of-pocket costs
- **Aggregate spending**: Represents the average cost that Medicare Part D plans pay per dosage unit across all plans and beneficiaries
- **Multiple manufacturers**: Each drug may have multiple rows (one per manufacturer), allowing comparison of costs across different manufacturers

**How It's Used**:
- The agent queries Medicare data by matching normalized brand names or generic names
- Results are sorted by `avg_spend_per_dose` (ascending - cheapest first)
- The agent uses the latest available year (typically 2023) for all cost comparisons
- Outlier flags are included but not currently used in ranking logic

### Memory Tools (`src/tools/memory_tools.py`)

**Tool 1**: `recall_drug_query(drug_name, dosage)`
- **Purpose**: Check if a drug was queried before and retrieve past findings
- **How it works**: 
  - Searches `Data/drug_memory.json` for matching drug name and dosage
  - Returns previous query results if found
  - Includes query count and last result
- **Returns**: Dictionary with `found` flag, `query_count`, `last_result`, and `last_query_time`
- **Use case**: Provide context from past searches at the start of a query

**Tool 2**: `remember_drug_query(drug_name, dosage, result)`
- **Purpose**: Save drug lookup results for future reference
- **How it works**: 
  - Updates `Data/drug_memory.json` with new query
  - Increments query count for the drug
  - Stores summary of findings
- **Returns**: Confirmation message
- **Use case**: Store findings at the end of a query for future reference

**Tool 3**: `get_recent_queries(limit)`
- **Purpose**: Get recent query history for context
- **How it works**: Returns list of most recent drug queries from memory file
- **Returns**: List of recent queries with timestamps
- **Use case**: Provide context about what the user has been researching

**Storage Details**:
- All memory tools write to `Data/drug_memory.json`
- JSON file format for simple persistence
- Long-term memory across server restarts
- Tracks query frequency per drug

All tools query SQLite databases (`products.db` and `medicare.db`) using indexed queries for efficient data retrieval. Database indexes are created on normalized names and years to optimize lookup performance.

## 5. Known Limitations

### Current Bugs

1. **Memory Response Bug**: Sometimes the final response includes the extra response from the agent remembering the search (when `remember_drug_query()` is called). This is an unfixed bug where the memory tool's response may leak into the final user-facing response.
2. **Redundant Recent History Bug**:  When the user inquires about past drug searches, the agent does not consolidate duplicates to only show the summary from the latest instance of that drug search session.

### Data Limitations

1. **Dataset Year**: Limited by dataset year **2023** (or latest available year in Medicare Part D data). The agent uses `medicare_latest_year()` to determine the latest available year, but the dataset may not include more recent years.

2. **Cost Data Level**: Costs are at **program-level** (Medicare Part D average spending), not at **copay level**. This means:
   - The `avg_spend_per_dose` metric reflects program-level averages
   - May not equal individual patient copayments
   - Does not reflect actual out-of-pocket costs for specific patients
   - Should be used as a relative comparison tool, not absolute cost prediction

### Architecture Limitations

1. **Memory Storage**:
   - JSON file storage (`Data/drug_memory.json`) - not scalable for production
   - Tracks drug queries only (not full conversations)
   - Simple storage structure (no semantic search)
   - No vector embeddings for better retrieval
   - Could be enhanced with vector database (e.g., ChromaDB)
   - No multi-user account support to safeguard each person's personal drug search history

2. **Planning Style**:
   - Instruction-based planning relies on Gemini's interpretation of instructions
   - Non-deterministic fallback decision (Step 5) may lead to inconsistent behavior
   - May not always follow optimal tool sequence

### Performance & Scalability

1. **Database Queries**:
   - Large databases (~50MB+ each) require disk I/O
   - Multiple sequential queries can be slow
   - No caching mechanism (queries repeated for same drugs)

2. **Memory Storage**:
   - JSON file storage loads all queries into memory when accessed
   - Could be problematic with many drug queries over time
   - Should implement pagination or lazy loading for large datasets

3. **Fuzzy Matching**:
   - Drug name matching uses fuzzy matching which may have false positives
   - Scoring algorithm could be improved
   - No confidence thresholds

### Edge Cases

1. **Missing Drug Information**:
   - If strength not provided and multiple matches exist, agent asks user
   - Could be improved with better disambiguation logic

2. **No Cost Data**:
   - If Medicare has no data for a drug, agent decides whether to try fallback (non-deterministic)
   - May still return no results even with fallback
   - Could provide better fallback strategies

3. **Database Freshness**:
   - Databases built from static source files
   - Requires manual updates for new drug data
   - No automatic data refresh mechanism

4. **Orange Book Coverage**:
   - Only FDA-approved drugs
   - May miss some generic alternatives
   - TE code filtering may exclude valid equivalents

5. **Name Variations**:
   - Drug names may have multiple spellings/variations
   - Fuzzy matching helps but not perfect
   - Brand vs generic identification may be incorrect in complex cases

### Security & Privacy

1. **API Key Storage**:
   - Uses environment variables (good practice)
   - `.env` file support (should not be committed to version control)
   - No built-in API key rotation mechanism

2. **Data Storage**:
   - Stores user queries and drug information in plain JSON files
   - No encryption of data at rest
   - Should consider privacy implications for sensitive health information
   - Memory files contain drug names and query history

### Scalability

1. **Concurrent Requests**:
   - ADK framework handles concurrent requests at the server level
   - Each request processed independently
   - No shared state between requests

2. **Database Size**:
   - Databases will grow over time (~50MB+ each currently)
   - No partitioning or archiving strategy for very large datasets
   - Indexes help but may need further optimization for extremely large tables

3. **Memory Usage**:
   - Drug memory loads all queries into memory when accessed
   - Could be problematic with many drug queries over time
   - Should implement pagination or lazy loading for large datasets

## 6. Observability & Testing

### Logging

Note:  Attempts were made to use Google ADK's LoggingPlugin for Observability of AI Agent.  This and other plugins such as for token count and budget failed due to Google ADK always ignoring the custom runner.py that imports and uses the plugins.  Different workarounds were attempted in collaboration with Claude.ai but we were unable to determine how to use LoggingPlugin by time of submission.

**ADK Framework Logging**:
- Use `adk web . -v` for verbose logging
- Or `adk web . --log_level debug` for debug level
- Logs include: tool calls, agent reasoning, errors, API calls
- Logs show which tools are called and in what order

**Memory Storage for Debugging**:
- Drug queries stored in `Data/drug_memory.json`
- Can review past queries and responses
- Includes timestamps and context
- Useful for tracing agent decisions and understanding memory usage

**Error Handling**:
- Tools return structured error responses (`{"ok": False, "error": "..."}`)
- ADK framework handles exceptions and provides error messages
- Agent can handle missing data gracefully with fallback strategies
- Database connection errors are caught and returned as user-friendly messages

### Testing

**CI Pipeline** (`.github/workflows/ci.yml`):
- Validates imports
- Checks code structure
- Validates agent configuration
- Syntax checking
- Ensures all required modules can be imported

**Agent Evaluation**:
- eval_config.json has one metric for LLM judged similarity of final response.
- test_cases.json has 5 test cases with different User inputs and expected final responses.
Note:  Efforts to add Hallucination and Tool-trajectory metrics to eval_config.json with Claude.ai's help were unsuccessful.  We were unsure where to specify the tool trajectory, and the metric for hallucination had validation errors we did not yet fix for the Dec 12-15, 2025 ODSC Agentic AI Hackathon.

**Manual Testing**:
```bash
# Test agent import
python -c "from drug_cost_agent import root_agent"

# Test tools
python -c "from src.tools.tools_ob import ob_match_identity"
python -c "from src.tools.tools_medicare import medicare_latest_year"
python -c "from src.tools.memory_tools import recall_drug_query"

# Test memory tools
python -c "from src.tools.memory_tools import remember_drug_query; remember_drug_query('test', '10mg', 'test result')"
```

**Trace Decisions**:
- Review `Data/drug_memory.json` for drug query history
- Check ADK logs (`adk web . -v`) for tool call sequence
- Examine agent reasoning and tool selection in verbose logs
- See which tools agent calls and in what order
- Understand why agent made certain decisions

### Error Recovery

**Tool-Level Errors**:
- Each tool returns structured responses with `ok` flag
- Errors include descriptive messages
- Agent can continue workflow even if some tools fail

**Database Errors**:
- Connection errors are caught and returned gracefully
- Missing data handled with fallback strategies
- Invalid queries return error messages instead of crashing

**API Errors**:
- Gemini API errors handled by ADK framework
- Rate limit errors would be caught by framework
- Network errors return user-friendly messages
