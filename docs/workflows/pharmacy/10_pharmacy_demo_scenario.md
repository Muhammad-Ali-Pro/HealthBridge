# 10 — Pharmacy Demo Scenario

Runs after the Patient and Doctor demos (or standalone after *Reset demo data*). Personas: Ahmed Khan (patient),
Dr. Arif Hassan @ South City Hospital (doctor), Sana Iqbal @ HealthPlus Pharmacy (pharmacist).

## A. Primary — full lifecycle (≈ 5 min)

| # | Presenter does | Audience sees | Status |
|---|---|---|---|
| 1 | As Ahmed: Consent & Access → share Consultations, Prescriptions, Current medications with Dr. Arif @ South City Hospital | Consent active | EXISTING |
| 2 | As Dr. Arif: Ahmed → New consultation → **Save & create prescription** → Paracetamol 500 mg ×20, Cetirizine 10 mg ×5 → **Issue** → select **HealthPlus Pharmacy** → **Send** | "Sent to HealthPlus Pharmacy" | EXISTING |
| 3 | Landing → **Continue as HealthPlus Pharmacy** (Sana) | Dashboard: Awaiting verification +1; minimum-necessary note | EXISTING |
| 4 | Pending Verification → open RX | Patient identity, **Penicillin** allergy chip, medicines, prescriber, South City Hospital — **no** diagnosis or history | EXISTING |
| 5 | Tick the four checks → **Verify prescription** | Status `verified`; moves to "Ready to dispense" | TO IMPLEMENT |
| 6 | **Record dispensing** → both medicines full quantity → Save | Status `dispensed`; Dispensing log row | TO IMPLEMENT |
| 7 | **Generate invoice** → unit prices (Paracetamol 2, Cetirizine 8) → Create | INV-…, PKR 80, `pending` | TO IMPLEMENT |
| 8 | Billing → **Record payment** PKR 80 | `paid`; Collected KPI updates | TO IMPLEMENT |
| 9 | As Ahmed: Prescriptions | Tracker Prescribed → Sent → Verified → Dispensed → **Billed (paid)**; timeline Pharmacy filter shows verified, dispensed, invoice | EXISTING display |
| 10 | As Dr. Arif: Ahmed's prescription | Verified / dispensed lifecycle, quantities; **no invoice** | EXISTING status; quantities display TO IMPLEMENT |

Talking points: pharmacy sees only what it needs; every step is attributed to HealthPlus Pharmacy and Sana Iqbal;
the patient sees billing, the doctor does not; nothing is substituted automatically.

## B. Partial dispensing

| # | Action | Result |
|---|---|---|
| 1 | Doctor prescribes Paracetamol 500 mg ×20 → HealthPlus | `sent` |
| 2 | Sana verifies | `verified` |
| 3 | Record dispensing: quantity now **10**, line status *Partial*, note "Remaining 10 tomorrow" | `partially_dispensed`; outstanding 10 |
| 4 | Generate invoice for this event (10 × PKR 2) → record payment PKR 10 | Invoice `partially_paid` |
| 5 | Ahmed sees "Part of your medicine was collected from HealthPlus Pharmacy" and the invoice | Patient view |
| 6 | Next day: Record dispensing 10 → *Dispensed* | `dispensed`; second dispensing event; second invoice possible (D13) |

## C. Rejection and substitution (optional)

- **Reject:** a prescription with a medicine matching Ahmed's allergy → allergy alert → **Reject with reason** "Allergy conflict — please review" → `rejected`; Ahmed: "could not fill… contact your doctor"; Dr. Arif sees the reason.
- **Substitution:** line *Request substitution* "Brand out of stock; generic available" → event recorded, prescription stays outstanding, Dr. Arif and Ahmed see the request; nothing changes in the prescription.

## Fallbacks
Reset demo data; the seed already contains HealthPlus prescriptions in `sent` and `verified` states for a quick start.
