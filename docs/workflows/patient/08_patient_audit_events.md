# 08 — Patient Audit Events

## Existing convention (follow it)

- Table `audit_logs` (`core/models.AuditLog`): `actor_id`, `actor_type` (role or `system`), `patient_id`,
  `provider_id` (the **doctor** concerned, if any), `organization_id`, `action`, `resource_type`, `resource_id`,
  `details` (JSON, column name `metadata`), `timestamp` (naive UTC).
- `action` ∈ `AuditAction`: `CONSENT_GRANTED`, `CONSENT_REVOKED`, `RECORD_ACCESSED`, `ACCESS_DENIED`,
  `RECORD_CREATED`, `RECORD_UPDATED`, `AI_SUMMARY_GENERATED`, `AI_FLAG_REVIEWED`.
- Record changes are `RECORD_CREATED` / `RECORD_UPDATED` with `details.event` = an `EventType` value and a short
  `details.summary` (omitted for drafts and internal notes; `details.patient_visible=false` hides the row from the patient).
- Writes go through `audit_service.log` (directly) or `activity_service.record` (timeline + audit together).
- Patient self-reads are **not** logged. Doctor reads are logged as `RECORD_ACCESSED`, de-duplicated per view.

## Events

| # | Event | Status | action | actor / actor_type | patient_id | provider_id | organization_id | resource | details (no unnecessary PHI) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Consent granted (selected) | EXISTING | `CONSENT_GRANTED` | patient / `patient` | own | doctor | doctor's org | `consent`, id | `consent_id` (CON-…), `scope_type`, `all_records=false`, `categories`, `duration`, `expires_at`, `purpose` |
| 2 | All-records access confirmed | EXISTING (same row) | `CONSENT_GRANTED` | patient | own | doctor | org | `consent` | as #1 with `scope_type="all"`, `all_records=true` — the explicit confirmation is implied by the row (the service refuses without `confirm_all`) |
| 3 | Consent revoked | EXISTING | `CONSENT_REVOKED` | patient | own | doctor | org | `consent` | `consent_id`, `reason="revoked by patient"`, `scope_type`, `categories` |
| 4 | Consent superseded | EXISTING | `CONSENT_REVOKED` | patient | own | doctor | org | `consent` | `reason="superseded by a new consent"` (shown as "Consent replaced") |
| 5 | Consent expired | **Not logged** (D4) | — | — | — | — | — | — | Derived status; FUTURE `CONSENT_EXPIRED` (actor_type `system`) via a scheduled job |
| 6 | Record viewed by a doctor | EXISTING | `RECORD_ACCESSED` | doctor / `doctor` | patient | doctor | doctor's org | view name (`patient_record`, `medical_timeline`, `ai_copilot`, `ai_source`, …) | `scope` (categories or "all"), `consent_id` |
| 7 | Access blocked | EXISTING | `ACCESS_DENIED` | doctor (or other role) | patient | doctor | org | category or `record` | `reason` |
| 8 | AI summary generated | EXISTING | `AI_SUMMARY_GENERATED` | doctor | patient | doctor | org | `ai_summary`, id | `generator`, `model`, `scope`, `record_counts`, `items_for_review` — **no content, no prompt, no key** |
| 9 | Note created by patient | TO IMPLEMENT | `RECORD_CREATED` | patient / `patient` | own | **null** | **null** | `patient_entries`, id | `event="patient_entry"`, `entry_type="note"`, `summary`=title, `patient_visible=true` |
| 10 | Allergy added by patient | TO IMPLEMENT | `RECORD_CREATED` | patient | own | null | null | `patient_entries` | `event="patient_entry"`, `entry_type="allergy"`, `summary`=substance |
| 11 | Other info added | TO IMPLEMENT | `RECORD_CREATED` | patient | own | null | null | `patient_entries` | `entry_type` ∈ condition/medication/other |
| 12 | Document uploaded by patient | TO IMPLEMENT | `RECORD_CREATED` | patient | own | null | null | `documents`, id | `event="document_added"`, `doc_type`, `summary`=title — never file content, never storage path |
| 13 | Prescription sent by patient (D5) | IMPLEMENTED | `RECORD_CREATED` (same action as the existing doctor send) | patient | own | **null** | pharmacy | `prescriptions`, id | `event="prescription_sent"`, `summary` "… sent to {pharmacy}" |
| 14 | "Record shared" | Covered by #1/#2 | — | — | — | — | — | — | Sharing is consent; there is no separate per-record share event |

Notes:
- `provider_id` stays **null** for patient-initiated record events (A1 fixes `activity_service.record`, which currently
  sets `provider_id=actor.id` for every actor).
- `actor_type` is the actor's role string (`patient`, `doctor`, `pharmacist`, `lab`) or `system`.
- Free text entered by the patient appears only as the short `summary` (title), which the patient can already see.

## What the patient sees of the audit trail (EXISTING `audit_service.patient_history`)

- **Consent & access tab:** actions `CONSENT_GRANTED`, `CONSENT_REVOKED`, `RECORD_ACCESSED`, `ACCESS_DENIED`, `AI_SUMMARY_GENERATED`.
- **All record activity tab:** additionally `RECORD_CREATED`, `RECORD_UPDATED` — excluding draft events and rows with `patient_visible=false`.
- Not shown: `AI_FLAG_REVIEWED` (clinician working data).
- New patient events (#9–#13) will appear in "All record activity" with "You" as organization.
