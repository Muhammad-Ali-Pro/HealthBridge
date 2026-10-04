# 01 — Patient Workflow (overview)

**Scope:** the complete patient experience in HealthBridge. **Priority:** implement first.
Labels: **EXISTING** · **TO IMPLEMENT** · **FUTURE** · **DECISION Dn** (see [../README.md](../README.md)).

## Journey map

```text
Patient
  ↓  Landing page ("Continue as Ahmed Khan")                    EXISTING  app.py / ui/shell.py enter_as()
  ↓  Patient demo sign-in (simulated, DEMO MODE)                EXISTING  no real authentication
  ↓  Home (dashboard)                                           EXISTING  views/patient/home.py
  ↓  My Health                                                  EXISTING  views/patient/my_health.py
  ↓  Medical Timeline                                           EXISTING  views/patient/timeline.py
  ↓  Prescriptions                                              EXISTING  views/patient/prescriptions.py (send = placeholder, D5)
  ↓  Medications                                                EXISTING  views/patient/medications.py
  ↓  Lab Reports                                                EXISTING  views/patient/reports.py
  ↓  Documents                                                  TO IMPLEMENT page (D3); data EXISTING on My Health
  ↓  Care Network                                               EXISTING  views/patient/care_network.py
  ↓  Consent & Access                                           EXISTING  views/patient/consent.py
  ↓  Record sharing (selected categories / all records)         EXISTING  consent_service.grant()
  ↓  Consent monitoring (active, past, "View access")           EXISTING
  ↓  Revoke access                                              EXISTING  consent_service.revoke()
  ↓  Activity / audit history                                   EXISTING  audit_service.patient_history()
```

Patient-created information (all **TO IMPLEMENT** as write paths; display is **EXISTING**):

| Patient action | Stored as | Display today |
|---|---|---|
| Add a personal note | `PatientEntry(entry_type="note")` | My Health "Information I added" (EXISTING) |
| Add an allergy | `PatientEntry(entry_type="allergy")` — never `Patient.allergies` (D2) | My Health (EXISTING) |
| Add other information (condition, medication taken, other) | `PatientEntry(entry_type="condition" \| "medication" \| "other")` | My Health (EXISTING) |
| Upload a document | `Document(source_type="patient", organization_id=None, uploaded_by=<patient user>)` | My Health "My documents" (EXISTING) |

Buttons for these exist as placeholders (`phase_action(...)` in `home.py` and `my_health.py`).

## Three sources of information — always distinguished

| Source | Meaning | How it is stored | How it is shown |
|---|---|---|---|
| **Patient-provided** | Entered by the patient; not clinically verified | `PatientEntry`; `Document.source_type="patient"`; `TimelineEvent.source_type="patient"` | Violet "Patient-provided" badge (`patient_provided_badge_html`), "Added by you" on the timeline |
| **Clinician-provided** | Written by a doctor acting at an organization | `Consultation`, `ClinicalNote`, `Prescription`, provider `Document`; `TimelineEvent.source_type="provider"` | "Organization · Dr. Name" source line (`org_badge_html` + provider name) |
| **Organization-provided** | Produced by a laboratory or pharmacy as an organization | `LabOrder`/`LabReport`, `Dispensing`, `Invoice`; `TimelineEvent.source_type="organization"` | Organization badge (e.g. "HealthLab Diagnostics", "HealthPlus Pharmacy") |

Clinician-documented allergies (`Patient.allergies`, e.g. *Penicillin*) and patient-reported allergies
(`PatientEntry`, e.g. *Shellfish (self-reported)*) must never be merged into one unlabelled list.

## What the patient never sees (EXISTING, enforced in services)

- Internal clinician notes (`NoteType.INTERNAL`, `TimelineEvent.patient_visible=False`).
- Doctors' private drafts (consultations and prescriptions with status `draft`).
- Unpublished lab results (values hidden until `published`).
- AI summaries and AI flags (doctor-only).
- Other patients' data.

## Building blocks to reuse (EXISTING)

| Concern | Reuse |
|---|---|
| Read own record | `record_service.own_record(session, actor)` → `AuthorizedRecord` |
| Consent | `consent_service.grant / revoke / list_for_patient / search_providers / get_for_patient` |
| Care network | `care_network_service.network(session, actor)` |
| History | `audit_service.patient_history(session, actor, patient_id, include_activity=...)` |
| Timeline + audit on write | `activity_service.record(...)` — **after** generalization A1 (source type) |
| Upload validation | `document_service` (allowed types PDF/PNG/JPG, 10 MB, local storage under `UPLOAD_DIR`) |

## Out of scope

- **FUTURE:** real authentication, patient-initiated access *requests* by doctors (D12), editing/deleting
  patient entries (D15), consent expiry notifications, emergency/break-glass access, family/caregiver proxies,
  patient messaging, appointment booking, payments.
