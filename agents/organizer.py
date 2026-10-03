"""Record Organizer — deterministic. Turns an ALREADY-AUTHORIZED record into a compact, citable dataset.

It never decides what the AI may see: it only receives AuthorizedRecord, which the consent service has
already filtered to the doctor's scope in their current organization.
"""

from core.schemas import AuthorizedRecord
from agents.schemas import SourceRef


def _d(dt) -> str:
    return dt.strftime("%d %b %Y") if dt else ""


def organize(record: AuthorizedRecord) -> tuple[dict, list[SourceRef]]:
    sources: list[SourceRef] = []

    def src(id_: str, kind: str, label: str, date: str) -> str:
        sources.append(SourceRef(id=id_, kind=kind, label=label, date=date))
        return id_

    p = record.patient
    src("PROFILE", "profile", "Clinician-documented patient profile (allergies, conditions)", "")

    consultations = []
    for c in sorted(record.consultations, key=lambda c: c.date):
        cid = src(f"C-{c.id}", "consultation", f"Consultation · {c.provider_name} · {c.organization_name}", _d(c.date))
        consultations.append({
            "id": cid, "date": _d(c.date), "organization": c.organization_name, "provider": c.provider_name,
            "reason": c.complaint, "symptoms_notes": c.notes, "observations": c.observations,
            "assessment": c.assessment, "diagnosis": c.diagnosis, "treatment_plan": c.treatment_plan,
            "follow_up": c.follow_up,
        })

    notes = []
    for n in sorted(record.notes, key=lambda n: n.created_at):
        nid = src(f"N-{n.id}", "clinical_note", f"Clinical note ({n.note_type.replace('_', ' ')}) · {n.provider_name} · "
                  f"{n.organization_name}", _d(n.created_at))
        notes.append({"id": nid, "date": _d(n.created_at), "type": n.note_type, "provider": n.provider_name,
                      "organization": n.organization_name, "content": n.content})

    prescriptions = []
    for rx in sorted(record.prescriptions, key=lambda r: r.created_at):
        rid = src(rx.display_id, "prescription", f"Prescription by {rx.provider_name} · {rx.organization_name}",
                  _d(rx.created_at))
        prescriptions.append({
            "id": rid, "date": _d(rx.created_at), "provider": rx.provider_name, "organization": rx.organization_name,
            "status": rx.status, "items": [{"medicine": i.drug_name, "strength": i.strength, "dosage": i.dosage,
                                            "route": i.route, "frequency": i.frequency, "duration_days": i.duration_days,
                                            "quantity": i.quantity} for i in rx.items]})

    current_medications = []
    known = {s.id for s in sources}
    for m in record.medications:
        if not m.current:
            continue
        rid = f"RX-{m.prescription_id:05d}"
        if rid not in known:  # medications may be shared without the prescription history
            known.add(src(rid, "prescription", f"Prescription by {m.prescribed_by} · {m.organization_name}", _d(m.started)))
        current_medications.append({
            "medicine": m.drug_name, "strength": m.strength, "dosage": m.dosage, "frequency": m.frequency,
            "since": _d(m.started), "until": _d(m.ends), "prescribed_by": m.prescribed_by,
            "organization": m.organization_name, "source": rid,
        })

    reports = []
    for o in sorted(record.reports, key=lambda o: o.ordered_at):
        if o.status != "published":
            continue
        lid = src(o.display_id, "lab_report", f"{o.test_name} report · {o.lab_name}", _d(o.published_at))
        reports.append({"id": lid, "date": _d(o.published_at), "test": o.test_name, "laboratory": o.lab_name,
                        "ordered_by": o.provider_name, "values": [v.model_dump() for v in o.values],
                        "interpretation": o.interpretation})

    documents = []
    for d in sorted(record.documents, key=lambda d: d.created_at):
        did = src(f"DOC-{d.id}", "document", f"{d.title} · {d.source}", _d(d.created_at))
        documents.append({"id": did, "date": _d(d.created_at), "title": d.title, "type": d.doc_type, "source": d.source})

    patient_provided = []
    for e in sorted(record.patient_entries, key=lambda e: e.created_at):
        eid = src(f"PE-{e.id}", "patient_provided", f"Patient-provided {e.entry_type}: {e.title}", _d(e.created_at))
        patient_provided.append({"id": eid, "date": _d(e.created_at), "type": e.entry_type, "title": e.title,
                                 "details": e.details})

    dataset = {
        "patient": {"age": p.age, "sex": p.sex, "clinician_documented_allergies": p.allergies,
                    "clinician_documented_conditions": p.conditions, "source": "PROFILE"},
        "authorized_categories": record.access.categories,
        "consultations": consultations,
        "clinical_notes": notes,
        "prescriptions": prescriptions,
        "current_medications": current_medications,
        "lab_reports": reports,
        "documents": documents,
        "patient_provided": patient_provided,
        "timeline": [{"date": _d(e.occurred_at), "event": e.event_type, "source": e.source, "summary": e.summary}
                     for e in sorted(record.timeline, key=lambda e: e.occurred_at)][-40:],
    }
    return dataset, sources


def record_counts(dataset: dict) -> dict[str, int]:
    return {k: len(dataset[k]) for k in ("consultations", "clinical_notes", "prescriptions", "current_medications",
                                         "lab_reports", "documents", "patient_provided")}
