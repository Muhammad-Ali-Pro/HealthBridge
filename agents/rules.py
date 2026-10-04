"""Deterministic summary + documentation-consistency checks (no AI).

Used (a) always, as a reliable baseline for documentation checks, and (b) as the full fallback when
the LLM is unavailable. Wording is review-oriented: it never diagnoses or recommends treatment.
"""

from collections import defaultdict
from datetime import datetime

from agents.schemas import (
    NOT_DOCUMENTED,
    ClinicalSummary,
    MedicationItem,
    PatientSnapshot,
    ReviewItem,
    SourcedItem,
)
from data.catalog import load_drug_catalog


def summarize(dataset: dict) -> ClinicalSummary:
    pt = dataset["patient"]
    snapshot = PatientSnapshot(
        age=pt["age"], sex=pt["sex"],
        allergies=[SourcedItem(text=f"{a} (clinician-documented)", sources=["PROFILE"])
                   for a in pt["clinician_documented_allergies"]],
        patient_provided=[SourcedItem(text=f"{e['title']}: {e['details']} (patient-provided, not clinician-verified)",
                                      sources=[e["id"]]) for e in dataset["patient_provided"]],
    )
    conditions = [SourcedItem(text=f"{c} (documented in patient profile)", sources=["PROFILE"])
                  for c in (pt["clinician_documented_conditions"] or [])]
    seen = {c.lower() for c in (pt["clinician_documented_conditions"] or [])}
    for c in reversed(dataset["consultations"]):
        dx = c["diagnosis"].strip()
        if dx and dx.lower() not in seen:
            seen.add(dx.lower())
            conditions.append(SourcedItem(text=f"Documented diagnosis: {dx} ({c['date']}, {c['organization']})",
                                          sources=[c["id"]]))
    meds = [MedicationItem(medicine=m["medicine"], strength=m["strength"] or NOT_DOCUMENTED,
                           dosage=m["dosage"] or NOT_DOCUMENTED, frequency=m["frequency"] or NOT_DOCUMENTED,
                           date=m["since"], sources=[m["source"]]) for m in dataset["current_medications"]]
    history = [SourcedItem(text=f"{c['date']} · {c['organization']} ({c['provider']}): {c['reason']}"
                                + (f" — {c['assessment'] or c['diagnosis']}" if (c['assessment'] or c['diagnosis']) else ""),
                           sources=[c["id"]]) for c in reversed(dataset["consultations"][-5:])]
    history += [SourcedItem(text=f"{n['date']} · Note by {n['provider']}: {n['content']}", sources=[n["id"]])
                for n in reversed(dataset["clinical_notes"][-3:])]
    prescriptions = [SourcedItem(
        text=f"{rx['date']} · " + ", ".join(f"{i['medicine']} {i['strength']} {i['frequency']}" for i in rx["items"])
             + f" — {rx['provider']}, {rx['organization']} ({rx['status'].replace('_', ' ')})",
        sources=[rx["id"]]) for rx in reversed(dataset["prescriptions"][-5:])]
    reports = []
    for r in reversed(dataset["lab_reports"]):
        flagged = [f"{v['analyte']} {v['value']} {v['unit']} ({v['flag']}, ref {v['reference']})"
                   for v in r["values"] if v.get("flag") not in (None, "normal")]
        text = f"{r['date']} · {r['test']} ({r['laboratory']}): " + ("; ".join(flagged) if flagged else "values within reference ranges")
        reports.append(SourcedItem(text=text, sources=[r["id"]]))
    follow_up = [SourcedItem(text=f"{c['date']} · {c['organization']} ({c['provider']}): {c['follow_up']}",
                             sources=[c["id"]]) for c in reversed(dataset["consultations"]) if c["follow_up"].strip()][:3]
    return ClinicalSummary(patient_snapshot=snapshot, active_conditions=conditions, current_medications=meds,
                           recent_history=history, recent_prescriptions=prescriptions,
                           important_changes=important_changes(dataset), follow_up=follow_up,
                           important_reports=reports, items_for_review=review(dataset))


def important_changes(dataset: dict) -> list[SourcedItem]:
    """Documented changes only — e.g. a medicine whose strength/frequency differs between prescriptions."""
    changes: list[SourcedItem] = []
    history: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    for rx in dataset["prescriptions"]:  # chronological
        for i in rx["items"]:
            history[i["medicine"].strip().lower()].append((rx, i))
    for entries in history.values():
        for (rx_a, a), (rx_b, b) in zip(entries, entries[1:]):
            if (a["strength"], a["frequency"]) != (b["strength"], b["frequency"]):
                changes.append(SourcedItem(
                    text=f"{b['medicine']}: documented as {a['strength']} {a['frequency']} ({rx_a['date']}), later "
                         f"{b['strength']} {b['frequency']} ({rx_b['date']}).", sources=[rx_a["id"], rx_b["id"]]))
    for rx in dataset["prescriptions"][-2:]:
        if rx["status"] in ("issued", "sent"):
            names = ", ".join(f"{i['medicine']} {i['strength']}" for i in rx["items"])
            where = f" — sent to {rx['pharmacy']}" if rx.get("pharmacy") and rx["status"] == "sent" else ""
            changes.append(SourcedItem(text=f"New prescription {rx['date']}: {names}{where}.", sources=[rx["id"]]))
    return changes


def review(dataset: dict) -> list[ReviewItem]:
    items: list[ReviewItem] = []

    # 1. Same medicine documented with different strength / frequency across prescriptions.
    by_drug: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    for rx in dataset["prescriptions"]:
        for i in rx["items"]:
            by_drug[i["medicine"].strip().lower()].append((rx, i))
    for entries in by_drug.values():
        variants = {(i["strength"].strip().lower(), i["frequency"].strip().lower()) for _, i in entries}
        if len(variants) > 1:
            name = entries[0][1]["medicine"]
            evidence = "; ".join(f"{i['strength']} {i['frequency']} ({rx['id']}, {rx['date']}, {rx['provider']})"
                                 for rx, i in entries)
            items.append(ReviewItem(
                severity="medium", category="medication_discrepancy",
                issue=f"Potential medication documentation discrepancy for clinician review: {name} is documented "
                      "with different strength or frequency across prescriptions.",
                evidence=evidence, sources=[rx["id"] for rx, _ in entries]))

    # 2. The same medicine appearing more than once among current medications.
    current = defaultdict(list)
    for m in dataset["current_medications"]:
        current[m["medicine"].strip().lower()].append(m)
    for meds in current.values():
        if len(meds) > 1:
            items.append(ReviewItem(
                severity="medium", category="duplicate_medication",
                issue=f"{meds[0]['medicine']} appears in more than one active prescription.",
                evidence="; ".join(f"{m['strength']} {m['frequency']} ({m['source']})" for m in meds),
                sources=[m["source"] for m in meds]))

    # 3. Patient-provided allergy not reflected in the clinician-documented allergy list.
    documented = [a.lower() for a in dataset["patient"]["clinician_documented_allergies"]]
    for e in dataset["patient_provided"]:
        if e["type"] == "allergy":
            word = e["title"].split("(")[0].strip().lower()
            if not any(word in a or a in word for a in documented):
                items.append(ReviewItem(
                    severity="medium", category="allergy_documentation",
                    issue="Allergy documentation inconsistency: a patient-reported allergy is not in the "
                          "clinician-documented allergy list.",
                    evidence=f"Patient-provided: {e['title']} ({e['date']}). Clinician-documented allergies: "
                             f"{', '.join(dataset['patient']['clinician_documented_allergies']) or 'none'}.",
                    sources=[e["id"], "PROFILE"]))

    # 4. A prescribed medicine whose catalog allergy group matches a documented allergy.
    catalog = {d["name"].lower(): d for d in load_drug_catalog()}
    for rx in dataset["prescriptions"]:
        for i in rx["items"]:
            group = (catalog.get(i["medicine"].strip().lower()) or {}).get("allergy_group")
            for a in documented:
                if group and (group in a or a.rstrip("s") in group):
                    items.append(ReviewItem(
                        severity="high", category="allergy_conflict",
                        issue=f"Documented allergy may conflict with a prescribed medicine ({i['medicine']}).",
                        evidence=f"{i['medicine']} ({rx['id']}) is in the {group} group; documented allergy: {a}.",
                        sources=[rx["id"], "PROFILE"]))

    # 5. Duplicate prescriptions: the same medicine, strength and frequency prescribed again within 7 days.
    for entries in by_drug.values():
        for (rx_a, a), (rx_b, b) in zip(entries, entries[1:]):
            same = (a["strength"].lower(), a["frequency"].lower()) == (b["strength"].lower(), b["frequency"].lower())
            days = (datetime.fromisoformat(rx_b["datetime"]) - datetime.fromisoformat(rx_a["datetime"])).days
            if same and rx_a["id"] != rx_b["id"] and abs(days) <= 7:
                items.append(ReviewItem(
                    severity="medium", category="duplicate_medication",
                    issue=f"Possible duplicate prescription: {a['medicine']} {a['strength']} {a['frequency']} "
                          "prescribed twice within 7 days.",
                    evidence=f"{rx_a['id']} ({rx_a['date']}) and {rx_b['id']} ({rx_b['date']}).",
                    sources=[rx_a["id"], rx_b["id"]]))

    # 6. Conflicting dates: a prescription dated before the consultation it is linked to.
    for rx in dataset["prescriptions"]:
        if rx.get("consultation_datetime") and rx["datetime"] < rx["consultation_datetime"]:
            items.append(ReviewItem(
                severity="low", category="date_inconsistency",
                issue=f"Prescription {rx['id']} is dated before its linked consultation.",
                evidence=f"Prescription {rx['datetime'][:16]} · consultation {rx['consultation_datetime'][:16]}.",
                sources=[rx["id"], rx["consultation"]]))

    # 7. Missing information in recent consultations.
    for c in dataset["consultations"][-3:]:
        missing = [label for key, label in (("diagnosis", "diagnosis"), ("follow_up", "follow-up instructions"))
                   if not c[key].strip()]
        if missing:
            items.append(ReviewItem(
                severity="low", category="missing_information",
                issue=f"Consultation on {c['date']} has no documented {' or '.join(missing)}.",
                evidence=f"{c['organization']} · {c['provider']} · reason: {c['reason']}", sources=[c["id"]]))
    return items
