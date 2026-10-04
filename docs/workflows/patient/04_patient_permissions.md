# 04 — Patient Permissions

Enforced in services (`access_service.require_self` / `authorize(... via="self")`), never only in the UI.
A patient actor is `Actor(role="patient")` whose user owns exactly one `Patient` row (`Patient.user_id`).

## Permission matrix (R = read, C = create, U = update, D = delete)

| Resource | R | C | U | D | Notes / status |
|---|---|---|---|---|---|
| Own profile (name, DOB, sex, clinician-documented allergies & conditions) | ✅ | — | ❌ | ❌ | EXISTING read. Clinician-documented fields are written only by clinicians. |
| Consultations (final) | ✅ | ❌ | ❌ | ❌ | EXISTING. Drafts never visible. |
| Additional notes on consultations | ✅ | ❌ | ❌ | ❌ | EXISTING (My Health). |
| Clinical notes (consultation / follow-up / observation) | ✅ | ❌ | ❌ | ❌ | EXISTING. |
| Internal clinician notes | ❌ | ❌ | ❌ | ❌ | EXISTING — filtered in `_query_notes`, `_query_timeline`, `notes_for_consultation`, `patient_history`. |
| Prescriptions (non-draft) | ✅ | ❌ | ❌* | ❌ | *Only `issued → sent` by choosing a pharmacy (D5, TO IMPLEMENT). Items never editable. |
| Medications (derived) | ✅ | ❌ | ❌ | ❌ | EXISTING. |
| Lab reports | ✅ (published values only) | ❌ | ❌ | ❌ | EXISTING. |
| Documents (provider / organization) | ✅ | ❌ | ❌ | ❌ | EXISTING. |
| Documents (own uploads) | ✅ | ✅ | ❌ | ❌ | C = TO IMPLEMENT; U/D = FUTURE (D15). |
| Patient entries (note, allergy, condition, medication, other) | ✅ | ✅ | ❌ | ❌ | C = TO IMPLEMENT; U/D = FUTURE (D15). |
| Timeline | ✅ (patient-visible events) | via the actions above | ❌ | ❌ | Append-only. |
| Care network | ✅ | ❌ | ❌ | ❌ | EXISTING (derived). |
| Consents | ✅ | ✅ grant | ✅ revoke only | ❌ | EXISTING. Revocation is the only update; consents are never deleted. |
| Consent/access history (audit) | ✅ (own, filtered) | ❌ | ❌ | ❌ | EXISTING. |
| Dispensing records | ✅ | ❌ | ❌ | ❌ | EXISTING read (shown via prescription status). |
| Invoices | ✅ | ❌ | ❌ | ❌ | EXISTING read (`can("billing")` is true only for self). Payment recording = pharmacy (D14). |
| AI summaries / AI flags | ❌ | ❌ | ❌ | ❌ | Doctor-only (EXISTING). |
| Audit logs | ✅ own filtered view | ❌ | ❌ | ❌ | No write path exists or may be added. |
| Other patients' anything | ❌ | ❌ | ❌ | ❌ | `authorize` → "Patients can only see their own record". |

## Must NOT be able to (each must be a tested denial)

| Forbidden action | Why it is impossible | Required test |
|---|---|---|
| Modify a doctor's clinical note or consultation | No patient write path; `clinical_service._require_doctor_access` requires `Role.DOCTOR` + organization | Calling `clinical_service.save_consultation`/`add_note` as a patient raises `AccessDenied` |
| Modify a prescription | `prescription_service` doctor functions require `Role.DOCTOR`; D5 branch only changes `issued → sent` | Patient `save_draft`/`issue` → `AccessDenied`; patient send on non-`issued` → error |
| Modify lab results | No lab write path exists at all yet (lab workflow is FUTURE); `lab_service` reads require `Role.LAB` | Patient `lab_service.list_orders` → `AccessDenied`; no patient UI control |
| Modify audit logs | No update/delete API exists | Assert `audit_service` exposes no mutation; UI has no control |
| Modify AI summaries / flags | `copilot_service._require_doctor` | Patient `review_flag` / `generate` → `AccessDenied` |
| Modify dispensing records / invoices | Pharmacy-only services (TO IMPLEMENT) check `Role.PHARMACIST` + organization | Patient call → `AccessDenied` |
| Change clinician-documented allergies | `Patient.allergies` is never written by patient services (D2) | After adding an allergy entry, `Patient.allergies` unchanged |
| Read another patient | `authorize` | Existing `test_patient_sees_own_full_record_only` |

## Patient write validation (TO IMPLEMENT)

| Input | Rule |
|---|---|
| Entry title | required, trimmed, 1–200 chars |
| Entry details | optional, ≤ 2000 chars |
| Entry type | one of `PatientEntryType` |
| Document file | `.pdf .png .jpg .jpeg`, non-empty, ≤ 10 MB (reuse `document_service.ALLOWED_TYPES`, `MAX_BYTES`) |
| Document title | required, ≤ 200 chars |
| Document type | one of `DocumentType` |
