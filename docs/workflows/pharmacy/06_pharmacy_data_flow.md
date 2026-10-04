# 06 — Pharmacy Data Flow

```text
Doctor (EXISTING)
  ↓  services/prescription_service.issue → send_to_pharmacy(rx, pharmacy_id)
  ↓    Prescription.pharmacy_id = HealthPlus · status = "sent" · sent_at
  ↓    activity_service.record(event="prescription_sent", category="prescriptions")  → TimelineEvent + AuditLog
Pharmacy assignment
  ↓  Prescription.pharmacy_id is the ONLY routing key (no queue table)
Pharmacy queue (EXISTING read)
  ↓  pharmacy_service.list_prescriptions(actor, AWAITING=[sent] | READY=[verified, partially_dispensed])
  ↓    WHERE pharmacy_id = actor.organization.id AND status NOT IN (draft, issued)
  ↓    record_service.prescription_to_out(rx, include_reason=False, include_invoice=True)
Verification (TO IMPLEMENT)
  ↓  pharmacy_service.verify / reject
  ↓    UPDATE Prescription(status, verified_at, verified_by | status_reason)
  ↓    activity_service.record(event="prescription_verified"|"prescription_rejected", category="prescriptions",
  ↓                            source_type="organization", organization_id=pharmacy)              (A1)
Dispensing (TO IMPLEMENT)
  ↓  pharmacy_service.record_dispensing
  ↓    INSERT Dispensing(prescription_id, pharmacist_id, organization_id, status, items_dispensed[], substitutions, notes)
  ↓    UPDATE Prescription.status (partially_dispensed | dispensed | unchanged)
  ↓    activity_service.record(event="dispensing", category="prescriptions", resource_type="dispensings", ...)
Invoice (TO IMPLEMENT)
  ↓  pharmacy_service.generate_invoice / record_payment / cancel_invoice
  ↓    INSERT/UPDATE Invoice(items[], total, amount_paid, payment_status)
  ↓    activity_service.record(event="invoice_issued"|"payment_recorded"|"invoice_cancelled", category="billing",
  ↓                            resource_type="invoices", ...)
Patient timeline (EXISTING read)
  ↓  record_service.own_record → _query_timeline (all categories incl. billing for self)
  ↓  views/patient/prescriptions.py plain status + tracker; Medical Timeline "Pharmacy" filter
Doctor timeline (EXISTING read)
  ↓  record_service.get_authorized_record (consent: prescriptions) → pharmacy events in category "prescriptions"
  ↓  billing events (category "billing") never visible to doctors (D8)
```

## Models

| Model | Key fields used by the pharmacy | Change needed |
|---|---|---|
| `Prescription` | `pharmacy_id`, `status`, `status_reason`, `sent_at`, items | add `verified_at`, `verified_by` (D7) |
| `PrescriptionItem` | `id`, `drug_name`, `strength`, `quantity`, ... | none |
| `Dispensing` | `prescription_id`, `pharmacist_id`, `organization_id`, `dispensed_at`, `status`, `items_dispensed` JSON, `substitutions`, `notes` | JSON line gains `item_id`, `status`, `note` (D6) — no column change |
| `Invoice` | `invoice_number`, `prescription_id`, `dispensing_id`, `patient_id`, `organization_id`, `created_by`, `items` JSON, `total`, `amount_paid`, `currency`, `payment_status` | none; number format `INV-{yyyy}-{rx:05d}-{n}` for new invoices (seed keeps `INV-{yyyy}-{rx:05d}`) |
| `TimelineEvent` | `source_type="organization"`, `organization_id` = pharmacy | none |
| `AuditLog` | `actor_type="pharmacist"`, `provider_id` null | none |
| `EventType` | add `payment_recorded`, `invoice_cancelled` (A2) | enum only |

## DTOs

`PrescriptionOut` (EXISTING) already carries `dispensings` (`DispensingOut`: pharmacist, pharmacy, time, status, `items`
JSON lines, `substitutions`, `notes`) and the latest `invoice`. TO IMPLEMENT for D13: add `invoices: list[InvoiceOut]`
(keep `invoice` = latest for backward compatibility) and add `dispensing_id` to `InvoiceOut`.

## Doctor-side display (read-only) — needs approval because it touches the Doctor workflow

`views/doctor/prescription_detail.py` shows the lifecycle tracker and "Sent to …" but not dispensing lines, rejection
reasons or substitution requests, and its caption says "(Phase 3)". To meet [09](09_pharmacy_patient_doctor_visibility.md),
add a read-only "Pharmacy updates" section (status reason, dispensing events with quantities, substitution requests) and
relabel the caption (D11). No billing (D8). No change to Doctor actions.

## Transactions

Each action is one `get_session()` transaction: state change + timeline event + audit row commit together or not at all.
Quantities are recomputed from all `Dispensing` rows inside the transaction before inserting a new one.
