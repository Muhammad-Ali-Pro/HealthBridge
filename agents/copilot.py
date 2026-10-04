"""HealthBridge AI Clinical Copilot — a small multi-agent LangGraph pipeline.

    Doctor
      ↓  (service) consent / authorization check — no consent → no graph run
    record_retrieval     Record Retrieval Agent: fetches through a consent-bound handle (no DB access),
      ↓                   organizes authorized records; unconsented categories stay empty
    clinical_summary     Clinical Summary Agent: AIProvider.generate_structured → Pydantic-validated JSON
      ↓                   (no live AI → deterministic demo response, always labelled as such)
      ↓
    safety_consistency   Safety / Consistency Agent: rule-based checks always + LLM documentation checks
      ↓
    assemble             strip citations to unknown records, drop unsupported statements, review-only wording
      ↓
    Doctor review (accept / dismiss each flag, view sources)

Agents never touch the database and cannot widen what they were given. They depend only on the
provider-independent `AIProvider` interface (agents/providers.py), never on a vendor SDK.
"""

import json
from collections.abc import Callable
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from agents import retrieval, rules
from agents.providers import AIProvider, AIUnavailable
from agents.schemas import NOT_DOCUMENTED, ClinicalSummary, ReviewItem, ReviewOutput, SourceRef

NOT_CONNECTED = ("Live AI is currently unavailable. Configure a valid Gemini API key to run the Clinical Copilot. "
                 "Showing a demo response built by deterministic rules from the authorized records.")
INVALID = ("The live model's output did not pass validation and was discarded. Showing a demo response built by "
           "deterministic rules from the authorized records.")


def _live_failed(exc: AIUnavailable) -> str:
    return (f"Live AI is currently unavailable — {exc} Showing a demo response built by deterministic rules from "
            "the authorized records.")

SUMMARY_SYSTEM = f"""You are the Clinical Summary Agent of HealthBridge AI Clinical Copilot, a documentation
assistant for a licensed clinician. You ORGANIZE and SUMMARIZE the provided patient records, which have already
been filtered to what this clinician is authorized to see. Strict rules:
- Use ONLY facts explicitly present in the records. Never infer, guess or invent. If something is not in the
  records, write "{NOT_DOCUMENTED}"
- Do NOT diagnose, prescribe, recommend or change treatment. Report conditions only as documented
  (e.g. "Documented diagnosis: ..."), never as your own conclusion.
- Every list item must cite one or more source ids exactly as they appear in the records (for example "C-12",
  "RX-00003", "N-2", "PE-2", "PROFILE").
- Label patient-provided information as patient-provided and not clinician-verified.
- recent_history: recent consultations and notes (max 5, newest first). recent_prescriptions: max 5.
  important_changes: documented changes only (e.g. a medicine's documented strength changed).
  follow_up: documented follow-up instructions.
- Leave items_for_review as an empty list (the Safety / Consistency Agent fills it).
Return ONE JSON object that matches this JSON schema:
{{schema}}"""

REVIEW_SYSTEM = """You are the Safety / Consistency Agent (a documentation consistency reviewer) for HealthBridge.
You do NOT diagnose and you never recommend treatment. Look only for documentation-level issues in the provided,
already-authorized records: duplicate prescriptions, conflicting medication strength/dose/frequency, inconsistent
dates, conflicting allergy documentation (including patient-provided vs clinician-documented), allergy/medication
conflicts explicitly supported by the records, missing information, contradictory statements.
Phrase each issue as "Potential ... for clinician review". Cite source ids exactly as given.
Each item: {"severity": "low"|"medium"|"high", "category": one of "medication_discrepancy", "duplicate_medication",
"allergy_documentation", "allergy_conflict", "missing_information", "date_inconsistency", "other",
"issue": str (description), "evidence": str (reason for the flag), "sources": [str],
"recommendation": "Review underlying record."}. Return ONE JSON object: {"items": [...]}. Return {"items": []} if none."""


class CopilotState(TypedDict, total=False):
    source: retrieval.ScopedRecordSource
    dataset: dict
    sources: list[SourceRef]
    retrieval: dict[str, int]
    categories: list[str]
    summary: ClinicalSummary
    review_items: list[ReviewItem]
    generator: str
    notices: list[str]
    removed: int


def build_graph(provider: AIProvider | None):
    def record_retrieval(state: CopilotState) -> dict:
        dataset, sources, counts, categories = retrieval.retrieve(state["source"])
        return {"dataset": dataset, "sources": sources, "retrieval": counts, "categories": categories}

    def clinical_summary(state: CopilotState) -> dict:
        dataset = state["dataset"]
        if provider is None:
            return {"summary": rules.summarize(dataset), "generator": "rule_based", "notices": [NOT_CONNECTED]}
        try:
            schema = json.dumps(ClinicalSummary.model_json_schema())
            raw = provider.generate_structured(SUMMARY_SYSTEM.replace("{schema}", schema),
                                               json.dumps({"records": dataset}, default=str), ClinicalSummary)
            summary = ClinicalSummary.model_validate(raw)
            return {"summary": summary.model_copy(update={"items_for_review": []}), "generator": "llm", "notices": []}
        except AIUnavailable as exc:
            return {"summary": rules.summarize(dataset), "generator": "rule_based", "notices": [_live_failed(exc)]}
        except ValidationError:
            return {"summary": rules.summarize(dataset), "generator": "rule_based", "notices": [INVALID]}

    def safety_consistency(state: CopilotState) -> dict:
        items = rules.review(state["dataset"])  # reliable, deterministic baseline
        notices = list(state.get("notices", []))
        if provider is not None and state.get("generator") == "llm":
            try:
                raw = provider.generate_structured(REVIEW_SYSTEM, json.dumps({"records": state["dataset"]}, default=str),
                                                   ReviewOutput)
                extra = ReviewOutput.model_validate(raw).items
                known = {i.issue.lower()[:60] for i in items}
                items += [i for i in extra if i.issue.lower()[:60] not in known]
            except (AIUnavailable, ValidationError):
                notices.append("AI consistency review was unavailable; rule-based documentation checks were applied.")
        return {"review_items": [i.model_copy(update={"flag_id": None}) for i in items], "notices": notices}

    def assemble(state: CopilotState) -> dict:
        # Valid citations: every retrieved record id, plus the prescriptions behind current medications
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
        reports = keep(summary.important_reports, strict) if state["dataset"]["lab_reports"] else []
        final = ClinicalSummary(
            patient_snapshot=snapshot,
            active_conditions=keep(summary.active_conditions, strict),
            current_medications=keep(summary.current_medications, strict),
            recent_history=keep(summary.recent_history, strict),
            recent_prescriptions=keep(summary.recent_prescriptions, strict),
            important_changes=keep(summary.important_changes, strict),
            follow_up=keep(summary.follow_up, strict),
            important_reports=reports,  # never present when lab reports were not retrieved (not consented)
            items_for_review=keep(state["review_items"], False),
        )
        return {"summary": final, "removed": removed}

    graph = StateGraph(CopilotState)
    graph.add_node("record_retrieval", record_retrieval)
    graph.add_node("clinical_summary", clinical_summary)
    graph.add_node("safety_consistency", safety_consistency)
    graph.add_node("assemble", assemble)
    graph.add_edge(START, "record_retrieval")
    graph.add_edge("record_retrieval", "clinical_summary")
    graph.add_edge("clinical_summary", "safety_consistency")
    graph.add_edge("safety_consistency", "assemble")
    graph.add_edge("assemble", END)
    return graph.compile()


AGENT_STEPS = ["record_retrieval", "clinical_summary", "safety_consistency", "assemble"]
STAGE_LABEL = {
    "record_retrieval": "Record Retrieval Agent · fetching consented records only…",
    "clinical_summary": "Clinical Summary Agent · summarizing authorized history…",
    "safety_consistency": "Safety / Consistency Agent · checking for documentation discrepancies…",
    "assemble": "Preparing clinician review · verifying every source…",
}


def run(source: retrieval.ScopedRecordSource, provider: AIProvider | None,
        on_progress: Callable[[str], None] | None = None) -> CopilotState:
    progress = on_progress or (lambda _msg: None)
    app = build_graph(provider)
    state: CopilotState = {"source": source}
    progress(STAGE_LABEL["record_retrieval"])
    for chunk in app.stream(state, stream_mode="updates"):
        for node, update in chunk.items():
            state.update(update)
            nxt = AGENT_STEPS.index(node) + 1
            if nxt < len(AGENT_STEPS):
                progress(STAGE_LABEL[AGENT_STEPS[nxt]])
    return state
