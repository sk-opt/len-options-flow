import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from crewai import Agent, Task, Crew, LLM
from crewai.flow import Flow, listen, or_, start, router
from pydantic import BaseModel


MAX_RETRIES = 5


def _bundled_path(name: str) -> Path:
    """Resolve a bundled file — works both with source and PyInstaller."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / name


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class OptionsFlowState(BaseModel):
    report: str = ""
    review: str = ""
    retries: int = 0
    feedback: str = ""


def _make_analyst(framework: str, llm: LLM) -> Agent:
    return Agent(
        llm=llm,
        role="Senior Options Flow Research Analyst",
        goal=(
            "Analyse the attached CSV of unusual options OI/volume data"
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


def _make_reviewer(llm: LLM) -> Agent:
    return Agent(
        llm=llm,
        role="Senior Options Flow Quality Reviewer",
        goal=(
            "Verify the Research Analyst's report for factual accuracy against the "
            "raw CSV data, the soundness of its logical reasoning, and the correctness "
            "of its options concepts. Flag any unsupported, illogical, or conceptually "
            "incorrect claims."
        ),
        backstory=(
            "You are a meticulous quality assurance specialist with deep expertise in "
            "options market structure, derivatives pricing, and market maker mechanics.\n\n"
            "Your job has three verification dimensions:\n"
            "  1. Data accuracy – cross-reference every quantitative claim against the CSV\n"
            "  2. Logic soundness – ensure conclusions follow from the evidence presented\n"
            "  3. Concept correctness – verify that options concepts (OI, greeks, hedging,\n"
            "     call/put dynamics, dealer positioning) are applied correctly\n\n"
            "You score each of the 5 sections independently on all three dimensions, "
            "providing specific CSV row citations and reasoning explanations for each flag, "
            "plus an overall PASS / REVISE verdict."
        ),
        verbose=True,
        allow_delegation=False,
    )


class OptionsFlowAnalysis(Flow[OptionsFlowState]):

    def __init__(self, csv_data: str, framework: str,
                 analyst_llm: LLM, reviewer_llm: LLM,
                 max_retries: int = MAX_RETRIES):
        super().__init__()
        self.csv_data = csv_data
        self.framework = framework
        self.analyst_llm = analyst_llm
        self.reviewer_llm = reviewer_llm
        self.max_retries = max_retries

    # --------------------------------------------------------------
    # Phase 1 – initial research
    # --------------------------------------------------------------
    @start()
    def research_phase(self):
        print(f"\n--- [1/{self.max_retries + 1}] Initial research phase ---\n")
        analyst = _make_analyst(self.framework, self.analyst_llm)
        task = Task(
            description=(
                f"Produce a thorough options flow analysis based on the following CSV data.\n\n"
                f"--- CSV DATA ---\n{self.csv_data}\n--- END CSV ---\n\n"
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
            agent=analyst,
        )
        crew = Crew(agents=[analyst], tasks=[task], verbose=True)
        result = crew.kickoff()
        self.state.report = result.raw

    # --------------------------------------------------------------
    # Phase 2 – quality review (triggered by initial OR revised report)
    # --------------------------------------------------------------
    @listen(or_("research_phase", "resume_review"))
    def review_phase(self):
        print(f"\n--- [{self.state.retries + 1}/{self.max_retries + 1}] Quality review phase ---\n")
        reviewer = _make_reviewer(self.reviewer_llm)
        feedback_hint = (
            f"\n--- PREVIOUS FEEDBACK (verify these were fixed) ---\n"
            f"{self.state.feedback}\n--- END ---\n"
            if self.state.feedback
            else ""
        )
        task = Task(
            description=(
                f"Review the Research Analyst's report for correctness.\n\n"
                f"--- REPORT TO REVIEW ---\n{self.state.report}\n--- END ---\n\n"
                f"--- REFERENCE CSV DATA ---\n{self.csv_data}\n--- END CSV ---\n\n"
                f"{feedback_hint}"
                f"For each of the 5 sections, evaluate on three dimensions:\n"
                f"  DATA:    PASS / FLAG – are factual claims supported by the CSV?\n"
                f"  LOGIC:   PASS / FLAG – is the reasoning coherent and sound?\n"
                f"  CONCEPT: PASS / FLAG – are options concepts correctly applied?\n\n"
                f"When you FLAG, cite the specific CSV row(s) and explain the issue.\n\n"
                f"Output a structured validation report:\n"
                f"  Section 1:  DATA=...  LOGIC=...  CONCEPT=...  (evidence)\n"
                f"  Section 2:  DATA=...  LOGIC=...  CONCEPT=...  (evidence)\n"
                f"  Section 3:  DATA=...  LOGIC=...  CONCEPT=...  (evidence)\n"
                f"  Section 4:  DATA=...  LOGIC=...  CONCEPT=...  (evidence)\n"
                f"  Section 5:  DATA=...  LOGIC=...  CONCEPT=...  (evidence)\n"
                f"  -----\n"
                f"  Overall Verdict: PASS / REVISE"
            ),
            expected_output=(
                "A structured validation report showing DATA/LOGIC/CONCEPT verdicts "
                "per section with evidence citations, plus an overall verdict."
            ),
            agent=reviewer,
        )
        crew = Crew(agents=[reviewer], tasks=[task], verbose=True)
        result = crew.kickoff()
        self.state.review = result.raw

    # --------------------------------------------------------------
    # Router – decide whether to approve or request revision
    # --------------------------------------------------------------
    @router(review_phase)
    def decide(self) -> Literal["revise", "approved"]:
        review_text = self.state.review.upper()
        has_flag = any(
            m in review_text
            for m in ["FLAG", "REVISE", "DATA_FLAG", "LOGIC_FLAG", "CONCEPT_FLAG"]
        )
        if has_flag and self.state.retries < self.max_retries:
            self.state.retries += 1
            self.state.feedback = self.state.review
            print(f"\n→ Revision {self.state.retries}/{self.max_retries} needed, sending back to analyst\n")
            return "revise"
        print(f"\n→ Report approved after {self.state.retries} revision(s)\n")
        return "approved"

    # --------------------------------------------------------------
    # Phase 3 – analyst revises report based on reviewer feedback
    # --------------------------------------------------------------
    @listen("revise")
    def revise_phase(self):
        print(f"\n--- Revision {self.state.retries}/{self.max_retries} in progress ---\n")
        analyst = _make_analyst(self.framework, self.analyst_llm)
        task = Task(
            description=(
                f"Revise your previous options flow analysis based on the "
                f"reviewer feedback below.\n\n"
                f"--- YOUR PREVIOUS REPORT ---\n{self.state.report}\n--- END ---\n\n"
                f"--- REVIEWER FEEDBACK (fix every issue) ---\n{self.state.feedback}\n--- END ---\n\n"
                f"--- REFERENCE CSV DATA ---\n{self.csv_data}\n--- END CSV ---\n\n"
                f"Produce a corrected 5-section report addressing every flag raised above."
            ),
            expected_output=(
                "A corrected 5-section options flow analysis report in plain text, "
                "with each section clearly labelled."
            ),
            agent=analyst,
        )
        crew = Crew(agents=[analyst], tasks=[task], verbose=True)
        result = crew.kickoff()
        self.state.report = result.raw

    # --------------------------------------------------------------
    # Router – chain back to review after revision completes
    # --------------------------------------------------------------
    @router("revise_phase")
    def resume_review(self):
        return "resume_review"

    # --------------------------------------------------------------
    # Terminal – produce final markdown
    # --------------------------------------------------------------
    @listen("approved")
    def done(self):
        verdict = "PASS" if self.state.retries == 0 else f"PASS (after {self.state.retries} revision(s))"
        md = (
            f"# Options Flow Analysis\n\n"            
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"**Analyst LLM:** {self.analyst_llm.model}\n\n"
            f"**Reviewer LLM:** {self.reviewer_llm.model}\n\n"
            f"**Revisions:** {self.state.retries}\n\n"
            f"---\n\n"
            f"## Approved Report\n\n"
            f"{self.state.report}\n\n"
            f"---\n\n"
            f"## Quality Review\n\n"
            f"{self.state.review}\n\n"
            f"---\n\n"
            f"## Verdict\n\n"
            f"{verdict}\n"
        )
        print(md)
        return md


def _env(key: str, fallback: str | None = None) -> str:
    """Read an env var, exiting with a clear message if missing."""
    val = os.getenv(key, fallback)
    if val is None:
        print(f"ERROR: environment variable {key} is not set.", file=sys.stderr)
        sys.exit(1)
    return val


def _llm(model: str, api_key: str, base_url: str | None) -> LLM:
    """Build an LLM instance.

    When a custom *base_url* is supplied the model name is sent as-is
    (e.g. ``openai/gpt-oss-120b``) and the native OpenAI SDK is forced
    so that the full model string reaches the custom endpoint.
    """
    extra: dict[str, Any] = {"model": model, "api_key": api_key, "base_url": base_url}
    if base_url:
        extra["provider"] = "openai"
    return LLM(**{k: v for k, v in extra.items() if v is not None})


def main():
    parser = argparse.ArgumentParser(
        description="LEN Options Flow Analysis — CrewAI multi-agent demo"
    )
    parser.add_argument("csv", help="Path to the options flow CSV data file")
    parser.add_argument(
        "-o", "--output",
        help="Path for the output markdown file (default: <csv_stem>_analysis_<timestamp>.md)",
    )
    parser.add_argument(
        "--framework",
        default=str(_bundled_path("OptionsFlow.md")),
        help="Path to the analysis framework markdown file (default: bundled OptionsFlow.md)",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    framework_path = Path(args.framework)
    if not framework_path.exists():
        print(f"ERROR: Framework file not found: {framework_path}", file=sys.stderr)
        sys.exit(1)

    output_path = args.output
    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(csv_path.with_name(f"{csv_path.stem}_analysis_{ts}.md"))

    # ---- per-agent model config with fallback chain ----
    analyst_model = os.getenv("ANALYST_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    analyst_key   = os.getenv("ANALYST_API_KEY") or _env("OPENAI_API_KEY")
    analyst_base  = os.getenv("ANALYST_BASE_URL") or None

    reviewer_model = os.getenv("REVIEWER_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    reviewer_key   = os.getenv("REVIEWER_API_KEY") or _env("OPENAI_API_KEY")
    reviewer_base  = os.getenv("REVIEWER_BASE_URL") or None

    analyst_llm  = _llm(analyst_model, analyst_key, analyst_base)
    reviewer_llm = _llm(reviewer_model, reviewer_key, reviewer_base)

    csv_data = load_text(csv_path)
    framework = load_text(framework_path)

    flow = OptionsFlowAnalysis(
        csv_data=csv_data,
        framework=framework,
        analyst_llm=analyst_llm,
        reviewer_llm=reviewer_llm,
    )
    result = flow.kickoff()

    if result is None:
        print("ERROR: Flow completed without producing a result.", file=sys.stderr)
        sys.exit(1)

    Path(output_path).write_text(result, encoding="utf-8")
    print(f"\nAnalysis saved to: {output_path}")


if __name__ == "__main__":
    main()
