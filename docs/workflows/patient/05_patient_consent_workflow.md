# 05 — Patient Consent Workflow

**Status: EXISTING** end-to-end (`services/consent_service.py`, `services/access_service.py`,
`views/patient/consent.py`, tests in `tests/test_consent.py` and `tests/test_access_control.py`).
This file is the authoritative description; changes to consent behaviour must update it first.

## 1. Grant flow

```text
Patient ─▶ Consent & Access ─▶ "Share Records with a Doctor" (dialog)
   Step 1  Choose the doctor        search "doctor or hospital/clinic" → select a DOCTOR + ORGANIZATION pair
   Step 2  Confirm who gets access  card: doctor, specialty, organization badge,
                                    "Only Dr. X at Org Y will get access — not other doctors there,
                                     and not Dr. X when working at another organization."
   Step 3  What to share            ( ) Share selected records   ( ) Share all my HealthBridge records
                                    [checkboxes for each category]
   Step 4  For how long             Until I revoke it · One consultation · 24 hours · 7 days ; optional reason
   Step 5  Privacy summary          WILL see: [chips]  ·  will NOT see: [locked chips]  ·  duration
           [Cancel]  [Share selected records | Confirm & Share All Records]
   ↓
consent_service.grant(actor, provider_id, organization_id, scope_type, categories, duration, purpose, confirm_all)
   ↓  validations (below) → supersede previous active consent for the same pair → Consent (+ ConsentScope rows)
   ↓  audit CONSENT_GRANTED
   ↓
"Access granted to Dr. X" success card (Consent ID CON-000NNN) → People with access
   ↓
Doctor (at THAT organization only) → access_service.authorize → allowed via "consent", categories = scope
```

### Validations (in the service)

| Rule | Error |
|---|---|
| Actor is a patient acting on their own record | `AccessDenied("Only patients can manage consent for their own record")` |
| The doctor has an **active membership** at the organization (`ProviderOrganization`) and role `doctor` | `ConsentError("That doctor does not work at the selected organization")` |
| `scope_type="selected"` needs ≥1 category | `ConsentError("Choose at least one type of record to share")` |
| `scope_type="all"` needs `confirm_all=True` | `ConsentError("Sharing all records requires explicit confirmation")` |
| Categories must be `RecordCategory` values; duration a `ConsentDuration` | `ValueError` |

### Doctor + organization specificity

Consent is keyed by **(patient_id, provider_id, organization_id)**:

| Ahmed grants | Dr. Arif at South City Hospital | Dr. Arif at Clifton Medical Centre | Another doctor at South City |
|---|---|---|---|
| Dr. Arif — South City Hospital | ✅ access (scoped) | ❌ "Patient consent is required…" | ❌ |

Provider options list each doctor's **primary organization first** (`ProviderOrganization.is_primary`), so the demo
default is *Dr. Arif Hassan — South City Hospital*. Other organizations remain selectable.

## 2. Selective consent — supported categories (EXISTING)

| UI label | `RecordCategory` | What the doctor then sees |
|---|---|---|
| Previous consultations | `consultations` | Consultations and clinical notes written at **clinics**; documented conditions |
| Prescriptions | `prescriptions` | All non-draft prescriptions (never invoices) |
| Current medications | `medications` | Medication list derived from active prescriptions (works even without `prescriptions`) |
| Laboratory reports | `lab_reports` | Lab orders/reports (published values only) |
| Hospital records | `hospital_records` | Consultations and notes written at **hospitals**; documented conditions |
| Imaging | `imaging_reports` | Imaging orders/reports |
| Documents | `documents` | Documents and patient-provided entries (D1 proposes allergies with any consent) |

Always shown with **any** active consent: identity (name, HB-ID, age, sex) and **clinician-documented allergies**.
Never shareable: **billing** (invoices), even with "all records". Never visible to any doctor via consent:
another doctor's private drafts. Internal clinician notes are visible to authorized clinicians (not to the patient).

## 3. Share all records

| Element | Behaviour |
|---|---|
| Choice | "Share all my HealthBridge records" |
| Warning (EXISTING) | Alert "Full medical record access": *"You're about to give {doctor} at {organization} access to your complete HealthBridge medical record, including consultations, prescriptions, medications, laboratory reports, hospital records and other available health information. Only share your complete record if you are comfortable giving this provider access to all available records."* |
| Confirmation | Button label becomes **"Confirm & Share All Records"**; the service additionally requires `confirm_all=True` (a UI bypass cannot create an all-records consent) |
| Stored | `Consent.scope_type="all"`, no `ConsentScope` rows; `consent_categories()` returns all 7 categories |
| Audit | `CONSENT_GRANTED` with `details.all_records = true`, `scope_type="all"`, `categories` = all |
| Resulting access | Every category; still no billing, still no other doctors' drafts; still organization-specific; still revocable and time-limited |

## 4. Duration and expiry

| Duration | `expires_at` | Effective expiry (derived by `effective_status`) |
|---|---|---|
| `until_revoked` | none | only by revocation |
| `hours_24` | granted + 24 h | at `expires_at` |
| `days_7` | granted + 7 d | at `expires_at` |
| `one_consultation` | granted + 24 h (safety cap) | first consultation by that doctor at that organization after grant **+ 2 h grace**, or the 24 h cap |

Expired consents move to "Past access" automatically. No audit row is written at expiry (D4).

## 5. One consent per pair (supersede) — EXISTING

Granting again for the same doctor + organization revokes the previous active consent with reason
*"superseded by a new consent"* and creates a new one. The history shows "Consent replaced".

## 6. Revocation

```text
Patient ─▶ People with access ─▶ "Revoke access" ─▶ dialog ("records are not deleted…") ─▶ "Revoke access"
   ↓  consent_service.revoke(actor, consent_id)  — must be the patient's own consent
   ↓  Consent.status = "revoked", revoked_at = now
   ↓  audit CONSENT_REVOKED {consent_id, reason: "revoked by patient", scope_type, categories}
   ↓  flash "Access revoked for Dr. X at Org Y."
Doctor (next request) ─▶ authorize: no active consent ─▶ locked "ACCESS RESTRICTED" view
                        any record/category read via require() ─▶ AccessDenied + audit ACCESS_DENIED
AI Clinical Copilot   ─▶ preview / generate / latest / flags_for_summary / review_flag / resolve_sources
                        all call access_service.require → blocked; previously generated summaries are
                        not shown (latest() requires active consent); no agent runs
```

Guarantees:
- Revocation never deletes or alters clinical records, AI rows or audit rows.
- Revocation is immediate: Streamlit re-authorizes on every rerun; there is no cached access.
- Records the doctor **authored** at that organization are also hidden after revocation (the authored-record rule applies only under an active consent).
- A revoked consent cannot be re-activated; the patient grants a new one.

## 7. Monitoring

| Where | What |
|---|---|
| Home → Active consents | doctor, organization, scope |
| Consent & Access → People with access | scope chips, granted, expiry text, consent ID, **View access** (when that doctor opened the record), **Revoke access** |
| Consent & Access → Past access | revoked / expired consents with end date |
| Consent & Access → History | CONSENT_GRANTED / CONSENT_REVOKED / "Consent replaced" / RECORD_ACCESSED / ACCESS_DENIED / AI_SUMMARY_GENERATED |
| Care Network | per doctor, what they can currently see |

## 8. TO IMPLEMENT / FUTURE

| Item | Status |
|---|---|
| D1: patient-reported allergies visible with any consent | TO IMPLEMENT if approved |
| Revocation flow UI test (dialog → revoked → doctor locked) | TO IMPLEMENT (service test exists) |
| Doctor-initiated access request / `pending` state | FUTURE (D12) |
| Expiry notifications, scheduled `CONSENT_EXPIRED` audit | FUTURE (D4) |
| Editing the scope of an existing consent | Not supported — grant again (supersede) |
| Emergency / break-glass access | FUTURE |
