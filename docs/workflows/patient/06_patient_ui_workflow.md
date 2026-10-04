# 06 — Patient UI Workflow

Keep the existing HealthBridge design system (`ui/theme.py`, `ui/components.py`, `ui/sections.py`): sidebar
navigation, top bar with "Home page" and profile menu, cards, status badges, organization badges, provenance badges.
No redesign.

## Navigation

EXISTING (`ui/shell.py` `NAV[Role.PATIENT]`), with one addition:

| Section | Item | Page | Status |
|---|---|---|---|
| My HealthBridge | Home | `views/patient/home.py` | EXISTING |
| | My Health | `views/patient/my_health.py` | EXISTING |
| | Medical Timeline | `views/patient/timeline.py` | EXISTING |
| | Prescriptions | `views/patient/prescriptions.py` | EXISTING |
| | Medications | `views/patient/medications.py` | EXISTING |
| | Lab Reports | `views/patient/reports.py` | EXISTING |
| | Documents | `views/patient/documents.py` | TO IMPLEMENT (D3) |
| Sharing & privacy | Care Network | `views/patient/care_network.py` | EXISTING |
| | Consent & Access | `views/patient/consent.py` | EXISTING |

Adding a nav item requires updating `tests/test_ui_smoke.py::test_role_specific_navigation`.

## Home (patient dashboard) — EXISTING, quick actions TO IMPLEMENT

| Section | Content | Status |
|---|---|---|
| Header | "Hello, Ahmed" + ownership concept card | EXISTING |
| Quick actions | **Share records with a doctor** (→ Consent) · Upload a document · Add a health note · Add allergy or information | Share EXISTING; the other three are `phase_action` placeholders → TO IMPLEMENT as dialogs |
| Health summary | `patient_hero`: allergies (clinician), conditions, current medications, last activity | EXISTING |
| Recent medical activity | 6 newest timeline events + "See my full timeline" | EXISTING |
| Recent healthcare encounters | `consultations_table` (4) | EXISTING |
| Current medications | `medications_html` | EXISTING |
| Recent prescriptions | latest prescription with progress tracker | EXISTING |
| Recent lab reports | latest published report, plain language | EXISTING |
| Active consents | doctor + organization + scope cards, "Manage consent & access" | EXISTING |
| My Care Network | diagram | EXISTING |

## My Health — EXISTING, actions TO IMPLEMENT

Medicines I'm taking now · My last visit (+ Additional notes) · Earlier visits · My latest test results ·
**Information I added** (patient-provided badge) with "Add a health note" / "Add allergy or information" ·
**My documents** with "Upload a document". The three add/upload buttons become working dialogs (same components as Home).

### Patient entry dialog (TO IMPLEMENT)
- Title "Add to my health record"; type selector: Note · Allergy · Condition · Medication I take · Other.
- Fields: title (required), details (optional). For Allergy: substance (title) + reaction (details).
- Explainer: *"This is added as patient-provided information. Your doctors will see it marked as reported by you, not verified."*
- Buttons: Cancel · Save. On save: success toast, entry appears in "Information I added" and on the timeline as "Added by you".

### Upload dialog (TO IMPLEMENT)
- File uploader (PDF/PNG/JPG, 10 MB), title (required), type (`DocumentType` labels), optional description.
- Explainer: *"Uploaded documents are marked as patient-provided. Doctors see them only if you share Documents."*
- Errors shown inline (reuse `ClinicalValidationError` messages).

## Medical Timeline — EXISTING

- Filters: All · Consultations · Prescriptions · Labs · Hospital · Pharmacy · Documents (with counts).
- Left card: record count, since, sources (organizations + you).
- Every entry shows provenance:

| Source | Display |
|---|---|
| Patient-provided | "Added by you" event label, violet |
| Clinician | `org badge` + "Dr. Name" (e.g. *South City Hospital · Dr. Arif Hassan*) |
| Laboratory | `HealthLab Diagnostics` org badge |
| Pharmacy | `HealthPlus Pharmacy` org badge |

- Never shown: internal clinician notes, drafts. Patient entries and patient uploads (once implemented) appear with source `patient`.

## Prescriptions — EXISTING, send TO IMPLEMENT (D5)

- "Choose a pharmacy" section for `issued` prescriptions: pharmacy selector (HealthPlus Pharmacy, CarePoint Pharmacy) +
  **Send Prescription** (currently placeholder) → confirmation dialog *"Only {pharmacy} will receive this prescription — medicines, dosage and your allergies. Not your medical history."* → send.
- "All prescriptions": cards with plain status + progress tracker (Prescribed → Sent → Verified → Dispensed → Billed).

## Medications · Lab Reports — EXISTING (read-only)

## Documents page — TO IMPLEMENT (D3)

Filter chips: All · From my doctors · From laboratories · Added by me. Each card: title, type, source badge, date,
linked consultation (if any), "Download" (via `document_service.read_file`). "Upload a document" button.

## Care Network — EXISTING

Diagram, "My doctors" (organizations + what each can see now), "My care organizations", link to Consent & Access.

## Consent & Access — EXISTING

See [05_patient_consent_workflow.md](05_patient_consent_workflow.md). Components: share dialog, people-with-access cards,
view-access dialog, revoke dialog, past-access table, history tabs.

## Placeholder relabelling (D11)

Replace "Phase 5" captions on the remaining patient placeholders with neutral roadmap text; when a placeholder is
implemented, remove the `phase_action` call entirely.

## UI states that must exist for every new control

| State | Behaviour |
|---|---|
| Empty | Friendly empty state (`empty_state`) — never a blank card |
| Validation error | Inline under the field, form keeps the user's input |
| Success | `hb_flash` toast + the new item visible without a manual refresh |
| Denied | Never shown to the patient for their own record; other-patient access is not reachable from the UI |
