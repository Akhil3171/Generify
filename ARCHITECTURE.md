# Architecture Overview

## System Architecture

This project follows a hybrid architecture combining:
1. **ADK Agent** (`drug_cost_agent/`) - Web interface using Google ADK
2. **Architecture Modules** (`src/`) - Required planner/executor/memory pattern
3. **Tools** (`src/tools_*.py`) - Shared tools used by both

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interface                         │
│                   (ADK Web Server)                          │
│                  http://127.0.0.1:8080                      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    ADK Agent Layer                          │
│              drug_cost_agent/agent.py                       │
│              (Gemini 2.5 Flash)                             │
│  - Reads user query                                         │
│  - Decides tool sequence                                    │
│  - Synthesizes response                                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Architecture Modules (src/)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  planner.py  │  │ executor.py  │  │  memory.py   │     │
│  │  (Gemini)    │→ │  (Gemini)    │→ │  (JSON)      │     │
│  │              │  │              │  │              │     │
│  │ Task break- │  │ Tool orchest-│  │ Session      │     │
│  │ down        │  │ ration       │  │ storage      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                  │                  │            │
│         └──────────────────┴──────────────────┘            │
│                            │                                │
│                   agent_core.py                            │
│              (Workflow Orchestrator)                       │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    Tools Layer (src/)                       │
│  ┌──────────────────┐      ┌──────────────────┐           │
│  │  tools_ob.py     │      │tools_medicare.py  │           │
│  │                  │      │                  │           │
│  │ - Match identity │      │ - Latest year    │           │
│  │ - Find equivs    │      │ - Lookup costs   │           │
│  │ - Generic cands  │      │                  │           │
│  └──────────────────┘      └──────────────────┘           │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                               │
│  ┌──────────────────┐      ┌──────────────────┐           │
│  │  products.db     │      │  medicare.db     │           │
│  │  (Orange Book)   │      │  (CMS Part D)    │           │
│  └──────────────────┘      └──────────────────┘           │
│                                                             │
│  sessions.json (Session memory storage)                    │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. User Interface
- **ADK Web Server**: Provides web UI via `adk web .`
- **Port**: 8080 (default)
- **Framework**: Google ADK (FastAPI-based)

### 2. Agent Core

#### Planner (`src/planner.py`)
- **Purpose**: Breaks down user queries into structured sub-tasks using Gemini API
- **Key class**: `Planner`
- **Main method**: `build_plan(user_input, context)`
- **Returns**: Dictionary with:
  - `drug_name`: Extracted drug name
  - `strength`: Extracted strength (if mentioned)
  - `dosage_form`: Extracted form (if mentioned)
  - `tasks`: List of sub-tasks to execute
- **Gemini API Usage**: Calls `genai.GenerativeModel()` to analyze and structure queries
- **Fallback**: Simple regex-based extraction if Gemini fails

#### Executor (`src/executor.py`)
- **Purpose**: Executes planned tasks by orchestrating tool calls and synthesizing responses
- **Key class**: `Executor`
- **Main method**: `execute(plan)`
- **Workflow**:
  1. Gets latest Medicare year
  2. Matches drug identity in Orange Book
  3. Finds therapeutic equivalents
  4. Looks up costs for each equivalent
  5. Ranks by cost
  6. Uses Gemini to synthesize final response
- **Gemini API Usage**: For final response generation after tool execution
- **Returns**: Dictionary with execution results and final response text

#### Memory (`src/memory.py`)
- **Purpose**: Stores and retrieves conversation context with session support
- **Key class**: `SessionMemory`
- **Storage**: JSON file (`Data/sessions.json`)
- **Features**:
  - Session-based storage (each conversation gets unique ID)
  - Persistent (survives app restarts)
  - Retrieval by keyword matching
  - Stores: queries, responses, drug data, cost comparisons
- **Methods**:
  - `store()`: Save interaction to session
  - `retrieve_from_session()`: Get relevant past interactions
  - `get_session()`: Get full session history
  - `list_sessions()`: List all stored sessions

#### Agent Core (`src/agent_core.py`)
- **Purpose**: Main workflow orchestrator (combines planner + executor + memory)
- **Key class**: `AgentCore`
- **Main method**: `process_user_input(user_input, session_id)`
- **Workflow**:
  1. Receive user input
  2. Retrieve relevant memory (optional)
  3. Plan sub-tasks (via `Planner`)
  4. Execute plan (via `Executor`)
  5. Generate final response
  6. Store in memory (optional)
- **Note**: Currently demonstrates architecture pattern (ADK agent uses tools directly)

### 3. Tools / APIs

#### Orange Book Tools (`src/tools_ob.py`)
- **Purpose**: FDA Orange Book drug matching and equivalence lookup
- **Tools**:
  - `ob_match_identity(drug_name, strength)`: Finds drug in Orange Book
    - Uses fuzzy matching (rapidfuzz library)
    - Returns best match + alternates
    - Identifies brand vs generic
  - `ob_find_equivalents(ingredient, strength, form, route)`: Finds therapeutic equivalents
    - Filters by TE code (therapeutic equivalence)
    - Returns all equivalent products
  - `ob_ingredient_to_generic_candidates(ingredient)`: Generates generic name candidates
    - Removes salt suffixes (HCl, sodium, etc.)
    - Used as fallback when exact match fails
- **Database**: `Data/products.db` (Orange Book data)

#### Medicare Tools (`src/tools_medicare.py`)
- **Purpose**: Medicare Part D cost lookup
- **Tools**:
  - `medicare_latest_year()`: Returns latest year with data
  - `medicare_lookup_costs(name, year)`: Looks up cost per dose unit
    - Searches by brand name or generic name
    - Returns sorted by cost (lowest first)
    - Includes manufacturer info
- **Database**: `Data/medicare.db` (CMS Part D spending data)

#### Path Utilities (`src/paths.py`)
- **Purpose**: Provides database file paths
- **Functions**:
  - `products_db_path()`: Returns path to Orange Book DB
  - `medicare_db_path()`: Returns path to Medicare DB
- **Why needed**: Centralized path management

### 4. Observability & Error Handling

- **Logging**: ADK provides built-in logging (use `-v` flag for verbose)
- **Error Handling**: 
  - Planner has fallback if Gemini fails
  - Executor catches exceptions and returns error messages
  - Tools return structured error responses
- **Session Tracking**: All interactions stored in `Data/sessions.json` for debugging

## Agent Workflow

### ADK Web Flow (Current Implementation)

```
1. User Query
   ↓
2. ADK Web Server (adk web)
   ↓
3. drug_cost_agent/agent.py (Gemini LLM)
   ↓
4. Reads instruction → Decides which tools to call
   ↓
5. src/tools_ob.py & src/tools_medicare.py
   ↓
6. Query databases (products.db, medicare.db)
   ↓
7. Return results to agent
   ↓
8. Agent synthesizes response (Gemini)
   ↓
9. Display in web UI
```

### Architecture Modules Flow (Demonstration Pattern)

```
1. Receive user input
   ↓
2. (Optional) Retrieve relevant memory (src/memory.py)
   ↓
3. Plan sub-tasks (src/planner.py using Gemini API)
   ↓
4. Execute plan (src/executor.py)
   ├── Call tools (src/tools_*.py)
   └── Use Gemini for synthesis
   ↓
5. Generate final response
   ↓
6. (Optional) Store in memory (src/memory.py)
   ↓
7. Return response
```

**Note**: The architecture modules (`planner.py`, `executor.py`, `memory.py`, `agent_core.py`) demonstrate the required pattern but are **not currently used by the ADK agent**. The ADK agent uses tools directly via its instruction-based workflow.

## Directory Structure

```
Generify/
├── drug_cost_agent/          # ADK Agent (Web Interface)
│   ├── __init__.py          # Exports root_agent
│   └── agent.py             # Agent definition using Gemini
├── src/                     # Core Code (Required Architecture)
│   ├── planner.py           # Task decomposition (Gemini API)
│   ├── executor.py          # Tool execution (Gemini API)
│   ├── memory.py            # Session storage
│   ├── agent_core.py        # Workflow orchestrator
│   ├── tools_ob.py          # Orange Book tools
│   ├── tools_medicare.py    # Medicare Part D tools
│   └── paths.py             # Database paths
├── Data/                     # Databases & Source Data
│   ├── products.db          # Orange Book (built)
│   ├── medicare.db          # Medicare Part D (built)
│   └── sessions.json        # Session memory (auto-created)
├── build_db.py              # Database builder
├── requirements.txt         # Dependencies
└── .env                     # API key (optional, uses env vars)
```

## File Dependencies

```
drug_cost_agent/agent.py
    ├── imports from src/tools_ob.py
    └── imports from src/tools_medicare.py

src/executor.py
    ├── imports from src/tools_ob.py
    ├── imports from src/tools_medicare.py
    └── uses google.generativeai (Gemini API)

src/planner.py
    └── uses google.generativeai (Gemini API)

src/agent_core.py
    ├── imports src/planner.py
    ├── imports src/executor.py
    └── imports src/memory.py

src/tools_*.py
    └── imports src/paths.py (for database paths)
```

## Key Design Decisions

### Why Two Approaches?

1. **ADK Agent** (`drug_cost_agent/`):
   - Provides web interface
   - Uses ADK's built-in tool-calling
   - LLM decides tool sequence dynamically
   - Currently active and working

2. **Architecture Modules** (`src/`):
   - Meets competition requirements (planner/executor/memory)
   - Demonstrates explicit Gemini API usage
   - Shows modular architecture pattern
   - Demonstrates required workflow

### Why Tools in `src/`?

- **Shared**: Both ADK agent and architecture modules use the same tools
- **Template requirement**: All code must be in `src/`
- **Reusable**: Tools are independent and can be used by any component

## Tool Integration

### External Tools & APIs

1. **Google Gemini API**
   - Used in: `planner.py`, `executor.py`, `drug_cost_agent/agent.py`
   - Purpose: Task planning, response synthesis, agent reasoning
   - Model: `gemini-2.5-flash` (ADK agent), `gemini-2.0-flash-exp` (modules)

2. **Orange Book Database** (`products.db`)
   - Tool: `ob_match_identity()`, `ob_find_equivalents()`, `ob_ingredient_to_generic_candidates()`
   - Purpose: Drug identity matching and therapeutic equivalence lookup
   - Source: FDA Orange Book data

3. **Medicare Part D Database** (`medicare.db`)
   - Tool: `medicare_latest_year()`, `medicare_lookup_costs()`
   - Purpose: Cost comparison and ranking
   - Source: CMS Medicare Part D spending data

## Known Limitations

1. **Architecture Modules Not Integrated**: The planner/executor/memory modules demonstrate the pattern but aren't used by the ADK agent (which uses tools directly)

2. **Memory Storage**: Session memory stored in JSON file - not scalable for production but sufficient for demo

3. **Error Handling**: Basic error handling - could be enhanced with retries and better error messages

4. **Database Size**: Large databases (~50MB+ each) - requires significant disk space

5. **API Rate Limits**: Gemini API calls may hit rate limits with high usage

6. **Fuzzy Matching**: Drug name matching uses fuzzy matching which may have false positives

7. **Data Freshness**: Databases built from static source files - requires manual updates for new data

## Testing & Observability

- **CI Pipeline**: `.github/workflows/ci.yml` validates imports, structure, and agent config
- **Session Storage**: All interactions stored in `Data/sessions.json` for review
- **ADK Logging**: Use `adk web . -v` for verbose logging
- **Test Commands**: See README.md for testing instructions
