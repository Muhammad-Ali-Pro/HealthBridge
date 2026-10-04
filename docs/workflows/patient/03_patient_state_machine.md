# 03 — Patient-side State Machines

Only states that exist in the code (`core/models.py`) are used. Proposed additions are marked **TO IMPLEMENT** / **FUTURE**.

## 1. Consent (`ConsentStatus`) — EXISTING

Stored values: `active`, `revoked`. `expired` is **derived** at check time by
`access_service.effective_status()`; it is never written to the row (DECISION D4).

```text
            grant()                      revoke() by patient
 (none) ───────────────▶  active  ───────────────────────────▶  revoked   (terminal)
                            │  ▲
                            │  └── grant() again for the same doctor + organization:
                            │      the old consent → revoked (reason "superseded by a new consent"),
                            │      a NEW consent row → active
                            │
                            └── time passes ──▶  expired (derived, terminal)
                                 • expires_at ≤ now            (hours_24, days_7, one_consultation 24 h cap)
                                 • one_consultation: first consultation by that doctor at that
                                   organization since grant + 2 h grace ≤ now
```

| Transition | Trigger | Guard | Effect | Audit |
|---|---|---|---|---|
| none → active | `consent_service.grant` | actor is the patient; doctor works at the organization (`ProviderOrganization.active`); ≥1 category, or `scope_type="all"` with `confirm_all=True` | `Consent` + `ConsentScope` rows | `CONSENT_GRANTED` |
| active → revoked | `consent_service.revoke` | consent belongs to the patient | `status`, `revoked_at` | `CONSENT_REVOKED` (reason "revoked by patient") |
| active → revoked (superseded) | new `grant` for same doctor+org | — | old row revoked, new row active | `CONSENT_REVOKED` (reason "superseded…") + `CONSENT_GRANTED` |
| active → expired | time | — | none (derived) | none (D4) |
| revoked/expired → active | **not allowed** | — | patient must grant a new consent | — |

`pending` (doctor-initiated access request) does **not** exist — **FUTURE** (D12).

Durations (`ConsentDuration`): `until_revoked` (no expiry) · `one_consultation` · `hours_24` · `days_7`.

## 2. Record visibility (from the patient's perspective) — EXISTING (derived, not stored)

There is no per-record visibility column except `TimelineEvent.patient_visible`. Visibility to a **doctor** is a
function of consent; visibility to the **patient** is fixed.

| Visibility state | Meaning | Determined by |
|---|---|---|
| `private` | Only the patient (and the record's author) can see it | No active consent for the viewer covers the record's category |
| `shared` | A specific doctor at a specific organization can see it | Active consent whose categories include the record's category (`AccessDecision.can`) |
| `revoked` | Was shared; the consent was revoked | Consent `revoked` → doctor falls back to `private` view |
| `expired` | Was shared; the consent expired | Consent effectively `expired` |
| `clinician-only` | Never visible to the patient | `ClinicalNote.note_type="internal"` / `TimelineEvent.patient_visible=False` |

Record → category mapping (EXISTING, `record_service`):

| Record | Category |
|---|---|
| Consultation / clinical note at a clinic | `consultations` |
| Consultation / clinical note at a hospital | `hospital_records` |
| Prescription | `prescriptions` |
| Current/previous medication (derived from prescriptions) | `medications` |
| Lab order/report (lab) | `lab_reports` |
| Lab order/report (imaging) | `imaging_reports` |
| Document (any source) | `documents` |
| Patient entry (note, allergy, …) | `documents` (DECISION D1 proposes allergies with any consent) |
| Invoice | `billing` — never shareable with doctors |

An author always sees records they wrote at their current organization while they hold an active consent there
(EXISTING "authored-record rule").

## 3. Prescription lifecycle — patient-facing view

Model (`PrescriptionStatus`, EXISTING): `draft → issued → sent → verified → partially_dispensed → dispensed`,
plus terminal `rejected` and `cancelled`. **Billing is not a prescription status** (DECISION D16).

```text
 Prescribed ──▶ Sent ──▶ Verified ──▶ Dispensed ──▶ Billed
 (issued)      (sent)    (verified)   (partially_dispensed shows as "Part collected";
                                        dispensed)   (derived from Invoice.payment_status)
       └──────────── rejected  ("could not fill — contact your doctor")
       └──────────── cancelled ("your doctor cancelled this prescription")
```

| Patient label | Underlying state | Plain-language text (EXISTING in `views/patient/prescriptions.py`) |
|---|---|---|
| (hidden) | `draft` | Never shown to the patient |
| Prescribed | `issued` | "Ready to send. Choose the pharmacy…" (send = D5) |
| Sent | `sent` | "Sent to {pharmacy}. The pharmacist will check it…" |
| Verified | `verified` | "Checked by {pharmacy} and ready for you to collect." |
| Part collected | `partially_dispensed` | "Part of your medicine was collected from {pharmacy}." |
| Dispensed | `dispensed` | "Collected from {pharmacy} on {date}." |
| Billed | invoice exists; `pending` / `partially_paid` / `paid` / `cancelled` | "Invoice INV-… : paid" |
| Rejected | `rejected` | "{pharmacy} could not fill this prescription. Please contact your doctor." |
| Cancelled | `cancelled` | "Your doctor cancelled this prescription." |

The patient never changes prescription state except **issued → sent** (D5). All pharmacy-side transitions are specified in
[../pharmacy/03_pharmacy_state_machine.md](../pharmacy/03_pharmacy_state_machine.md) and are not implemented by the Patient workflow.

## 4. Patient entry / patient document — TO IMPLEMENT

```text
 (none) ── add_entry() / upload_own() ──▶ recorded   (append-only; D15: edit/delete = FUTURE)
```
