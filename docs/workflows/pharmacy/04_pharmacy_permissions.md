# 04 — Pharmacy Permissions

## Authorization boundary

A pharmacy actor is `Actor(role="pharmacist")` whose working organization has `org_type="pharmacy"`
(`pharmacy_service._require_pharmacy`, EXISTING). The pharmacy may access **only prescriptions whose
`Prescription.pharmacy_id` equals its organization** and whose status is not `draft`/`issued` (`HIDDEN`), plus the
`Dispensing` and `Invoice` rows **it** created for them. It never uses consent and never reads the longitudinal
record: `access_service.authorize` returns *"Pharmacies and laboratories only see the prescriptions and test orders
sent to them."* for any record request (EXISTING, tested).

```text
             ┌───────────── Patient's longitudinal record (consent-gated, doctors only) ─────────────┐
             │ consultations · notes · labs · documents · hospital records · AI · timeline          │
             └───────────────────────────────────────────────────────────────────────────────────────┘
                                   ✗ pharmacy cannot cross this line
             ┌── Prescriptions routed to THIS pharmacy ──┐
             │ identity · allergies · items · prescriber │ ◀── pharmacy_service (only read/write path)
             │ dispensing · invoices of this pharmacy    │
             └───────────────────────────────────────────┘
```

## Allowed

| Data | R | C | U | Notes |
|---|---|---|---|---|
| Patient identity needed for dispensing: name, HB-ID, age, sex | ✅ | ❌ | ❌ | EXISTING (`PatientIdentity`) — no phone/address in UI |
| Patient **allergies** (clinician-documented) | ✅ | ❌ | ❌ | EXISTING — safety check for dispensing (deliberate, documented exception) |
| Prescription header: RX id, dates, status, status reason, notes on the prescription | ✅ | ❌ | status only via verify/reject/dispense | Consultation **reason is excluded** (`include_reason=False`) |
| Medicines: drug, strength, dosage, route, frequency, duration, quantity, instructions | ✅ | ❌ | ❌ | Immutable |
| Prescriber name and prescribing organization | ✅ | ❌ | ❌ | |
| Dispensing records of this pharmacy | ✅ | ✅ | ❌ | Append-only (corrections = new event, FUTURE) |
| Invoices of this pharmacy | ✅ | ✅ | payment / cancel | |
| Substitution request text | ✅ | ✅ | ❌ | Request only (D10) |

## Not allowed

| Data | Why | Enforcement |
|---|---|---|
| Unrelated medical history, consultations, clinical notes, diagnoses | Not needed to dispense | `authorize` denies non-doctors; `pharmacy_service` exposes no such query |
| Consultation reason linked to the prescription | Clinical context, not needed | `prescription_to_out(include_reason=False)` |
| Lab reports, imaging, documents | Not needed | as above |
| Internal clinician notes | Clinician-only | as above |
| AI summaries, AI flags, Copilot | Doctor-only | `copilot_service._require_doctor` |
| Prescriptions routed to another pharmacy, or not yet sent | Not theirs | `pharmacy_id` filter + `HIDDEN` statuses |
| Other prescriptions of the same patient at other pharmacies | Not theirs | `pharmacy_id` filter |
| Patient timeline, consent records, care network | Patient/doctor-only | no API |
| Modify prescription content, prescriber, patient data | Integrity | no API |
| Other pharmacies' invoices | Not theirs | `Invoice.organization_id` filter |

## Pharmacy staff vs pharmacy

Authorization is per **organization**: any pharmacist of HealthPlus Pharmacy may act on HealthPlus prescriptions.
Each action records the individual pharmacist (`actor_id`, `Dispensing.pharmacist_id`, `Invoice.created_by`, `verified_by`).
Roles within a pharmacy (technician vs pharmacist) are FUTURE.

## Required denials (each must be tested)

- Pharmacist of CarePoint Pharmacy cannot list, open, verify, dispense or invoice a HealthPlus prescription.
- Pharmacist cannot call `record_service.get_authorized_record` (EXISTING test), `copilot_service.*`, `consent_service.*`, `clinical_service.*`.
- Doctor and patient actors cannot call `pharmacy_service` write functions.
