# Technical Explanation

## 1. Agent Workflow

The agent processes user input through the following step-by-step workflow:

### Step 1: Receive User Input
- User submits a query via ADK web interface (e.g., "Find cheapest equivalent for Lipitor 20mg")
- Input is received by `drug_cost_agent/agent.py`

### Step 2: (Optional) Retrieve Relevant Memory
- If session-based memory is enabled, the system retrieves past interactions
- Uses keyword matching to find relevant previous queries
- Context from memory can inform planning decisions
### This is not used, we used a tool instead, memory_tools in src/tools subdirectory
- **Implementation**: `src/memory.py` → `retrieve_from_session()`

### Step 3: Plan Sub-Tasks
- **Planner** (`src/planner.py`) analyzes the user query using Gemini API
- Extracts key information:
  - Drug name (brand or generic)
  - Strength (if mentioned)
  - Dosage form (if mentioned)
- Creates structured plan with ordered sub-tasks:
  1. Get latest Medicare year available
  2. Match drug identity in Orange Book
  3. Find therapeutic equivalents
  4. Lookup Medicare costs for each equivalent
  5. Rank by cost and generate response
- **Pattern**: Uses ReAct-style planning where Gemini breaks down the goal into actionable steps
- **Fallback**: If Gemini API fails, uses regex-based extraction

### Step 4: Call Tools or APIs as Needed
- **Executor** (`src/executor.py`) orchestrates tool execution:
  1. Calls `medicare_latest_year()` to determine available data year
  2. Calls `ob_match_identity()` to find drug in Orange Book
  3. Calls `ob_find_equivalents()` to find therapeutic equivalents
  4. Calls `medicare_lookup_costs()` for each equivalent to get cost data
  5. Falls back to `ob_ingredient_to_generic_candidates()` if needed
- Tools query SQLite databases (`products.db`, `medicare.db`)
- Results are collected and processed

### Step 5: Summarize and Return Final Output
- **Executor** uses Gemini API to synthesize a natural language response
- Ranks drugs by cost (lowest first)
- Includes disclaimers about data source and year
- **Memory**: Stores interaction in session storage (`src/memory.py`)
- Final response displayed in ADK web interface

## 2. Key Modules

### Planner (`src/planner.py`)

**Purpose**: Breaks down user goals into structured sub-tasks using Gemini API.

**How it works**:
- Uses `google.generativeai.GenerativeModel()` to analyze user input
- Prompts Gemini to extract drug information and create task list
- Returns structured plan dictionary with:
  - `drug_name`: Extracted drug name
  - `strength`: Extracted strength (or None)
  - `dosage_form`: Extracted form (or None)
  - `tasks`: Ordered list of sub-tasks

**Example**:
```python
plan = planner.build_plan("Find cheapest equivalent for Lipitor 20mg")
# Returns: {
#   "drug_name": "Lipitor",
#   "strength": "20mg",
#   "dosage_form": None,
#   "tasks": ["Get latest Medicare year", "Match identity", ...]
# }
```

**Gemini API Usage**: Direct calls to `genai.GenerativeModel().generate_content()` for task decomposition.

### Executor (`src/executor.py`)

**Purpose**: Executes planned tasks by orchestrating tool calls and synthesizing responses.

**How it works**:
- Takes plan from planner
- Sequentially executes each task:
  1. Calls `medicare_latest_year()` tool
  2. Calls `ob_match_identity()` tool with drug name
  3. Calls `ob_find_equivalents()` tool with identity details
  4. Calls `medicare_lookup_costs()` for each equivalent
  5. Handles fallbacks if no costs found
- Collects all results
- Uses Gemini API to synthesize final natural language response
- Returns structured results dictionary with final response text

**Gemini API Usage**: 
- Calls `genai.GenerativeModel().generate_content()` for response synthesis
- Formats cost data and asks Gemini to create user-friendly explanation

**Error Handling**: Catches exceptions, returns error messages, handles missing data gracefully.

///
NEW: for Memory implementation for Generify, see now in Tools section of this document ## Memory Tools  (`src/tools/memory_tools.py`)
///
### Memory Store (`src/memory.py`)

**Purpose**: Stores and retrieves conversation context with session support.

**How it works**:
- **Storage**: JSON file (`Data/sessions.json`) - persistent across restarts
- **Session-based**: Each conversation gets unique session ID (UUID)
- **Stores**:
  - User queries
  - Agent responses
  - Drug identities found
  - Cost comparison data
  - Timestamps
- **Retrieval**: Keyword-based matching to find relevant past interactions
- **Methods**:
  - `store()`: Save interaction to session
  - `retrieve_from_session()`: Get relevant past interactions (keyword matching)
  - `get_session()`: Get full session history
  - `list_sessions()`: List all stored sessions

**Example**:
```python
# Store interaction
store_session(session_id, "Find Lipitor alternatives", results, response)

# Retrieve relevant past interactions
past = retrieve_from_session(session_id, "cheaper option", limit=3)
```


## 3. Tool Integration

### Google Gemini API

**Usage Locations**:
1. **`src/planner.py`**: Task decomposition
   - Function: `Planner.build_plan()`
   - Model: `gemini-2.0-flash-exp`
   - Purpose: Analyze user query and create structured plan

2. **`src/executor.py`**: Response synthesis
   - Function: `Executor._synthesize_response()`
   - Model: `gemini-2.0-flash-exp`
   - Purpose: Generate natural language response from cost data

3. **`drug_cost_agent/agent.py`**: Agent reasoning
   - Model: `gemini-2.5-flash`
   - Purpose: Decide which tools to call and synthesize final response
   - Framework: Google ADK (handles API calls automatically)

**API Key Management**:
- Reads `GOOGLE_API_KEY` from environment variables
- Supports global environment variables (like ADK)
- Optional `.env` file fallback
- Lazy initialization (only configures when needed)

### Orange Book Tools (`src/tools/tools_ob.py`)

**Tool 1**: `ob_match_identity(drug_name, strength)`
- **Purpose**: Find drug in FDA Orange Book
- **How it calls**: Direct SQLite query to `products.db`
- **Algorithm**: 
  - Exact normalized match first
  - Prefix matching fallback
  - Fuzzy matching with `rapidfuzz` library for scoring
  - Strength matching bonus
- **Returns**: Best match + alternates with classification (brand/generic)

**Tool 2**: `ob_find_equivalents(ingredient, strength, form, route)`
- **Purpose**: Find therapeutic equivalents
- **How it calls**: SQLite query filtering by normalized ingredient/strength/form/route
- **Filter**: TE code starting with "A" (therapeutic equivalence)
- **Returns**: List of equivalent products with trade names

**Tool 3**: `ob_ingredient_to_generic_candidates(ingredient)`
- **Purpose**: Generate generic name candidates (fallback)
- **Algorithm**: Removes salt suffixes (HCl, sodium, etc.) from ingredient name
- **Returns**: List of candidate generic names

### Medicare Tools (`src/tools/tools_medicare.py`)

**Tool 1**: `medicare_latest_year()`
- **Purpose**: Get latest year with Medicare Part D data
- **How it calls**: SQLite query `SELECT MAX(year) FROM cms_partd_costs_slim`
- **Returns**: Latest available year

**Tool 2**: `medicare_lookup_costs(name, year)`
- **Purpose**: Lookup cost per dose unit
- **How it calls**: SQLite query to `medicare.db`
- **Search**: By normalized brand name OR generic name
- **Sorting**: By `avg_spend_per_dose` (ascending - cheapest first)
- **Returns**: List of cost records with manufacturer info

## Memory Tools  (`src/tools/memory_tools.py`)

### Long-Term Memory
Generify remembers previous drug queries across sessions to provide faster, context-aware responses.

**Features:**
- Recalls past drug lookups automatically
- Tracks query frequency per drug
- Persists across server restarts
- Provides context from recent searches

**Example:**
```
First query: "Wellbutrin 300mg"
→ Full lookup with Medicare data, result is Wellbutrin XL (BUPROPION HYDROCHLORIDE) 300mg, Extended Release Tablet, Oral.

Later query: "Wellbutrin XL 300mg"
→ "I've looked into Wellbutrin 300mg recently!"
   [Provides cached insights + updated data]
```

**Implementation:**
Memory is implemented as agent tools (`remember_drug_query`, `recall_drug_query`, `get_recent_queries`) that the LLM autonomously uses to enhance user experience.

**Storage:**
`data/drug_memory.json` - Persistent file-based storage

**Limitations**: 
- JSON file storage (not scalable for production)
- No vector embeddings (could be enhanced)

## 4. Observability & Testing

### Logging

**ADK Framework Logging**:
- Use `adk web . -v` for verbose logging
- Or `adk web . --log_level debug` for debug level
- Logs include: tool calls, agent reasoning, errors

**Session Storage for Debugging**:
- All interactions stored in `Data/sessions.json`
- Can review past queries and responses
- Includes timestamps and full context
- Useful for tracing agent decisions

**Error Handling**:
- Tools return structured error responses (`{"ok": False, "error": "..."}`)
- Executor catches exceptions and returns user-friendly error messages
- Planner has fallback if Gemini API fails

### Testing

**CI Pipeline** (`.github/workflows/ci.yml`):
- Validates imports
- Checks code structure
- Validates agent configuration
- Syntax checking

**Manual Testing**:
```bash
# Test agent import
python -c "from drug_cost_agent import root_agent"

# Test tools
python -c "from src.tools.tools_ob import ob_match_identity"
python -c "from src.tools.tools_medicare import medicare_latest_year"

# Test planner (requires API key)
python -c "from src.planner import build_plan; print(build_plan('test'))"

# Test executor (requires API key)
python -c "from src.executor import Executor; e = Executor()"

# Test memory
python -c "from src.memory import get_memory; m = get_memory()"
```

**Trace Decisions**:
- Review `Data/sessions.json` to see stored interactions
- Check ADK logs for tool call sequence
- Examine executor results structure

## 5. Known Limitations

### Architecture Limitations

1. **Dual Architecture**: 
   - Architecture modules (planner/executor/memory) demonstrate the pattern but aren't integrated with ADK agent
   - ADK agent uses tools directly via instruction-based workflow
   - This creates some redundancy but meets competition requirements

2. **Memory Storage**:
   - JSON file storage (`Data/sessions.json`) not scalable for production
   - Simple keyword matching (not semantic search)
   - No vector embeddings for better retrieval
   - Could be enhanced with vector database (e.g., ChromaDB)

### Performance Bottlenecks

1. **Database Queries**:
   - Large databases (~50MB+ each) require disk I/O
   - Multiple sequential queries can be slow
   - No caching mechanism (queries repeated for same drugs)

2. **Gemini API Calls**:
   - Multiple API calls per query (planner + executor synthesis)
   - Rate limits may be hit with high usage
   - No request batching or caching

3. **Fuzzy Matching**:
   - Drug name matching uses fuzzy matching which may have false positives
   - Scoring algorithm could be improved
   - No confidence thresholds

### Edge Cases & Ambiguous Inputs

1. **Missing Drug Information**:
   - If strength not provided and multiple matches exist, agent asks user
   - Could be improved with better disambiguation logic

2. **No Cost Data**:
   - If Medicare has no data for a drug, falls back to generic candidates
   - May still return no results
   - Could provide better fallback strategies

3. **Database Freshness**:
   - Databases built from static source files
   - Requires manual updates for new drug data
   - No automatic data refresh mechanism

4. **Error Recovery**:
   - Basic error handling - could be enhanced with retries
   - No exponential backoff for API failures
   - Limited fallback strategies

### Data Limitations

1. **Medicare Part D Data**:
   - Program-level averages, not individual copay
   - May not reflect actual patient costs
   - Limited to available years in dataset

2. **Orange Book Coverage**:
   - Only FDA-approved drugs
   - May miss some generic alternatives
   - TE code filtering may exclude valid equivalents

3. **Name Variations**:
   - Drug names may have multiple spellings/variations
   - Fuzzy matching helps but not perfect
   - Brand vs generic identification may be incorrect

### Security & Privacy

1. **API Key Storage**:
   - Uses environment variables (good)
   - `.env` file support (should not be committed)
   - No key rotation mechanism

2. **Session Data**:
   - Stores user queries and drug information
   - No encryption of session data
   - Should consider privacy implications

### Scalability

1. **Single-threaded**:
   - No concurrent request handling
   - ADK handles this, but architecture modules are synchronous

2. **Database Size**:
   - Databases will grow over time
   - No partitioning or archiving strategy
   - Indexes help but may need optimization

3. **Memory Usage**:
   - Session storage loads all sessions into memory
   - Could be problematic with many sessions
   - Should implement pagination or lazy loading

