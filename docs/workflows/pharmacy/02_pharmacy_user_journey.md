# 02 — Pharmacist User Journey

Persona: **Sana Iqbal**, Pharmacist in charge, **HealthPlus Pharmacy**. For each step: **Screen** · **Action** ·
**Service** · **Database change** · **Status change** · **Audit**. All writes also append a `TimelineEvent`
(`source_type="organization"`, `organization_id` = pharmacy, `actor_id` = pharmacist) via `activity_service.record` (A1).
Audit uses `RECORD_UPDATED` / `RECORD_CREATED` with `details.event`; see [07_pharmacy_audit_events.md](07_pharmacy_audit_events.md).

### 1. Pharmacy dashboard — EXISTING
- **Screen:** `views/pharmacy/dashboard.py` — greeting, minimum-necessary note, quick actions, KPIs (Awaiting verification, Ready to dispense, Dispensed today, Pending), prescription queue, recently dispensed.
- **Service:** `pharmacy_service.queue_overview`, `list_prescriptions`. **DB/Status/Audit:** none.

### 2. Pending verification — EXISTING (read)
- **Screen:** `views/pharmacy/pending.py` tabs "Awaiting verification (n)" / "Ready to dispense (n)" with master–detail.
- **Service:** `list_prescriptions(statuses=AWAITING|READY)`. **DB/Status/Audit:** none.

### 3. Open prescription — EXISTING (read); access audit TO IMPLEMENT (recommended)
- **Screen:** `ui/workflows.pharmacy_detail`: patient name/age/sex, **allergies**, medicines table (strength, dosage, route, frequency, duration, quantity, instructions), prescriber, prescribing organization, dispensing pharmacy, verification checklist, billing.
- **Service:** `get_prescription` (TO IMPLEMENT; must check `rx.pharmacy_id == actor org`).
- **DB/Status:** none. **Audit (recommended):** `RECORD_ACCESSED`, resource_type `pharmacy_prescription`, provider_id null — visible to the patient as "opened by HealthPlus Pharmacy".

### 4. Verify — TO IMPLEMENT
- **Screen:** checklist (Patient identity · Allergy cross-check · Dose, frequency and duration · Prescriber and organization) — all four must be ticked → **Verify prescription** → confirm.
- **Service:** `verify(rx_id)`; guards: routed to this pharmacy, status `sent`.
- **DB:** `Prescription.status="verified"`, `verified_at`, `verified_by` (D7).
- **Status:** `sent → verified`.
- **Audit:** `RECORD_UPDATED`, event `prescription_verified`, summary "{medicines} verified by the pharmacist".

### 5. Reject / unable to verify — TO IMPLEMENT
- **Screen:** **Reject with reason** → dialog with required reason (e.g. "Dose exceeds maximum", "Prescription unclear", "Allergy conflict — contact prescriber").
- **Service:** `reject(rx_id, reason)`; guards: routed here, status `sent`, reason 5–500 chars.
- **DB:** `status="rejected"`, `status_reason=reason`.
- **Status:** `sent → rejected` (terminal, D9).
- **Audit:** `RECORD_UPDATED`, event `prescription_rejected`, `details.reason` (short, clinical-free wording recommended).

### 6. Dispensing (full) — TO IMPLEMENT
- **Screen:** **Record dispensing** → form with one row per medicine: quantity prescribed, already dispensed, outstanding, *quantity now* (default = outstanding), line status.
- **Service:** `record_dispensing(rx_id, lines=[{item_id, quantity, status="dispensed"}])`; guards: status ∈ {`verified`, `partially_dispensed`}; cumulative ≤ prescribed.
- **DB:** `Dispensing(status="dispensed", items_dispensed=[{drug_name, item_id, quantity_prescribed, quantity_dispensed, status}])`; prescription status recomputed.
- **Status:** → `dispensed` when every medicine's cumulative quantity = prescribed.
- **Audit:** `RECORD_CREATED`, event `dispensing`, summary "Paracetamol ×20, Cetirizine ×5 dispensed".

### 7. Partial dispensing — TO IMPLEMENT
- **Screen:** same form, quantity now < outstanding (e.g. 10 of 20), line status `partial`.
- **DB:** `Dispensing(status="partial")`.
- **Status:** `verified → partially_dispensed` (or stays `partially_dispensed`); a later dispensing completes it → `dispensed`.
- **Audit:** `RECORD_CREATED`, event `dispensing`, `details.dispensing_status="partial"`.

### 8. Medicine unavailable — TO IMPLEMENT
- **Screen:** line status **Unavailable** (quantity 0) with optional note.
- **DB:** line `status="unavailable"`; if no line dispensed anything → `Dispensing(status="unavailable")`.
- **Status:** unchanged if nothing dispensed now; otherwise as computed (partial). The medicine remains outstanding.
- **Audit:** `RECORD_CREATED`, event `dispensing`, `details.dispensing_status="unavailable"`. Patient sees "{medicine} unavailable at {pharmacy}".

### 9. Substitution request — TO IMPLEMENT (D10)
- **Screen:** line status **Request substitution** + required request text (e.g. "Brand X out of stock; generic Y 500 mg available").
- **DB:** line `status="substitution_requested"`; `Dispensing.substitutions` = request text; nothing substituted.
- **Status:** unchanged for that medicine (still outstanding).
- **Audit:** `RECORD_CREATED`, event `dispensing`, `details.dispensing_status="substitution_requested"`. Shown to the prescriber and the patient; the doctor issues a new prescription if they agree.

### 10. Complete dispensing — TO IMPLEMENT
- When all medicines are fully dispensed the prescription becomes `dispensed`; the "Generate invoice" action appears for each un-invoiced dispensing event.

### 11. Invoice — TO IMPLEMENT
- **Screen:** **Generate invoice** → lines pre-filled from the dispensing event's dispensed quantities; pharmacist enters unit price (PKR) per line (D14); total computed.
- **Service:** `generate_invoice(dispensing_id, unit_prices)`; guards: dispensing belongs to this pharmacy, ≥1 unit dispensed, no invoice yet for this dispensing, prices > 0.
- **DB:** `Invoice(invoice_number, prescription_id, dispensing_id, patient_id, organization_id, created_by, items, total, amount_paid=0, payment_status="pending")`.
- **Status:** prescription status unchanged (D16). Invoice `pending`.
- **Audit:** `RECORD_CREATED`, event `invoice_issued`, category `billing`, summary "Invoice INV-… · PKR …".

### 12. Payment status — TO IMPLEMENT
- **Screen:** Billing → invoice row → **Record payment** (amount) or **Cancel invoice** (reason; only if unpaid).
- **Service:** `record_payment(invoice_id, amount)` / `cancel_invoice(invoice_id, reason)`.
- **DB:** `amount_paid += amount`; `payment_status` = `partially_paid` (0 < paid < total) or `paid` (paid = total); or `cancelled`.
- **Audit:** `RECORD_UPDATED`, event `payment_recorded` (NEW `EventType`, A2) or `invoice_cancelled` (NEW), category `billing`, `details.amount`, `details.payment_status`.
