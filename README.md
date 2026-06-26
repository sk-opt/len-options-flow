# LEN Options Flow Analysis — Multi-Agent CrewAI Demo

A multi-agent workflow that analyses unusual options open-interest (OI) and volume data for **LEN (Lennar Corporation)** using [CrewAI](https://github.com/crewAIInc/crewAI).

Two specialist agents collaborate in a **Flow** with automatic revision loop:

| Agent | Role |
|---|---|
| **ResearchAnalyst** | Produces a 5-section options flow analysis report based on CSV data + analysis framework |
| **QualityReviewer** | Verifies the report for **DATA** accuracy, **LOGIC** soundness, and **CONCEPT** correctness |

## Architecture

```
research_phase ──→ review_phase ──→ decide ──┬─ "approved" ──→ done
    │                  │  ↑                   │
    └── (initial) ─────┘  └── "revise" ───── revise_phase
                                              (loops back to review_phase)
```

1. **research_phase** — ResearchAnalyst reads the CSV and analysis framework, generates a 5-section report
2. **review_phase** — QualityReviewer scores each section on DATA / LOGIC / CONCEPT (PASS or FLAG)
3. **decide** (`@router`) — if any FLAG exists and retries < 2, routes to `"revise"`; otherwise `"approved"`
4. **revise_phase** — ResearchAnalyst receives the flagged review and corrects the report
5. Loops back to **review_phase** for re-evaluation
6. **done** — prints the approved report alongside the final review

## Environment Variables

### Per-agent configuration (recommended)

Set these to use different models or API providers for each agent.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `ANALYST_MODEL` | No | `OPENAI_MODEL` or `gpt-4o-mini` | LLM model for the Research Analyst |
| `ANALYST_API_KEY` | No | `OPENAI_API_KEY` | API key for the Research Analyst |
| `ANALYST_BASE_URL` | No | *(none)* | Custom base URL (e.g. for a local LLM or proxy) |
| `REVIEWER_MODEL` | No | `OPENAI_MODEL` or `gpt-4o-mini` | LLM model for the Quality Reviewer |
| `REVIEWER_API_KEY` | No | `OPENAI_API_KEY` | API key for the Quality Reviewer |
| `REVIEWER_BASE_URL` | No | *(none)* | Custom base URL for the Reviewer |

### Common fallback

If per-agent vars are not set, these serve as the fallback.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `OPENAI_API_KEY` | **Yes** (unless both per-agent keys set) | — | Fallback API key for both agents |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Fallback model for both agents |

## Usage

```
usage: len-options-flow.exe [-h] [-o OUTPUT] [--framework FRAMEWORK] csv

positional arguments:
  csv                   Path to the options flow CSV data file

options:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Path for the output markdown file (default: <csv_stem>_analysis_<timestamp>.md)
  --framework FRAMEWORK
                        Path to the analysis framework markdown file (default: bundled OptionsFlow.md)
```

### With virtual environment (source)

```powershell
$env:OPENAI_API_KEY="sk-..."
& "C:\Users\WDAGUtilityAccount\crewai-env\Scripts\python.exe" crewai_demo.py data.csv -o report.md
```

### With standalone exe

```powershell
len-options-flow.exe data.csv -o report.md
```

### Different models and keys for each agent

```powershell
$env:ANALYST_MODEL="gpt-4o"
$env:ANALYST_API_KEY="sk-analyst-key..."
$env:REVIEWER_MODEL="anthropic/claude-sonnet-4-20250514"
$env:REVIEWER_API_KEY="sk-reviewer-key..."
len-options-flow.exe data.csv
```

### Custom providers (via LiteLLM)

```powershell
$env:ANALYST_MODEL="groq/llama3-70b-8192"
$env:ANALYST_API_KEY="gsk-..."
$env:REVIEWER_MODEL="openai/gpt-4o-mini"
$env:REVIEWER_API_KEY="sk-..."
```

## Input Files

The script reads the CSV from the path provided on the command line and the analysis framework from the bundled `OptionsFlow.md` (or a custom path via `--framework`).

## Output

The final result is saved as a structured markdown file containing:

- **Approved Report** — the 5-section analysis (possibly revised after review flags)
- **Quality Review** — per-section DATA / LOGIC / CONCEPT verdicts with evidence
- **Verdict** — PASS or PASS (after N revisions)

The output is also printed to stdout for immediate inspection.

## Building the standalone exe

```powershell
# Requires PyInstaller (install in your CrewAI venv)
C:\Users\WDAGUtilityAccount\crewai-env\Scripts\python.exe -m pip install pyinstaller

# Build with --onedir (recommended) for reliability
C:\Users\WDAGUtilityAccount\crewai-env\Scripts\python.exe -m PyInstaller --noconfirm --onedir --console ^
    --name len-options-flow ^
    --add-data "OptionsFlow.md;." ^
    --hidden-import crewai ^
    --hidden-import crewai.flow ^
    --hidden-import pydantic ^
    --hidden-import httpx ^
    --hidden-import openai ^
    --hidden-import chromadb ^
    --hidden-import tokenizers ^
    --hidden-import tiktoken ^
    --collect-all pydantic ^
    --collect-all crewai ^
    --collect-all chromadb ^
    crewai_demo.py

# Run from the output folder
dist\len-options-flow\len-options-flow.exe data.csv -o report.md
```

Or simply run `build.bat` (included in the repo).

> **Note:** The folder at `dist\len-options-flow\` is self-contained. Zip it for distribution — no installation required on the target machine. Total size is ~430 MB due to bundled Python runtime, ChromaDB, ONNX runtime, and CrewAI.

## Report Sections

1. **Big picture** — stock price trend context
2. **Recent activity (30d)** — timeline of flows, support / resistance levels
3. **Flow intent** — speculative bet vs. institutional hedge; position types
4. **Market mechanics** — role of big players, dealers, market makers, and retail
5. **Conclusion & strategy** — actionable recommendation with example
