# 07 — Pharmacy Audit Events

Convention (EXISTING, see [../patient/08_patient_audit_events.md](../patient/08_patient_audit_events.md)): `AuditLog` with
`action` ∈ `AuditAction`, record changes as `RECORD_CREATED` / `RECORD_UPDATED` + `details.event` (`EventType`),
written with a `TimelineEvent` by `activity_service.record`. Seed data already uses this for pharmacy events
(`actor_type="pharmacist"`, `provider_id=null`, `organization_id` = pharmacy, timeline `source_type="organization"`).
Pharmacy events must **not** set `provider_id` (A1).

| # | Event | action | details.event | resource | Timeline category | details (beyond event/summary) | Status |
|---|---|---|---|---|---|---|---|
| 1 | Prescription received | `RECORD_UPDATED` (by sender) | `prescription_sent` | `prescriptions` | prescriptions | — (written by doctor/patient at send time; summary "… sent to HealthPlus Pharmacy") | EXISTING (doctor) |
| 2 | Prescription opened by pharmacy | `RECORD_ACCESSED` | — | `pharmacy_prescription`, rx id | — | `pharmacy`, de-duplicated like doctor access | TO IMPLEMENT (recommended) |
| 3 | Verified | `RECORD_UPDATED` | `prescription_verified` | `prescriptions` | prescriptions | `checklist: [identity, allergy, dose, prescriber]` | TO IMPLEMENT (event type EXISTING) |
| 4 | Rejected | `RECORD_UPDATED` | `prescription_rejected` | `prescriptions` | prescriptions | `reason` | TO IMPLEMENT (event type EXISTING) |
| 5 | Dispensing (full) | `RECORD_CREATED` | `dispensing` | `dispensings`, id | prescriptions | `dispensing_status="dispensed"`, `lines: [{drug_name, quantity}]` | TO IMPLEMENT |
| 6 | Partial dispensing | `RECORD_CREATED` | `dispensing` | `dispensings` | prescriptions | `dispensing_status="partial"`, outstanding per drug | TO IMPLEMENT |
| 7 | Unavailable | `RECORD_CREATED` | `dispensing` | `dispensings` | prescriptions | `dispensing_status="unavailable"`, drugs | TO IMPLEMENT |
| 8 | Substitution request | `RECORD_CREATED` | `dispensing` | `dispensings` | prescriptions | `dispensing_status="substitution_requested"`, `request` (short text) | TO IMPLEMENT |
| 9 | Completed | (same row as the dispensing that completes it) | `dispensing` | `dispensings` | prescriptions | `prescription_status="dispensed"` | TO IMPLEMENT |
| 10 | Invoice generated | `RECORD_CREATED` | `invoice_issued` | `invoices`, id | **billing** | `invoice_number`, `total`, `currency` | TO IMPLEMENT (event type EXISTING) |
| 11 | Payment recorded | `RECORD_UPDATED` | `payment_recorded` (NEW) | `invoices` | billing | `amount`, `amount_paid`, `payment_status` | TO IMPLEMENT |
| 12 | Invoice cancelled | `RECORD_UPDATED` | `invoice_cancelled` (NEW) | `invoices` | billing | `reason` | TO IMPLEMENT |
| 13 | Access denied (wrong pharmacy / invalid role) | `ACCESS_DENIED` | — | `prescription` | — | `reason` | TO IMPLEMENT |

Every row: `actor_id` = pharmacist user, `actor_type="pharmacist"`, `patient_id` = prescription's patient,
`provider_id=null`, `organization_id` = pharmacy, `timestamp` UTC.

## Visibility of these events

| Viewer | Sees |
|---|---|
| Patient | All of the above in "All record activity" and on the timeline (Pharmacy filter), including billing |
| Doctor (with `prescriptions` consent, or as prescriber at that org) | #1, #3–#9 on the timeline (category `prescriptions`); never billing (#10–#12) |
| Pharmacy | Its own actions via its pages; FUTURE: a pharmacy activity log |

## Must not be logged

Patient medical history, diagnoses, consultation reasons, free-text clinical notes, prices beyond the invoice summary in
places other than billing events, any secrets.
