# 05 — Pharmacy UI Workflow

Hackathon-focused: replace placeholders with working actions on the **existing** pages; no inventory screens.
Keep the HealthBridge design system and the minimum-necessary note on every page that shows patient data.

| Nav item | Page | Today | Target |
|---|---|---|---|
| Dashboard | `views/pharmacy/dashboard.py` | EXISTING KPIs + queue + recently dispensed | Add KPI "Outstanding (PKR)"; queue cards link to Pending Verification detail |
| Prescriptions | `views/pharmacy/prescriptions.py` | EXISTING list, filters all/sent/verified/dispensed | Add filters *partially dispensed* and *rejected* |
| Pending Verification | `views/pharmacy/pending.py` | EXISTING tabs + master–detail (`ui/workflows.pharmacy_detail`) with placeholder buttons | Working **Verify** / **Reject** (tab 1) and **Record dispensing** (tab 2) |
| Dispensing | `views/pharmacy/dispensing.py` | EXISTING log | Show per-line status, substitution request text, "Generate invoice" for un-invoiced events |
| Billing | `views/pharmacy/billing.py` | EXISTING KPIs + invoice table, "Record payment" placeholder | Working **Record payment** and **Cancel invoice** per row |
| Patients | `views/pharmacy/patients.py` | EXISTING identity + allergies + this pharmacy's prescriptions | unchanged |

## Prescription detail (`ui/workflows.pharmacy_detail`) — target layout

1. Header: RX id, patient name, age, sex, received time, status badge. Allergy chips.
2. Medication table (existing) + columns *Dispensed so far* and *Outstanding* once dispensing has started.
3. Prescriber + prescribing organization + dispensing pharmacy (existing).
4. **Verification** (status `sent`): checklist of four checkboxes (identity, allergy cross-check, dose/frequency/duration,
   prescriber & organization). **Verify prescription** enabled only when all are ticked → confirmation dialog.
   **Reject with reason** → dialog with required reason.
5. **Dispensing** (status `verified` / `partially_dispensed`): **Record dispensing** opens a form with one row per
   medicine: outstanding, quantity now (number input, max = outstanding), line status (Dispensed / Partial / Unavailable /
   Request substitution), note; substitution text area appears when requested. Summary preview → **Save dispensing**.
6. Dispensing history for this prescription (existing data, list of events with lines).
7. **Billing**: per dispensing event — invoice or **Generate invoice** (unit price per line, total preview).
8. AI pharmacy check card stays a FUTURE placeholder (relabel per D11).

Allergy safety cue: if a medicine name matches a listed allergy (reuse `prescription_service.allergy_warnings`), show a
danger alert above the verification actions. The pharmacist decides; nothing is blocked automatically.

## Messages (plain language)

| Event | Toast |
|---|---|
| Verified | "RX-00012 verified — ready to dispense." |
| Rejected | "RX-00012 rejected. The prescriber and patient can see the reason." |
| Full dispensing | "All medicines dispensed for RX-00012." |
| Partial | "Partially dispensed — 10 of 20 Paracetamol outstanding." |
| Substitution requested | "Substitution request sent to Dr. Arif Hassan. Nothing was substituted." |
| Invoice | "Invoice INV-2026-00012-1 created (PKR 240)." |
| Payment | "Payment recorded — invoice is now Paid." |

## Error states

Invalid transition, over-dispensing, payment > outstanding, missing reason: inline error, no state change, form keeps input.
Prescription routed elsewhere: generic "This prescription is not available to your pharmacy."
