# 03 — Pharmacy State Machines

All status names are the actual enum values in `core/models.py`.

## 1. Prescription (`PrescriptionStatus`)

```text
 draft ──issue()──▶ issued ──send_to_pharmacy()──▶ sent ──verify()──▶ verified ──record_dispensing()──┐
  (doctor)            (doctor)        (doctor; patient = D5)   │ (pharmacy)                  (pharmacy)  │
                                                              │                                         ▼
                                                              └─reject()──▶ rejected        partially_dispensed
                                                                            (terminal)            │   ▲  │
                                                                                                  └───┘  │ record_dispensing()
                                                                                                         ▼ (all quantities complete)
                                                                                                      dispensed (terminal)
 cancelled — enum value exists; no service sets it (prescriber cancellation is FUTURE, D17)
```

| From | To | Actor | Function | Guard | Status |
|---|---|---|---|---|---|
| draft | issued | prescribing doctor | `prescription_service.issue` | own draft, consent | EXISTING |
| issued | sent | prescribing doctor | `send_to_pharmacy` | prescriber at prescribing org, consent, target is a pharmacy | EXISTING |
| issued | sent | patient | `send_to_pharmacy` (patient branch) | own prescription | TO IMPLEMENT (D5) |
| sent | verified | pharmacist of that pharmacy | `pharmacy_service.verify` | routed here | TO IMPLEMENT |
| sent | rejected | pharmacist of that pharmacy | `pharmacy_service.reject` | routed here, reason | TO IMPLEMENT |
| verified | partially_dispensed | pharmacist | `record_dispensing` | some quantity dispensed, some outstanding | TO IMPLEMENT |
| verified / partially_dispensed | dispensed | pharmacist | `record_dispensing` | every item cumulative = prescribed | TO IMPLEMENT |
| partially_dispensed | partially_dispensed | pharmacist | `record_dispensing` | more dispensed, still outstanding; or only unavailable/substitution lines | TO IMPLEMENT |
| verified | verified | pharmacist | `record_dispensing` | nothing dispensed (all lines unavailable / substitution requested) | TO IMPLEMENT |

### Invalid transitions (must raise and change nothing)

| Attempt | Expected error |
|---|---|
| verify / reject a `draft`, `issued`, `verified`, `partially_dispensed`, `dispensed`, `rejected`, `cancelled` prescription | "Only prescriptions awaiting verification can be verified/rejected" |
| dispense a `sent` (unverified) prescription | "Verify the prescription before dispensing" |
| dispense a `dispensed`, `rejected`, `cancelled` prescription | "This prescription can no longer be dispensed" |
| any action on a prescription routed to another pharmacy | `AccessDenied` (+ `ACCESS_DENIED` audit) |
| `verified → sent`, `partially_dispensed → verified`, anything out of `dispensed`/`rejected` | not offered; service refuses |
| pharmacy edits items, quantities prescribed, dosage, prescriber | no API exists; prescriptions are immutable after issue |

## 2. Medicine dispensing (`DispensingStatus`) — per line (D6) and per event

Values: `dispensed`, `partial`, `unavailable`, `substitution_requested`. There is **no** `pending` value — a medicine is
*pending* when its cumulative dispensed quantity < prescribed and no line covers it yet (derived, not stored).

Per-line (inside `Dispensing.items_dispensed` JSON, D6):

| Line status | quantity_dispensed | Meaning |
|---|---|---|
| `dispensed` | = outstanding (completes the medicine) | Fully supplied |
| `partial` | 0 < q < outstanding | Some supplied, remainder outstanding |
| `unavailable` | 0 | Not in stock now; remains outstanding |
| `substitution_requested` | 0 | Request recorded for the prescriber; never substituted automatically |

Per-event aggregate (`Dispensing.status`): `dispensed` if every line in the event is `dispensed` and the prescription is
complete; `partial` if any quantity was supplied but something remains; `unavailable` if nothing was supplied and at least
one line is unavailable; `substitution_requested` if nothing was supplied and a substitution was requested.

Quantity invariant (per prescription item): `Σ quantity_dispensed over all Dispensing events ≤ PrescriptionItem.quantity`.

## 3. Invoice (`PaymentStatus`)

```text
 (none) ──generate_invoice()──▶ pending ──record_payment(partial)──▶ partially_paid ──record_payment(rest)──▶ paid
                                  │                                        │
                                  │                                        └─ record_payment(full rest) ─▶ paid
                                  └──cancel_invoice()──▶ cancelled   (only when amount_paid = 0)
```

| Transition | Guard |
|---|---|
| create → pending | dispensing event at this pharmacy, ≥1 unit dispensed, no invoice for that dispensing yet |
| pending → partially_paid | 0 < amount < outstanding |
| pending/partially_paid → paid | amount = outstanding |
| pending → cancelled | amount_paid = 0, reason given |
| overpayment, negative/zero amount, payment on cancelled/paid | refused |

Billing never changes the prescription status (D16). The patient sees "Billed" derived from invoices.
