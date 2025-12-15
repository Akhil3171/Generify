# Generify - Drug Cost Comparison Agent

A tool-using AI agent that helps users find equivalent drugs and rank them by Medicare Part D average spend per dosage unit. Built with Google ADK and Gemini.

## 🎯 Overview

Generify uses the Orange Book (FDA) to identify therapeutic equivalent drugs and Medicare Part D data to rank them by cost-effectiveness. The agent helps users find the most cost-effective generic alternatives to brand-name medications.

## 📋 Submission Checklist

- [x] All code in `src/` runs without errors  
- [x] `ARCHITECTURE.md` contains a clear diagram sketch and explanation  
- [x] `EXPLANATION.md` covers planning, tool use, memory, and limitations  
- [x] `DEMO.md` links to a 3–5 min video with timestamped highlights *(https://youtu.be/BxoGwARAWCY)*  

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Google Gemini API key ([Get one here](https://aistudio.google.com/app/apikey))
- Source data files (see Data Setup below)
- Google ADK with eval

### Installation

0. **Install Google ADK**
   pip install 'google-adk[eval]'


1. **Clone the repository**
   ```bash
   git clone https://github.com/Akhil3171/Generify.git
   cd Generify
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API key**
   
   ADK automatically reads `GOOGLE_API_KEY` from environment variables. You can either:
   - Use a global environment variable (recommended)
   - Or create a `.env` file in the project root:
     ```bash
     GOOGLE_API_KEY=your_api_key_here
     ```
   
   Get your API key from: https://aistudio.google.com/app/apikey

4. **Build databases** (if not already present)
   
   Download the required source data files:
   - Orange Book data: `products.txt` → place in `Data/` folder
   - Medicare Part D data: `DSD_PTD_RY25_P04_V10_DY23_BGM.csv` → place in `Data/` folder
   
   Then run:
   ```bash
   python build_db.py
   ```
   
   This creates:
   - `Data/products.db` (Orange Book database)
   - `Data/medicare.db` (Medicare Part D database)

5. **Run the ADK web server**
   ```bash
   adk web .
   ```
   
   The server will start and display a URL (typically `http://127.0.0.1:8080`). Open it in your browser.
   
   **Alternative commands:**
   ```bash
   # Custom port
   adk web . --port 8081
   
   # Verbose logging
   adk web . -v
   
   # Auto-reload (development)
   adk web . --reload
   ```
6.  **OPTIONAL - Run adk eval test cases**
   e.g. on separate terminal or new command line
   a. Run tests and get simple results (PASS/FAIL metrics)
   ```bash
   adk eval drug_cost_agent evaluation\test_cases.json --config_file_path evaluation\eval_config.json
   ```
   b. Run tests and get detailed results
   ```bash
   adk eval drug_cost_agent evaluation\test_cases.json --config_file_path evaluation\eval_config.json --print_detailed_results
   ```

### Project Structure

```
Generify/
├── drug_cost_agent/          # ADK Agent (Web Interface)
│   ├── __init__.py
│   └── agent.py              # Agent definition using Gemini
├── src/                      # Core Code (Required Architecture)
│   ├── planner.py            # Task decomposition (Gemini API)
│   ├── executor.py           # Tool execution (Gemini API)
│   ├── memory.py             # Session storage
│   ├── agent_core.py         # Workflow orchestrator
│   ├── paths.py              # Database paths
│   ├── tools/                # Tools directory
│   │   ├── tools_ob.py       # Orange Book tools
│   │   ├── tools_medicare.py # Medicare Part D tools
│   │   └── memory_tools.py  # Memory tools (ADK)
│   └── plugins/              # ADK plugins
├── Data/                     # Databases & Source Data
│   ├── products.db           # Orange Book (built)
│   ├── medicare.db           # Medicare Part D (built)
│   └── sessions.json         # Session memory (auto-created)
├── build_db.py               # Database builder
├── requirements.txt          # Dependencies
└── .env                      # API key (optional, uses env vars)
```

See `ARCHITECTURE.md` and `EXPLANATION.md` for detailed technical explanations.

### Usage

Once the ADK web server is running, interact with the agent by asking questions like:
- "Find equivalent drugs for Lipitor 20mg"
- "What are the cheapest alternatives to Advil?"
- "Compare costs for metformin 500mg tablets"
- "I need a cheaper option for Prozac"

### Troubleshooting

**Agent not found:**
- Ensure you're in the project root directory
- Run `adk web .` (note the dot)
- Verify `drug_cost_agent/` folder exists

**API key errors:**
- Check that `GOOGLE_API_KEY` is set in environment variables
- Test: `python -c "import os; print(os.getenv('GOOGLE_API_KEY'))"`

**Database errors:**
- Ensure databases exist: `ls Data/*.db`
- Rebuild if needed: `python build_db.py`

**Import errors:**
- Test imports: `python -c "from drug_cost_agent import root_agent"`
- Verify dependencies: `pip install -r requirements.txt`

**Port already in use:**
- Use different port: `adk web . --port 8081`
- Or kill process using port 8080

*Visual representation of the project directory structure showing the organization of ADK agent, source code, tools, and data files.*
