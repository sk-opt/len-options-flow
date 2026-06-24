import os
import sys
from pathlib import Path

from crewai import Agent, Task, Crew, LLM
from crewai.flow import Flow, listen, or_, start, router
from pydantic import BaseModel


CSV_PATH = Path(r"C:\Users\WDAGUtilityAccount\Desktop\Downloads\Options_Unusual_OI_LEN_20260624.csv")
MD_PATH  = Path(r"C:\Users\WDAGUtilityAccount\Desktop\Downloads\OptionsFlow.md")
MAX_RETRIES = 2


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
        analyst = _make_analyst(self.framework, self.analyst_llm)
        task = Task(
            description=(
                f"Produce a thorough options flow analysis for LEN based on the following CSV data.\n\n"
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
    @listen(or_("research_phase", "revise_phase"))
    def review_phase(self):
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
    def decide(self):
        review_text = self.state.review.upper()
        has_flag = any(
            m in review_text
            for m in ["FLAG", "REVISE", "DATA_FLAG", "LOGIC_FLAG", "CONCEPT_FLAG"]
        )
        if has_flag and self.state.retries < self.max_retries:
            self.state.retries += 1
            self.state.feedback = self.state.review
            return "revise"
        return "approved"

    # --------------------------------------------------------------
    # Phase 3 – analyst revises report based on reviewer feedback
    # --------------------------------------------------------------
    @listen("revise")
    def revise_phase(self):
        analyst = _make_analyst(self.framework, self.analyst_llm)
        task = Task(
            description=(
                f"Revise your previous options flow analysis for LEN based on the "
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
    # Terminal – print final approved result
    # --------------------------------------------------------------
    @listen("approved")
    def done(self):
        output = (
            f"=== APPROVED REPORT ===\n{self.state.report}\n\n"
            f"=== FINAL REVIEW ===\n{self.state.review}"
        )
        print(output)
        return output


def _strip_provider(model: str) -> str:
    """Strip a LiteLLM provider prefix (e.g. 'openai/') when a custom
    base_url is used, so the model name is sent verbatim to that endpoint."""
    return model.split("/", 1)[-1] if "/" in model else model


def _env(key: str, fallback: str | None = None) -> str:
    """Read an env var, exiting with a clear message if missing."""
    val = os.getenv(key, fallback)
    if val is None:
        print(f"ERROR: environment variable {key} is not set.", file=sys.stderr)
        sys.exit(1)
    return val


def main():
    # ---- per-agent model config with fallback chain ----
    analyst_model_raw = os.getenv("ANALYST_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    analyst_key   = os.getenv("ANALYST_API_KEY") or _env("OPENAI_API_KEY")
    analyst_base  = os.getenv("ANALYST_BASE_URL") or None
    analyst_model = _strip_provider(analyst_model_raw) if analyst_base else analyst_model_raw

    reviewer_model_raw = os.getenv("REVIEWER_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    reviewer_key   = os.getenv("REVIEWER_API_KEY") or _env("OPENAI_API_KEY")
    reviewer_base  = os.getenv("REVIEWER_BASE_URL") or None
    reviewer_model = _strip_provider(reviewer_model_raw) if reviewer_base else reviewer_model_raw

    analyst_llm  = LLM(model=analyst_model, api_key=analyst_key, base_url=analyst_base)
    reviewer_llm = LLM(model=reviewer_model, api_key=reviewer_key, base_url=reviewer_base)

    csv_data = load_text(CSV_PATH)
    framework = load_text(MD_PATH)

    flow = OptionsFlowAnalysis(
        csv_data=csv_data,
        framework=framework,
        analyst_llm=analyst_llm,
        reviewer_llm=reviewer_llm,
    )
    flow.kickoff()


if __name__ == "__main__":
    main()
