# 12 — Patient Test Plan

Runner: `.venv\Scripts\python.exe -m pytest -q` (+ `python -m pyflakes agents core services ui views tests data app.py`).
Fixtures (`tests/conftest.py`): `seeded` (in-memory DB with demo data), `actor(name, org)`, `pid(name)`; UI tests use
Streamlit `AppTest` against a temp DB. **AppTest caveat:** after app code calls `st.switch_page`, the next `at.run()`
returns to the test's page — follow navigations with `at.switch_page(...)` (see `tests/test_phase2_fixes.py`).

Proposed new files: `tests/test_patient_workflow.py` (service/authorization), `tests/test_patient_ui.py` (AppTest).

## Critical tests

| # | Requirement | Level | Status / where |
|---|---|---|---|
| 1 | Patient can view own records | service | EXISTING `test_access_control::test_patient_sees_own_full_record_only` |
| 2 | Patient can grant consent | service | EXISTING `test_consent::test_grant_selected_records_gives_scoped_access_and_is_audited` |
| 3 | Patient selects specific categories | service | EXISTING `test_consent::test_demo_story_ahmed_shares_selected_records_with_dr_arif`, `test_access_control::test_selected_scope_filters_every_record_type` |
| 4 | Share all only after confirmation | service | EXISTING `test_consent::test_share_all_requires_explicit_confirmation`; **UI TO IMPLEMENT**: warning text + "Confirm & Share All Records" label |
| 5 | Consent is organization-specific | service | EXISTING `test_access_control::test_consent_is_organization_specific` |
| 6 | Same doctor at another org gets nothing | service + UI | EXISTING (`test_phase2_additions::test_same_doctor_two_organizations_different_consent_states`, `test_phase2_fixes::test_restricted_banner_points_to_working_at_selector`) |
| 7 | Patient can revoke | service | EXISTING `test_consent::test_revoke_removes_access_but_never_deletes_records`; **UI TO IMPLEMENT** revoke dialog |
| 8 | Revocation blocks doctor | service | EXISTING (same) — add explicit `ACCESS_DENIED` audit assertion **TO IMPLEMENT** |
| 9 | Revocation blocks AI | service | EXISTING `test_copilot::test_ai_summary_is_audited_scoped_and_hidden_after_revocation`; add `preview`/`flags_for_summary`/`resolve_sources` denial **TO IMPLEMENT** |
| 10 | Patient-created info correctly marked | service + UI | **TO IMPLEMENT**: entry → `source_type=patient`, `provider_id=null`, badge rendered |
| 11 | Internal clinician notes hidden | service + UI | EXISTING (`test_phase2_additions::test_internal_notes_never_reach_the_patient`, `test_phase2_fixes::test_patient_sees_additional_notes_but_not_internal_note_in_ui`) |
| 12 | Audit events generated | service | EXISTING for consent/access; **TO IMPLEMENT** for entries/uploads/patient send |
| 13 | Cannot modify clinician records | service | **TO IMPLEMENT**: patient actor → `clinical_service.save_consultation/add_note` raise `AccessDenied` |
| 14 | Cannot modify prescriptions | service | **TO IMPLEMENT**: patient → `prescription_service.save_draft/issue` raise; patient send of non-issued refused |
| 15 | Cannot modify lab reports | service | **TO IMPLEMENT**: patient → `lab_service.list_orders` raises; no write API reachable |

## Unit tests (TO IMPLEMENT)
- Patient entry validation: title required/≤200, details ≤2000, type ∈ `PatientEntryType`.
- Patient upload validation: allowed extensions, empty file, >10 MB, missing title.
- `activity_service.record` (after A1): `source_type` honoured; `provider_id` null for patient/pharmacist actors.
- Prescription plain-status mapping covers every `PrescriptionStatus` (incl. `rejected`, `cancelled`) and invoice states.

## Service tests (TO IMPLEMENT)
- `add_entry` note / allergy / condition → row, timeline event (`patient_entry`, category `documents`, source `patient`), audit row.
- Allergy entry leaves `Patient.allergies` unchanged (D2).
- `upload_own` stores file under `UPLOAD_DIR/patient_<id>/`, `Document.source_type=patient`, `organization_id=None`; `read_file` works for the patient.
- D5: patient `send_to_pharmacy` happy path; refuses non-issued, other patient's, non-pharmacy target; doctor branch unchanged (regression).
- D1 (if approved): doctor with only `prescriptions` consent sees patient-reported allergies; does not see other patient entries.

## Authorization tests (TO IMPLEMENT unless noted)
- Patient A cannot add entries/upload for patient B (`require_self`).
- Doctor/pharmacist/lab cannot call `add_entry` / `upload_own` / patient send branch.
- After revocation: `copilot_service.preview`, `generate`, `latest`, `flags_for_summary`, `resolve_sources` all raise for the doctor.
- `audit_service.patient_history` refuses non-self actors (EXISTING behaviour; add test).

## UI tests (AppTest) (TO IMPLEMENT unless noted)
- Every patient page renders without exception (EXISTING `test_ui_smoke::test_page_renders_without_error`; extend for Documents page).
- Patient nav includes Documents (update `test_role_specific_navigation`).
- Home/My Health dialogs: add note → visible with badge; add allergy → visible; validation errors inline.
- Upload dialog: valid file → listed; invalid → error.
- Consent dialog: default South City (EXISTING `test_phase2_fixes`), share-all warning + confirm label, selected without category disabled.
- Revoke dialog: confirm → Past access + flash.
- Prescriptions: patient send (D5) → card shows "Sent to HealthPlus Pharmacy".

## Integration tests (TO IMPLEMENT)
- Full story: grant (selected) → doctor reads only scoped categories → doctor AI payload has no unconsented ids → revoke → doctor denied + `ACCESS_DENIED` audited → history lists grant, access, revoke, denial in order.
- Patient entry → doctor with `documents` consent sees it labelled patient-provided; doctor without it does not (except D1 allergies).

## Browser tests (real Chrome, manual or scripted via CDP as in Phase 2)
Follow [10_patient_demo_scenario.md](10_patient_demo_scenario.md) end-to-end and record PASS/FAIL per step, including:
consent default, selective grant, doctor scope, organization switch lock, revoke, doctor lock, patient note/allergy/upload,
timeline provenance, internal note absence.

## Regression tests (must stay green)
All existing suites, in particular: `test_consent.py`, `test_access_control.py`, `test_copilot.py`,
`test_ai_provider.py`, `test_doctor_ui.py`, `test_doctor_workflow.py`, `test_phase2_additions.py`, `test_phase2_fixes.py`.
The Doctor workflow must not change behaviour.
