import os
import sys
from pathlib import Path

from crewai import Agent, Task, Crew, Process


CSV_PATH = Path(r"C:\Users\WDAGUtilityAccount\Desktop\Downloads\Options_Unusual_OI_LEN_20260624.csv")
MD_PATH  = Path(r"C:\Users\WDAGUtilityAccount\Desktop\Downloads\OptionsFlow.md")


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    csv_data = load_text(CSV_PATH)
    framework = load_text(MD_PATH)

    # ------------------------------------------------------------------
    # Agent 1 – Research Analyst
    # ------------------------------------------------------------------
    research_analyst = Agent(
        role="Senior Options Flow Research Analyst",
        goal=(
            "Analyse the attached CSV of unusual options OI/volume data for LEN "
            "using the provided analysis framework and produce a complete 5-section report."
        ),
        backstory=(
            f"You are an expert in options trading and flow analysis. "
            f"Your core analysis methodology is:\n\n{framework}\n\n"
            "You have a keen eye for detecting institutional vs retail activity, "
            "and you always ground your conclusions in the actual data."
        ),
        verbose=True,
        allow_delegation=False,
    )

    # ------------------------------------------------------------------
    # Agent 2 – Quality Reviewer
    # ------------------------------------------------------------------
    quality_reviewer = Agent(
        role="Senior Options Flow Quality Reviewer",
        goal=(
            "Verify the Research Analyst's report for factual correctness against the "
            "raw CSV data. Flag any claim that is not supported or contradicted by the data."
        ),
        backstory=(
            "You are a meticulous quality assurance specialist with deep expertise in "
            "options market structure. Your job is to cross-reference every quantitative "
            "and qualitative claim in a research report against the source CSV data.\n\n"
            "You score each of the 5 sections independently:\n"
            "  PASS  – all claims are supported by the data\n"
            "  FLAG  – one or more claims are unsupported, exaggerated, or contradicted\n\n"
            "You provide specific CSV row citations for each flag and an overall PASS/REVISE verdict."
        ),
        verbose=True,
        allow_delegation=False,
    )

    # ------------------------------------------------------------------
    # Task 1 – Research
    # ------------------------------------------------------------------
    research_task = Task(
        description=(
            f"Produce a thorough options flow analysis for LEN based on the following CSV data.\n\n"
            f"--- CSV DATA ---\n{csv_data}\n--- END CSV ---\n\n"
            f"Structure your report using these 5 sections exactly:\n"
            f"1/. Key observation (big picture), stock price trend\n"
            f"2/. Dominant recent activity (30 days), timeline of flows, support / resistance\n"
            f"3/. What is the flow telling us — speculative bet on direction or institutional hedge?\n"
            f"   Are big players opening long/short call/put, long/short straddle/strangle, collar?\n"
            f"4/. Possible interpretations — explain the role, mechanism and interaction between "
            f"   big player, dealer, market maker and retail investor.\n"
            f"5/. Conclusion and suggested strategy with example for retail investor. "
            f"Should they follow the big player view or do the opposite?"
        ),
        expected_output=(
            "A complete 5-section options flow analysis report in plain text, "
            "with each section clearly labelled."
        ),
        agent=research_analyst,
    )

    # ------------------------------------------------------------------
    # Task 2 – Quality Review (receives research output via context)
    # ------------------------------------------------------------------
    review_task = Task(
        description=(
            "Review the Research Analyst's report for correctness against the original CSV data.\n\n"
            f"--- REFERENCE CSV DATA ---\n{csv_data}\n--- END CSV ---\n\n"
            "For each of the 5 sections, determine:\n"
            "  PASS  – every claim is factually supported by the CSV\n"
            "  FLAG  – a claim is unsubstantiated, exaggerated, or contradicted\n\n"
            "When you FLAG a section, cite the specific CSV row(s) that contradict the claim.\n\n"
            "Output a structured validation report with:\n"
            "  Section 1: PASS/FLAG (evidence)\n"
            "  Section 2: PASS/FLAG (evidence)\n"
            "  Section 3: PASS/FLAG (evidence)\n"
            "  Section 4: PASS/FLAG (evidence)\n"
            "  Section 5: PASS/FLAG (evidence)\n"
            "  -----\n"
            "  Overall Verdict: PASS / REVISE"
        ),
        expected_output=(
            "A structured validation report showing PASS/FLAG per section with "
            "CSV row citations, plus an overall verdict."
        ),
        agent=quality_reviewer,
        context=[research_task],
    )

    # ------------------------------------------------------------------
    # Crew – sequential execution
    # ------------------------------------------------------------------
    crew = Crew(
        agents=[research_analyst, quality_reviewer],
        tasks=[research_task, review_task],
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff()
    print("\n" + "=" * 72)
    print("FINAL OUTPUT")
    print("=" * 72)
    print(result)


if __name__ == "__main__":
    main()
