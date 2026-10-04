# HealthBridge — Workflow Specifications (source of truth)

These documents are the permanent implementation reference for the **Patient** and **Pharmacy** workflows.
They describe what already exists in the codebase (as of commit `6a603c6`), what must be built, and what is
out of scope. They are specifications, not code.

> **Implementation order:** Patient workflow first (implement → verify → approve), then Pharmacy.
> The Doctor workflow (Phase 2) is complete and must not be changed by either.

## Implementation status (updated 4 October 2026)

| Area | Status |
|---|---|
| Shared dependencies A1–A3 (source-aware activity recording, new event types, `verified_by`/`verified_at`, schema v7) | **Implemented** (commit `cf30b74`) |
| Patient workflow (`patient/`) | **Implemented** (commit `cf30b74`) — items labelled TO IMPLEMENT in the patient files were written before implementation and are now built, except where marked FUTURE |
| A5 — read-only pharmacy status on the doctor's prescription page | Not implemented |
| Pharmacy workflow (`pharmacy/`) | **Not implemented** beyond the existing read-only pages; the pharmacy files remain the specification for the next phase |

## Status labels used in every document

| Label | Meaning |
|---|---|
| **EXISTING** | Implemented and tested in the current codebase. Reuse it — do not rebuild it. |
| **TO IMPLEMENT** | Required for the workflow, not yet built. |
| **FUTURE** | Deliberately out of current scope. Do not build. |
| **DECISION Dn** | Needs a product decision before implementation (see the register below). Each has a recommended default. |

## The connected journey

```text
PATIENT ─────────────────────────────────────────────────────────────┐
   │  Consent  (doctor + organization + categories + duration)        │
   ▼                                                                  │
DOCTOR  (EXISTING — Phase 2)                                          │
   │  Consultation  (consent-checked; patient-visible + internal)     │
   │  Prescription  (draft → issued → sent to a pharmacy)             │
   ▼                                                                  │
PHARMACY  (read-only today; actions TO IMPLEMENT)                     │
   │  Verification  (sent → verified | rejected)                      │
   │  Dispensing    (verified → partially_dispensed → dispensed)      │
   │  Billing       (invoice: pending → partially_paid → paid)        │
   ▼                                                                  │
PATIENT  sees every step on one timeline, with provenance  ◄──────────┘

LABORATORY  — FUTURE — NOT IMPLEMENTED in these specifications
   (read-only lab pages and seeded lab data exist; no lab workflow files are written yet)
```

## Files

| Workflow | Files |
|---|---|
| Patient (implement first) | [patient/](patient/) — 01 workflow · 02 user journey · 03 state machine · 04 permissions · 05 consent · 06 UI · 07 data flow · 08 audit · 09 privacy & security · 10 demo · 11 acceptance criteria · 12 test plan |
| Pharmacy (implement second) | [pharmacy/](pharmacy/) — 01 workflow · 02 user journey · 03 state machine · 04 permissions · 05 UI · 06 data flow · 07 audit · 08 privacy & security · 09 patient/doctor visibility · 10 demo · 11 acceptance criteria · 12 test plan |

## Architecture these specs build on (EXISTING — do not replace)

- **Stack:** Python · Streamlit (`st.navigation`, custom CSS) · SQLite · SQLAlchemy · Pydantic · LangGraph · Google Gemini (BYOK).
- **Layers:** `views/<role>/*.py` (UI) → `services/*_service.py` (business rules + authorization) →
  `core/models.py` (SQLAlchemy) / `core/schemas.py` (Pydantic DTOs). The UI never queries the database directly.
- **Security boundary:** `services/access_service.py` (`authorize`, `require`, `require_self`) and
  `services/record_service.py` (`get_authorized_record`, `own_record`) — the only read path to a patient's record.
- **Provenance:** every record carries patient + actor + organization + timestamp; `TimelineEvent.source_type`
  is `patient` / `provider` / `organization`; `TimelineEvent.patient_visible=False` hides internal clinician notes.
- **Audit:** `services/audit_service.py` → `AuditLog` (`action`, `actor_type`, `patient_id`, `provider_id`,
  `organization_id`, `resource_type`, `resource_id`, `details` JSON, `timestamp`). Record changes use
  `RECORD_CREATED` / `RECORD_UPDATED` with `details.event` = an `EventType` value.
- **Schema versioning:** `core/db.py` `SCHEMA_VERSION` (currently 6). Demo databases with an older version are
  rebuilt automatically — any model change must bump it and keep `data/seed.py` consistent.

## Cross-cutting rules (apply to every workflow)

1. Authorization is enforced in services, never only in the UI. Every new service function authorizes first.
2. Consent is per **patient + doctor + organization**; only doctors read the longitudinal record via consent.
3. Pharmacies see only prescriptions routed to their organization (minimum necessary). Never AI output.
4. The patient sees their own full record except internal clinician notes, private drafts and unpublished lab results.
5. Nothing deletes clinical records. Revocation removes access, not data. Corrections are new records.
6. AI writes only `AISummary` / `AIFlag`, is doctor-only, and runs only through the consent service.
7. Audit entries never contain record content beyond a short summary, and never secrets.
8. No real payments, pharmacy/hospital/lab integrations, inventory or supplier management.

## Shared architectural dependencies (needed by both Patient and Pharmacy work)

| ID | Dependency | Why | Status |
|---|---|---|---|
| A1 | Generalize `activity_service.record()` to accept `source_type` and to set `provider_id` only for doctors | It hard-codes `SourceType.PROVIDER` and `provider_id=actor.id`; patient and pharmacist actions would be mislabelled as doctor activity. `data/seed.py::_record` already shows the correct pattern. | TO IMPLEMENT (first) |
| A2 | New `EventType` values for actions with no event yet (see 08 / 07 audit files) | Keep the `RECORD_CREATED`/`RECORD_UPDATED` + `details.event` convention | TO IMPLEMENT |
| A3 | `SCHEMA_VERSION` bump if any column is added (D7) | Demo DB rebuild | TO IMPLEMENT if D7 = add columns |
| A4 | AppTest navigation caveat | AppTest does not keep a page switch made by app code; tests must call `at.switch_page(...)` to follow it (see `tests/test_phase2_fixes.py`) | EXISTING knowledge |
| A5 | Read-only pharmacy lifecycle on the doctor's prescription page | Doctor must see verification/rejection/dispensing (not billing); `views/doctor/prescription_detail.py` shows only the tracker today | TO IMPLEMENT with Pharmacy — touches a Doctor view, needs approval |

## Decision register

Each decision has a **recommended default**. Implementation may proceed on the default unless the product owner
chooses otherwise. Decisions are referenced from the individual files as **DECISION Dn**.

| ID | Question | Current code | Recommended default |
|---|---|---|---|
| D1 | Should doctors see **patient-reported allergies** with any active consent? | Patient entries (incl. allergies) are visible to doctors only when `documents` is shared; clinician-documented `Patient.allergies` are shown with any consent | Yes — show patient-reported allergies with any active consent, labelled *patient-provided, not verified* (safety-critical, like clinician allergies). Other patient entries stay under `documents`. |
| D2 | Where does a patient-added allergy go? | `Patient.allergies` = clinician-documented list; `PatientEntry(entry_type="allergy")` exists | Only `PatientEntry(entry_type="allergy")`. Never write `Patient.allergies` from the patient side. |
| D3 | Separate patient **Documents** page? | Documents appear on My Health; no nav item | Add `views/patient/documents.py` ("Documents") to patient nav after Lab Reports. |
| D4 | Log consent **expiry** in the audit trail? | Expiry is derived at check time (`access_service.effective_status`); no event | Do not write on read. Show expired consents (derived) in the patient's history; add `CONSENT_EXPIRED` only as FUTURE scheduled job. |
| D5 | Can the **patient** choose the pharmacy for an `issued` prescription? | Doctor can send (EXISTING); patient page has a placeholder selector + "Send Prescription" | Yes, in the Patient workflow, reusing `prescription_service.send_to_pharmacy` with a patient-actor branch (own prescription, status `issued`, target is a pharmacy). |
| D6 | Per-medicine dispensing status | `Dispensing.status` is one value per dispensing event; per-item data is `items_dispensed` JSON (quantities only) | Add `status` (+ optional `note`) per entry inside `items_dispensed` JSON — no column change. `Dispensing.status` = aggregate. |
| D7 | Verification metadata | `Prescription` has no `verified_at` / `verified_by` | Add `verified_at`, `verified_by` columns (bump `SCHEMA_VERSION`). |
| D8 | Does the doctor see billing? | Never (`BILLING_CATEGORY` not shareable, even with "all records") | Keep: doctor sees dispensing status and quantities, never invoices or payment. |
| D9 | After a pharmacy **rejects**, can the prescription be re-sent? | No transition exists | `rejected` is terminal. The doctor issues a new prescription. |
| D10 | Substitution handling | `DispensingStatus.SUBSTITUTION_REQUESTED` + `Dispensing.substitutions` text; "never automatic" | Request only: recorded and shown to patient and prescriber; the doctor issues a new prescription if they agree. No approval workflow in MVP. |
| D11 | UI placeholder phase numbers | Patient placeholders say "Phase 5", pharmacy "Phase 3" | Replace numbers with roadmap names ("Coming in the Patient workflow") since order changed. |
| D12 | Landing page says doctors can "request access" | No request flow, no `pending` consent state | Reword the landing card; access requests are FUTURE. |
| D13 | Invoice granularity | `Invoice.dispensing_id` exists; `PrescriptionOut.invoice` shows only the latest | One invoice per dispensing event; show all invoices for a prescription. |
| D14 | Invoice prices | No price catalog for dispensing; seed uses a fixed unit price | Pharmacist enters unit price per dispensed medicine (simulated billing, PKR). |
| D15 | Can a patient edit/delete their own entries and uploads? | No patient write paths exist | MVP: create only (append-only, like clinical records); corrections are new entries. Delete = FUTURE. |
| D16 | Prescription "Billed" step for the patient | Not a `PrescriptionStatus`; billing lives on `Invoice.payment_status` | Derive "Billed" in the patient UI from the presence/status of invoices. No new prescription status. |
| D17 | Prescriber cancellation | `PrescriptionStatus.CANCELLED` and event `prescription_cancelled` exist; no service sets them | FUTURE — out of scope for Patient and Pharmacy work; doctors issue a new prescription instead. |
