# 09 — Who Sees What (Patient · Doctor · Pharmacy)

Adjusted to the actual architecture. "Consent-based" = doctor at the organization named in an active consent that
covers the category; the prescribing doctor also sees records they authored at that organization while consented.

| Information | Patient | Doctor | Pharmacy |
|---|---|---|---|
| Prescription (header, prescriber, organization, dates, status) | ✅ own | ✅ consent: `prescriptions` (or own authored) | ✅ only if routed to it and status ≥ `sent` |
| Consultation reason linked to a prescription | ✅ | ✅ consent | ❌ (`include_reason=False`) |
| Medicines (drug, strength, dosage, route, frequency, duration, quantity, instructions) | ✅ | ✅ consent | ✅ routed only |
| Current medications list (derived) | ✅ | ✅ consent: `medications` | ❌ |
| Patient identity (name, HB-ID, age, sex) | ✅ | ✅ any consent; directory search shows identity only | ✅ routed only |
| Clinician-documented allergies | ✅ | ✅ any consent | ✅ routed only (safety) |
| Patient-reported allergies | ✅ | ✅ consent `documents` (D1: any consent) | ❌ (FUTURE: consider for safety) |
| Pharmacy verification status / rejection reason | ✅ | ✅ consent | ✅ |
| Dispensing status, per-medicine lines | ✅ | ✅ consent (display TO IMPLEMENT on doctor prescription page) | ✅ own pharmacy |
| Dispensed quantities | ✅ | ✅ consent | ✅ |
| Substitution request text | ✅ | ✅ consent (prescriber should see it) | ✅ |
| Billing: invoice, amounts, payment status | ✅ | ❌ never (D8) | ✅ own invoices |
| Full medical history (consultations, notes, hospital records) | ✅ (minus internal notes) | consent-based per category | ❌ |
| Lab / imaging reports | ✅ published only | consent: `lab_reports` / `imaging_reports` | ❌ |
| Documents | ✅ | consent: `documents` | ❌ |
| Internal clinician notes | ❌ | ✅ authorized clinicians | ❌ |
| Doctor's private drafts | ❌ | author only | ❌ |
| AI summary | ❌ | ✅ requesting doctor at that org, active consent | ❌ |
| AI flags | ❌ | ✅ requesting doctor at that org, active consent | ❌ |
| Consent records & access history | ✅ | ❌ (sees only the resulting access banner) | ❌ |
| Audit trail | ✅ own filtered view | own activity (`provider_activity`) | FUTURE own activity |

Status: rows marked ✅ for the Pharmacy column are EXISTING in `pharmacy_service` (read) except actions, which are TO IMPLEMENT.
