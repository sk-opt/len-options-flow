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

### Different models and keys for each agent

```powershell
$env:ANALYST_MODEL="gpt-4o"
$env:ANALYST_API_KEY="sk-analyst-key..."
$env:REVIEWER_MODEL="anthropic/claude-sonnet-4-20250514"
$env:REVIEWER_API_KEY="sk-reviewer-key..."
& "C:\Users\WDAGUtilityAccount\crewai-env\Scripts\python.exe" crewai_demo.py
```

### Same model, single API key (simple)

```powershell
$env:OPENAI_API_KEY="sk-..."
& "C:\Users\WDAGUtilityAccount\crewai-env\Scripts\python.exe" crewai_demo.py
```

### Custom providers (via LiteLLM)

```powershell
$env:ANALYST_MODEL="groq/llama3-70b-8192"
$env:ANALYST_API_KEY="gsk-..."
$env:REVIEWER_MODEL="openai/gpt-4o-mini"
$env:REVIEWER_API_KEY="sk-..."
```

## Input Files

The script reads two files at startup (paths are currently hardcoded):

| File | Content |
|---|---|
| `Options_Unusual_OI_LEN_20260624.csv` | Unusual options OI / volume data for LEN |
| `OptionsFlow.md` | Analysis framework (5-section methodology) |

## Report Sections

1. **Big picture** — stock price trend context
2. **Recent activity (30d)** — timeline of flows, support / resistance levels
3. **Flow intent** — speculative bet vs. institutional hedge; position types
4. **Market mechanics** — role of big players, dealers, market makers, and retail
5. **Conclusion & strategy** — actionable recommendation with example
