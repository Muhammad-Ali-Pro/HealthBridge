# 11 — Pharmacy Acceptance Criteria

Tags: **[E]** existing (must not regress) · **[T]** to implement · **[D]** depends on a decision (default assumed).

## Dashboard
- **AC-R1 [E]** Given Sana works at HealthPlus Pharmacy, when she opens the Dashboard, then KPIs (awaiting verification, ready to dispense, dispensed today, pending) count only HealthPlus prescriptions.
- **AC-R2 [E]** The queue never shows `draft`/`issued` prescriptions or prescriptions routed to CarePoint Pharmacy.

## Verification
- **AC-R3 [T]** Given a `sent` HealthPlus prescription, when Sana ticks all four checks and confirms *Verify*, then status = `verified`, `verified_by` = Sana, `verified_at` set (D7), a `prescription_verified` timeline event (source organization) and `RECORD_UPDATED` audit exist.
- **AC-R4 [T]** Given fewer than four checks ticked, then *Verify* is disabled.
- **AC-R5 [T]** Given a prescription that is not `sent`, then verify is refused and nothing changes.

## Rejection
- **AC-R6 [T]** Given a `sent` prescription, when Sana rejects with a reason, then status = `rejected`, `status_reason` = reason, event `prescription_rejected` is audited, and the patient sees "could not fill… contact your doctor".
- **AC-R7 [T]** Given an empty reason, then rejection is refused.
- **AC-R8 [T][D9]** Given a `rejected` prescription, then no further pharmacy action is offered or accepted.

## Dispensing
- **AC-R9 [T]** Given a `sent` prescription, when dispensing is attempted, then it is refused ("Verify the prescription before dispensing").
- **AC-R10 [T]** Given a `verified` prescription, when every medicine is dispensed in full, then one `Dispensing(status=dispensed)` row exists with per-line quantities and the prescription is `dispensed`.
- **AC-R11 [T]** Given Paracetamol ×20, when 10 are dispensed, then the prescription is `partially_dispensed` with 10 outstanding; when the remaining 10 are dispensed later, it becomes `dispensed`.
- **AC-R12 [T]** Given 20 prescribed and 10 already dispensed, when 11 are entered, then the save is refused and nothing is written.

## Unavailable · Substitution
- **AC-R13 [T]** Given a line marked *Unavailable*, then quantity 0 is recorded, the medicine stays outstanding, and the patient and doctor see it as unavailable at HealthPlus.
- **AC-R14 [T][D10]** Given *Request substitution* with text, then the request is stored on the dispensing event, items are unchanged, and the prescriber and patient can read the request.

## Invoice · Payment
- **AC-R15 [T][D13][D14]** Given a dispensing event with dispensed quantities, when Sana enters unit prices and generates an invoice, then an `Invoice(pending)` linked to that dispensing exists with correct total, and `invoice_issued` (category billing) is audited.
- **AC-R16 [T]** A second invoice for the same dispensing event is refused.
- **AC-R17 [T]** Payment less than outstanding → `partially_paid`; equal → `paid`; greater, zero or negative → refused.
- **AC-R18 [T]** An unpaid invoice can be cancelled with a reason; a (partially) paid one cannot.

## Patient visibility
- **AC-R19 [E/T]** Ahmed sees each status change, dispensed quantities, rejection reason, substitution request, invoice and payment status on Prescriptions and the timeline (display EXISTING; data from new actions).

## Doctor visibility
- **AC-R20 [T]** Dr. Arif (consented, prescriber) sees verified / rejected (with reason) / partial / dispensed / substitution requests for his prescriptions, and never sees invoices or payment (D8).

## Audit
- **AC-R21 [T]** Every pharmacy action creates exactly one audit row with `actor_type=pharmacist`, `organization_id` = pharmacy, `provider_id` null, and a timeline event with `source_type=organization`.

## Security
- **AC-R22 [T]** A CarePoint pharmacist calling any HealthPlus action by id gets `AccessDenied` and an `ACCESS_DENIED` audit row.
- **AC-R23 [E]** A pharmacist cannot read Ahmed's longitudinal record, consultations, labs, documents, AI summaries or flags.
- **AC-R24 [T]** Doctors and patients cannot call pharmacy write functions.
