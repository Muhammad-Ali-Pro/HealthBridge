# 02 — Patient User Journey

Persona: **Ahmed Khan** (HB-000001, 48, male; clinician-documented allergy *Penicillin*, condition *Type 2 diabetes*;
self-reported allergy *Shellfish*). Each step lists: **Sees** · **Does** · **Internally** · **Data change** · **Audit**.
Audit actions are `AuditAction` values; "event" means `details.event` (`EventType`). See [08_patient_audit_events.md](08_patient_audit_events.md).

---

### 1. Enter HealthBridge — EXISTING
- **Sees:** landing page, four demo personas, DEMO MODE label.
- **Does:** "Continue as Ahmed Khan".
- **Internally:** `ui/shell.enter_as("patient")` sets `hb_role`, `hb_user_id`; `resolve_actor()` builds the `Actor`.
- **Data change:** none (session state only). **Audit:** none (simulated sign-in; self-access is not logged).

### 2. View dashboard (Home) — EXISTING
- **Sees:** greeting, ownership message, quick actions, health summary hero, recent activity, encounters,
  current medications, recent prescription, recent lab report, active consents, care network diagram.
- **Internally:** `record_service.own_record`, `care_network_service.network`, `consent_service.list_for_patient`.
- **Data change:** none. **Audit:** none (patient self-access is intentionally not logged — `test_patient_self_access_is_not_logged_as_provider_access`).

### 3. View health summary (My Health) — EXISTING
- **Sees:** current medicines, last visit (incl. *Additional notes*), earlier visits, latest results in plain
  language, "Information I added", "My documents".
- **Data change / Audit:** none.

### 4. View recent activity — EXISTING
- **Sees:** newest-first timeline on Home (6 items) and full Medical Timeline with filters
  All · Consultations · Prescriptions · Labs · Hospital · Pharmacy · Documents; every entry shows its source.
- **Internally:** `_query_timeline` with `patient_visible = true` only.
- **Data change / Audit:** none.

### 5. View consultations — EXISTING
- **Sees:** consultation list (Home "Recent healthcare encounters"), Last visit / Earlier visits on My Health with
  reason, notes, observations, assessment, diagnosis, plan, follow-up, **Additional notes**. Never internal notes, never drafts.
- **Data change / Audit:** none.

### 6. View prescriptions — EXISTING (send = TO IMPLEMENT, D5)
- **Sees:** every non-draft prescription with a plain-language status and progress tracker
  (Prescribed → Sent → Verified → Dispensed → Billed); issued-but-unsent prescriptions under "Choose a pharmacy".
- **Does (D5, TO IMPLEMENT):** choose a pharmacy → "Send Prescription" → confirm.
- **Internally:** `prescription_service.send_to_pharmacy` with a patient-actor branch (own prescription, status `issued`, target org type `pharmacy`).
- **Data change:** `Prescription.pharmacy_id`, `status=sent`, `sent_at`. Timeline event `prescription_sent` (source `patient`).
- **Audit:** `RECORD_UPDATED`, event `prescription_sent`, actor_type `patient`, organization_id = pharmacy.

### 7. View medications — EXISTING
- **Sees:** "Taking now" (derived from active prescriptions within their course) and previous medications, with prescriber and organization.

### 8. View labs — EXISTING
- **Sees:** published reports (values, reference ranges, flags in plain language) and "Being processed" for unpublished orders (no values).

### 9. View documents — EXISTING data, TO IMPLEMENT page (D3)
- **Sees:** documents from providers, organizations and himself, each with source and type.
- **Internally:** `own_record(...).documents`; file download through `document_service.read_file` (EXISTING, owner/consent-checked).

### 10. Add a personal note — TO IMPLEMENT
- **Sees:** "Add a health note" → form (title, details).
- **Internally:** new `patient_entry_service.add_entry(session, actor, entry_type="note", title, details)` →
  `access_service.require_self`; validation (title required, ≤200 chars; details ≤2000).
- **Data change:** `PatientEntry` row; `TimelineEvent(event_type="patient_entry", record_category="documents", source_type="patient", actor_id=<patient user>, organization_id=None)`.
- **Audit:** `RECORD_CREATED`, event `patient_entry`, actor_type `patient`, resource_type `patient_entries`, details `{entry_type}` (no free text beyond the title summary).

### 11. Add an allergy — TO IMPLEMENT
- **Sees:** "Add allergy or information" → type selector (Allergy / Condition / Medication I take / Other), substance, reaction (optional).
- **Internally:** same service, `entry_type="allergy"` (D2: never modifies `Patient.allergies`).
- **Data change:** `PatientEntry(entry_type="allergy")` + timeline event (source `patient`).
- **Audit:** `RECORD_CREATED`, event `patient_entry`, details `{entry_type: "allergy"}`.
- **Visibility to doctors:** D1 (recommended: shown with any active consent, labelled patient-provided).

### 12. Upload a document — TO IMPLEMENT
- **Sees:** "Upload a document" → file (PDF/PNG/JPG ≤10 MB), title, type.
- **Internally:** extend `document_service` with a patient path (`upload_own`), reusing its validation and storage;
  `require_self`.
- **Data change:** file under `UPLOAD_DIR/patient_<id>/`; `Document(source_type="patient", organization_id=None, uploaded_by=<patient user>, record_category="documents")`; timeline event `document_added` (source `patient`).
- **Audit:** `RECORD_CREATED`, event `document_added`, resource_type `documents`, details `{doc_type, title}` (never file content).

### 13. Open Care Network — EXISTING
- **Sees:** diagram + "My doctors" (with what each can currently see) + "My care organizations" (visits, tests, prescriptions).
- **Internally:** `care_network_service.network` (built from consultations, prescriptions, lab orders and consents).

### 14. See doctors / organizations — EXISTING
- Each doctor card shows organizations and consent status per organization; each organization shows its relation.

### 15. Open Consent & Access — EXISTING
- **Sees:** "Share Records with a Doctor", the per-organization rule explainer, People with access, Past access,
  History (two tabs: Consent & access; All record activity).

### 16. Grant access — EXISTING
- **Does:** "Share Records with a Doctor" → dialog (5 steps). Detailed in [05_patient_consent_workflow.md](05_patient_consent_workflow.md).

### 17. Select doctor — EXISTING
- Search by doctor or organization; options are **doctor + organization pairs**, each doctor's primary organization first
  (default for the demo: *Dr. Arif Hassan — South City Hospital*).

### 18. Select organization — EXISTING
- The organization is part of the pair; the confirmation card states "Only Dr. X at Org Y will get access — not other doctors there, and not Dr. X at another organization."

### 19. Select record categories — EXISTING
- Checkboxes: Previous consultations · Prescriptions · Current medications · Laboratory reports · Hospital records · Imaging · Documents.
- Privacy summary shows what will and will **not** be shared. Confirm is disabled until at least one category is chosen.

### 20. Share all records — EXISTING
- **Does:** "Share all my HealthBridge records".

### 21. Confirm warning — EXISTING
- **Sees:** "Full medical record access" warning. Button changes to "Confirm & Share All Records".
- **Internally:** `consent_service.grant(..., scope_type="all", confirm_all=True)`; without `confirm_all` the service raises `ConsentError`.
- **Data change:** `Consent(scope_type="all")` with no `ConsentScope` rows; any previous active consent for the same doctor+organization is revoked ("superseded").
- **Audit:** `CONSENT_GRANTED` with `details.all_records = true`, `scope_type`, `categories` (all), `duration`, `expires_at`, `purpose`, `consent_id`.

### 22. View active consent — EXISTING
- **Sees:** People with access card (doctor, organization, scope chips, granted date, expiry text, CON-id) → "View access" dialog lists when that doctor opened the record (`RECORD_ACCESSED`).

### 23. Revoke consent — EXISTING
- **Does:** "Revoke access" → dialog → "Revoke access".
- **Internally:** `consent_service.revoke` → `_revoke`.
- **Data change:** `Consent.status="revoked"`, `revoked_at`. No record is deleted.
- **Audit:** `CONSENT_REVOKED`, details `{consent_id, reason: "revoked by patient", scope_type, categories}`.

### 24. View access history — EXISTING
- **Sees:** Consent & access tab (granted, revoked, replaced, record opened, access blocked, AI summary generated) and
  All record activity tab (records created/updated, excluding drafts and internal notes).

### 25. Verify that the doctor loses access — EXISTING
- **Internally:** next request by the doctor → `access_service.authorize` finds no active consent → locked view;
  `require` logs `ACCESS_DENIED`. AI Clinical Copilot preview/generate/latest/flags all call `require` and are blocked.
- **Patient sees:** the consent under Past access ("Revoked …"); any blocked attempt appears as "Access blocked" in history.
