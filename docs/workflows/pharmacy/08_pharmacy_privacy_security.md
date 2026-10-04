# 08 — Pharmacy Privacy & Security

| # | Scenario | Expected response | Enforcement point | Status |
|---|---|---|---|---|
| 1 | **Wrong pharmacy**: CarePoint pharmacist opens/acts on a HealthPlus prescription (forged id) | `AccessDenied("This prescription is not available to your pharmacy")`, no change, `ACCESS_DENIED` audited | `pharmacy_service.get_prescription` / every write checks `rx.pharmacy_id == actor org` | List filter EXISTING; per-id check TO IMPLEMENT |
| 2 | **Wrong organization context**: pharmacist account acting under a non-pharmacy organization | `AccessDenied("Pharmacy staff only")` | `_require_pharmacy` (org type must be `pharmacy`) | EXISTING |
| 3 | **Unauthorized patient**: pharmacy requests a patient record / timeline / documents | `AccessDenied` — "Pharmacies and laboratories only see the prescriptions and test orders sent to them." | `access_service.authorize` | EXISTING (tested) |
| 4 | **Not-yet-sent prescription** (`draft`/`issued`) | Invisible; per-id access denied | `HIDDEN` statuses filter | EXISTING list; per-id TO IMPLEMENT |
| 5 | **Dispensing before verification** | Refused: "Verify the prescription before dispensing" | `record_dispensing` status guard | TO IMPLEMENT |
| 6 | **Over-dispensing** (cumulative > prescribed, negative, non-integer) | Refused with the outstanding quantity; nothing written | `record_dispensing` quantity invariant | TO IMPLEMENT |
| 7 | **Prescription modification** (items, dose, quantity, prescriber) | No API exists; UI offers none | Immutable after issue | EXISTING by absence — keep it that way |
| 8 | **Accessing unrelated medical records** (consultation reason, diagnosis, labs, documents, other prescriptions) | Not returned | `include_reason=False`; queries filtered by `pharmacy_id` | EXISTING (tested) |
| 9 | **Accessing AI information** (summaries, flags, Copilot) | Denied | `copilot_service._require_doctor`; no pharmacy UI | EXISTING |
| 10 | Double verification / race (two pharmacists) | Second attempt refused (status no longer `sent`) | status guard inside the transaction | TO IMPLEMENT |
| 11 | Re-invoicing the same dispensing | Refused ("Invoice already exists for this dispensing") | `generate_invoice` guard | TO IMPLEMENT |
| 12 | Overpayment / payment on cancelled or paid invoice | Refused | `record_payment` guard | TO IMPLEMENT |
| 13 | Automatic substitution | Impossible — only a request is stored | `substitution_requested` never changes items | TO IMPLEMENT (design rule) |
| 14 | Rejection without reason | Refused | `reject` validation | TO IMPLEMENT |
| 15 | Doctor or patient calls pharmacy write functions | `AccessDenied` | `_require_pharmacy` | TO IMPLEMENT (tests) |
| 16 | Pharmacy sees billing of other pharmacies | Not returned | `Invoice.organization_id` filter | EXISTING |
| 17 | Doctor sees invoices | Never (D8) | `BILLING_CATEGORY` not shareable | EXISTING (tested) |
| 18 | Free text (reason, substitution request, notes) with HTML/script | Escaped on render (`esc`) | UI | must hold |

## Data minimization notes

- Allergies are shown to the pharmacy deliberately (dispensing safety) — documented exception, already in place.
- Patient phone/address are not shown in pharmacy UI.
- Audit details for pharmacy events contain drug names and quantities only — no diagnoses.
