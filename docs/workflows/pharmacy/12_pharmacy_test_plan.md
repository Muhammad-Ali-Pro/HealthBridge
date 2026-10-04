# 12 — Pharmacy Test Plan

Same tooling as [../patient/12_patient_test_plan.md](../patient/12_patient_test_plan.md) (pytest, `seeded` fixture,
AppTest with the `switch_page` caveat, pyflakes). Proposed files: `tests/test_pharmacy_workflow.py`
(service/authorization/integration) and `tests/test_pharmacy_ui.py` (AppTest). Helper fixture: a prescription created through
the real doctor services (`clinical_service.save_consultation` → `prescription_service.save_draft/issue/send_to_pharmacy`).

## Critical tests

| # | Requirement | Level | Status |
|---|---|---|---|
| 1 | Pharmacy only sees prescriptions assigned to it | service | EXISTING `test_access_control::test_pharmacy_sees_only_routed_prescriptions_minimum_necessary`; add per-id `get_prescription` denial TO IMPLEMENT |
| 2 | Cannot access unrelated patient records | service | EXISTING (same test: `get_authorized_record` → `AccessDenied`) |
| 3 | Cannot access AI | service | TO IMPLEMENT: pharmacist → `copilot_service.preview/generate/latest/review_flag` raise |
| 4 | Cannot dispense before verification | service | TO IMPLEMENT |
| 5 | Cannot over-dispense | service | TO IMPLEMENT (single event and cumulative across events) |
| 6 | Partial dispensing works | service | TO IMPLEMENT (status `partially_dispensed`, outstanding computed) |
| 7 | Full dispensing works | service | TO IMPLEMENT (status `dispensed`) |
| 8 | Invoice generated | service | TO IMPLEMENT (total, number format, link to dispensing, billing event) |
| 9 | Patient sees status | service + UI | TO IMPLEMENT (own_record shows new status/invoice; patient Prescriptions text) |
| 10 | Doctor sees status | service + UI | TO IMPLEMENT (authorized record shows dispensing; no invoice) |
| 11 | Audit generated | service | TO IMPLEMENT (one row per action; actor_type, org, provider_id null; timeline source organization) |

## Unit tests
- Quantity math: outstanding per item from multiple `Dispensing` rows; aggregate `Dispensing.status` from lines (D6).
- Prescription status recomputation table (verified/partial/dispensed/unchanged).
- Invoice total = Σ quantity × unit price, rounded to 2 dp; number format `INV-{yyyy}-{rx:05d}-{n}` unique.
- Payment status from (total, amount_paid).

## Service tests
- verify happy path; verify on every non-`sent` status refused.
- reject requires reason; terminal afterwards.
- record_dispensing: full; partial then complete; unavailable only (status unchanged); substitution request (items unchanged, text stored); mixed lines.
- generate_invoice: happy path; duplicate refused; zero-quantity event refused; non-positive price refused.
- record_payment: partial, full, over, zero, on cancelled/paid refused; cancel unpaid ok, cancel paid refused.
- D7: `verified_at`/`verified_by` persisted; schema version bumped and seed rebuild works.

## Authorization tests
- CarePoint pharmacist → every HealthPlus action by id → `AccessDenied` + `ACCESS_DENIED` audit.
- Doctor / patient / lab actors → `pharmacy_service` writes → `AccessDenied`.
- Pharmacist → `record_service`, `consent_service`, `clinical_service`, `copilot_service` → denied.
- `prescription_to_out` for pharmacy never includes consultation reason (EXISTING behaviour; keep asserted).

## UI tests (AppTest)
- Every pharmacy page renders (EXISTING smoke) and shows no placeholder for implemented actions.
- Pending Verification: checklist gating; verify → card moves to "Ready to dispense"; reject dialog requires reason.
- Dispensing form: max quantity enforced; partial → status badge; unavailable/substitution lines render.
- Billing: generate invoice → row; record payment → badge `paid`; cancel unpaid.
- Patient Prescriptions shows the new plain-language statuses; doctor prescription page shows lifecycle without billing.

## Integration tests
- Full chain: patient consent → doctor prescribes & sends → pharmacy verify → partial → complete → invoice → payment →
  patient sees billed/paid → doctor sees dispensed, no invoice → audit rows in order with correct actors.
- Rejection chain: send → reject → doctor & patient see reason → no further actions possible.

## Browser tests (real Chrome)
Run [10_pharmacy_demo_scenario.md](10_pharmacy_demo_scenario.md) A and B end-to-end; record PASS/FAIL per step.

## Regression tests
All existing suites must stay green; in particular Phase 2 doctor send-to-pharmacy tests
(`test_phase2_additions::test_prescription_sent_to_selected_pharmacy`, `test_pharmacy_handoff_rules`,
`test_doctor_ui::test_prescription_detail_sends_to_selected_pharmacy`) and the patient workflow tests.
