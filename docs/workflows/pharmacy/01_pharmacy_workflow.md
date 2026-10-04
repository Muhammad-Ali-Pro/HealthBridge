# 01 — Pharmacy Workflow (overview)

**Priority:** implement **after** the Patient workflow is implemented, verified and approved.
Labels: **EXISTING** · **TO IMPLEMENT** · **FUTURE** · **DECISION Dn** (see [../README.md](../README.md)).

## End-to-end flow

```text
Doctor (EXISTING, Phase 2)
  ↓  Prescription: draft → issued                          prescription_service.save_draft / issue
  ↓  Send to Pharmacy (doctor; patient = D5)                prescription_service.send_to_pharmacy → status "sent"
HealthPlus Pharmacy (Sana Iqbal, Pharmacist in charge)
  ↓  Queue: "Awaiting verification"                         EXISTING read (pharmacy_service.list_prescriptions)
  ↓  Verification: verify  → "verified"                     TO IMPLEMENT
  │               reject  → "rejected" (reason, terminal)   TO IMPLEMENT (D9)
  ↓  Dispensing (per medicine: dispensed / partial /        TO IMPLEMENT (D6)
  │   unavailable / substitution_requested)
  │   → "partially_dispensed" (some quantity outstanding)
  │   → "dispensed"           (every medicine fully dispensed)
  ↓  Invoice (per dispensing event, simulated PKR)          TO IMPLEMENT (D13, D14)
  ↓  Payment status: pending → partially_paid → paid        TO IMPLEMENT (cancelled if unpaid)
Patient (EXISTING display)
  ↓  sees status, quantities, pharmacy, invoice & payment on Prescriptions + Timeline
Doctor (EXISTING data, display partly TO IMPLEMENT)
  ↓  sees lifecycle (sent / verified / rejected + reason / dispensed / partial / substitution request) — never billing (D8)
```

## What exists today

| Area | Status | Where |
|---|---|---|
| Pharmacist personas | EXISTING | Sana Iqbal @ HealthPlus Pharmacy; Hamza Sheikh @ CarePoint Pharmacy (`data/seed.py`) |
| Navigation | EXISTING | Dashboard · Prescriptions · Pending Verification · Dispensing · Billing · Patients (`ui/shell.py`) |
| Minimum-necessary read service | EXISTING | `services/pharmacy_service.py`: `list_prescriptions`, `queue_overview`, `list_invoices`, `billing_overview`, `patients` |
| Queue / detail panel | EXISTING read-only | `views/pharmacy/pending.py` + `ui/workflows.pharmacy_detail` (medicines, prescriber, organization, allergies, checklist) |
| Dispensing log, billing table | EXISTING read-only | `views/pharmacy/dispensing.py`, `views/pharmacy/billing.py` |
| Models | EXISTING | `Prescription`, `PrescriptionItem`, `Dispensing`, `Invoice`; enums `PrescriptionStatus`, `DispensingStatus`, `PaymentStatus` |
| Timeline/audit conventions for pharmacy events | EXISTING in seed only | `data/seed.py::_prescription` (`source_type="organization"`, `actor_type="pharmacist"`, events `prescription_verified`, `dispensing`, `invoice_issued`) |
| Every pharmacy **action** (verify, reject, dispense, partial, unavailable, substitution, invoice, payment) | **TO IMPLEMENT** | currently `phase_action(...)` placeholders |
| AI pharmacy check | **FUTURE** | placeholder card "Phase 6" in `pharmacy_detail` |

## Service functions to add (TO IMPLEMENT, in `services/pharmacy_service.py`)

| Function | Purpose |
|---|---|
| `get_prescription(session, actor, rx_id)` | Single prescription, only if routed to the actor's pharmacy |
| `verify(session, actor, rx_id)` | `sent → verified` (sets `verified_at`, `verified_by` — D7) |
| `reject(session, actor, rx_id, reason)` | `sent → rejected`, reason required → `status_reason` |
| `record_dispensing(session, actor, rx_id, lines, notes="", substitution_request="")` | One `Dispensing` event with per-medicine lines; updates prescription status |
| `generate_invoice(session, actor, dispensing_id, unit_prices)` | Invoice for that dispensing event's dispensed quantities |
| `record_payment(session, actor, invoice_id, amount)` | Updates `amount_paid` / `payment_status` |
| `cancel_invoice(session, actor, invoice_id, reason)` | Only while nothing has been paid |

All functions: `_require_pharmacy(actor)` + the prescription/invoice must belong to that pharmacy; write timeline + audit through
`activity_service.record(..., source_type="organization")` (A1).

## Out of scope (FUTURE)

Inventory/stock levels, suppliers, pricing catalogue, real payment gateway, insurance, controlled-drug registers,
returns/refunds, prescriber cancellation (`cancelled` exists in the enum but no service sets it — D17),
automatic substitution (never), AI pharmacy checks (Phase 6), real pharmacy integrations.
