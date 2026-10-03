"""HealthBridge Clinical Copilot — a small LangGraph pipeline over PRE-AUTHORIZED records.

    (service) consent check + authorized record retrieval      ← happens BEFORE this graph
        ↓
    organize_records     deterministic: citable, chronological dataset
        ↓
    clinical_summary     Clinical Summary Agent (LLM → Pydantic-validated JSON; rule-based fallback)
        ↓
    consistency_review   Consistency Review Agent (rules always + LLM documentation checks)
        ↓
    assemble             strip unsupported citations, enforce review-only wording

Agents never touch the database and cannot widen what they were given.
"""

import json
from collections.abc import Callable
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from agents import organizer, rules
from agents.llm import LLMUnavailable
from agents.schemas import ClinicalSummary, ReviewItem, ReviewOutput, SourceRef
from core.schemas import AuthorizedRecord

LLMFn = Callable[[str, str], dict]

UNAVAILABLE = ("AI summary is temporarily unavailable. Showing a rule-based summary built directly from the "
               "authorized records (no AI).")
INVALID = ("The AI output did not pass validation and was discarded. Showing a rule-based summary built directly "
           "from the authorized records.")

SUMMARY_SYSTEM = """You are HealthBridge Clinical Copilot, a documentation assistant for a licensed clinician.
You ORGANIZE and SUMMARIZE the provided patient records, which have already been filtered to what this clinician
is authorized to see. Strict rules:
- Use ONLY facts explicitly present in the records. Never infer, guess or invent. If something is not in the
  records, write "Not documented in available records."
- Do NOT diagnose, prescribe, recommend or change treatment. Report conditions only as documented
  (e.g. "Documented diagnosis: ..."), never as your own conclusion.
- Every list item must cite one or more source ids exactly as they appear in the records (for example "C-12",
  "RX-00003", "LAB-00001", "PE-2", "PROFILE").
- Label patient-provided information as patient-provided and not clinician-verified.
- Keep recent_history and recent_prescriptions to at most 5 items each, newest first.
- Leave items_for_review as an empty list (a separate reviewer fills it).
Return ONE JSON object that matches this JSON schema:
{schema}"""

REVIEW_SYSTEM = """You are a documentation consistency reviewer for HealthBridge. You do NOT diagnose and you never
recommend treatment. Look only for documentation-level issues in the provided, already-authorized records:
duplicate medication entries, conflicting medication strength/dose/frequency, inconsistent dates, conflicting allergy
documentation (including patient-provided vs clinician-documented), missing information, contradictory statements.
Phrase each issue as "Potential ... for clinician review". Cite source ids exactly as given.
Each item: {"severity": "low"|"medium"|"high", "issue": str, "evidence": str, "sources": [str],
"recommendation": "Review underlying record."}. Return ONE JSON object: {"items": [...]}. Return {"items": []} if none."""


class CopilotState(TypedDict, total=False):
    record: AuthorizedRecord
    dataset: dict
    sources: list[SourceRef]
    summary: ClinicalSummary
    review_items: list[ReviewItem]
    generator: str
    notices: list[str]
    removed: int


def build_graph(llm: LLMFn | None):
    def organize_records(state: CopilotState) -> dict:
        dataset, sources = organizer.organize(state["record"])
        return {"dataset": dataset, "sources": sources}

    def clinical_summary(state: CopilotState) -> dict:
        dataset = state["dataset"]
        if llm is None:
            return {"summary": rules.summarize(dataset), "generator": "rule_based", "notices": [UNAVAILABLE]}
        try:
            schema = json.dumps(ClinicalSummary.model_json_schema())
            raw = llm(SUMMARY_SYSTEM.replace("{schema}", schema), json.dumps({"records": dataset}, default=str))
            summary = ClinicalSummary.model_validate(raw)
            return {"summary": summary.model_copy(update={"items_for_review": []}), "generator": "llm", "notices": []}
        except LLMUnavailable:
            return {"summary": rules.summarize(dataset), "generator": "rule_based", "notices": [UNAVAILABLE]}
        except ValidationError:
            return {"summary": rules.summarize(dataset), "generator": "rule_based", "notices": [INVALID]}

    def consistency_review(state: CopilotState) -> dict:
        items = rules.review(state["dataset"])  # reliable, deterministic baseline
        notices = list(state.get("notices", []))
        if llm is not None and state.get("generator") == "llm":
            try:
                raw = llm(REVIEW_SYSTEM, json.dumps({"records": state["dataset"]}, default=str))
                extra = ReviewOutput.model_validate(raw).items
                known = {i.issue.lower()[:60] for i in items}
                items += [i for i in extra if i.issue.lower()[:60] not in known]
            except (LLMUnavailable, ValidationError):
                notices.append("AI consistency review was unavailable; rule-based documentation checks were applied.")
        return {"review_items": items, "notices": notices}

    def assemble(state: CopilotState) -> dict:
        # Valid citations: every organized record id, plus the prescriptions behind current medications
        # (medications may be shared without the full prescription history).
        known = {s.id for s in state["sources"]} | {m["source"] for m in state["dataset"]["current_medications"]}
        summary = state["summary"]
        removed = 0

        def keep(items, require_source: bool):
            nonlocal removed
            out = []
            for it in items:
                it = it.model_copy(update={"sources": [s for s in it.sources if s in known]})
                if require_source and not it.sources:
                    removed += 1  # unsupported statement: no verifiable source → not shown
                    continue
                out.append(it)
            return out

        strict = state.get("generator") == "llm"
        pt = state["dataset"]["patient"]
        snapshot = summary.patient_snapshot.model_copy(update={
            "age": pt["age"], "sex": pt["sex"],  # identity facts always come from the record, not the model
            "allergies": keep(summary.patient_snapshot.allergies, strict),
            "patient_provided": keep(summary.patient_snapshot.patient_provided, strict),
        })
        final = ClinicalSummary(
            patient_snapshot=snapshot,
            active_conditions=keep(summary.active_conditions, strict),
            current_medications=keep(summary.current_medications, strict),
            recent_history=keep(summary.recent_history, strict),
            recent_prescriptions=keep(summary.recent_prescriptions, strict),
            important_reports=keep(summary.important_reports, strict),
            items_for_review=keep(state["review_items"], False),
        )
        return {"summary": final, "removed": removed}

    graph = StateGraph(CopilotState)
    graph.add_node("organize_records", organize_records)
    graph.add_node("clinical_summary", clinical_summary)
    graph.add_node("consistency_review", consistency_review)
    graph.add_node("assemble", assemble)
    graph.add_edge(START, "organize_records")
    graph.add_edge("organize_records", "clinical_summary")
    graph.add_edge("clinical_summary", "consistency_review")
    graph.add_edge("consistency_review", "assemble")
    graph.add_edge("assemble", END)
    return graph.compile()


NEXT_STAGE = {
    "organize_records": "Generating summary…",
    "clinical_summary": "Checking for documentation inconsistencies…",
    "consistency_review": "Preparing clinician review…",
}


def run(record: AuthorizedRecord, llm: LLMFn | None, on_progress: Callable[[str], None] | None = None) -> CopilotState:
    progress = on_progress or (lambda _msg: None)
    app = build_graph(llm)
    state: CopilotState = {"record": record}
    progress("Organizing clinical timeline…")
    for chunk in app.stream(state, stream_mode="updates"):
        for node, update in chunk.items():
            state.update(update)
            if node in NEXT_STAGE:
                progress(NEXT_STAGE[node])
    return state
