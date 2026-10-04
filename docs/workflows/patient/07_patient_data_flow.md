# 07 — Patient Data Flow

Exact modules, functions and models. Arrows are synchronous calls inside one Streamlit run; each view opens a
session with `core.db.get_session()` (commit on success, rollback on exception).

## 1. Reading the patient's own record — EXISTING

```text
Patient
  ↓  views/patient/{home,my_health,timeline,prescriptions,medications,reports,care_network}.py
  ↓  ui.shell.current_actor()                                   → Actor(role="patient", id=<user id>)
  ↓  services/record_service.own_record(session, actor)
  ↓    access_service.authorize(...)  → AccessDecision(via="self", scope_type="all", categories=all)
  ↓    _patient_out · _query_consultations (final only) · _query_notes (excludes internal)
  ↓    _query_prescriptions (excludes draft; invoices included because can("billing") for self)
  ↓    _query_medications · _query_reports (values only when published) · _query_documents
  ↓    _query_patient_entries · _query_timeline (patient_visible = true)
  ↓  core/models: Patient, Consultation, ClinicalNote, Prescription(+Item, Dispensing, Invoice),
  ↓               LabOrder(+LabResult, LabReport), Document, PatientEntry, TimelineEvent
  ↓  SQLite
  ↑  AuthorizedRecord (Pydantic DTOs in core/schemas.py) → rendered by ui/components.py & ui/sections.py
```
No audit row is written for self-access (by design).

## 2. Granting consent — EXISTING

```text
Patient
  ↓  views/patient/consent.py share_dialog()
  ↓  consent_service.search_providers(session)        → ProviderOption list (primary org first)
  ↓  consent_service.grant(session, actor, provider_id, organization_id, scope_type, categories,
  ↓                        duration, purpose, confirm_all)
  ↓    _patient_for(actor)                              → Patient (or AccessDenied)
  ↓    ProviderOrganization lookup (active membership)  → or ConsentError
  ↓    access_service.active_consent(...)               → previous? → _revoke(reason="superseded…")
  ↓    INSERT Consent (+ ConsentScope rows for "selected")
  ↓    audit_service.log(CONSENT_GRANTED, details{consent_id, scope_type, all_records, categories,
  ↓                                               duration, expires_at, purpose})
  ↓  session commit
Doctor (later, at that organization)
  ↓  access_service.authorize → active_consent → effective_status == "active" → AccessDecision(via="consent")
  ↓  record_service.get_authorized_record → filtered by decision.can(category)
  ↓  audit_service.log_record_access(RECORD_ACCESSED, de-duplicated per view)
```

## 3. Revoking consent — EXISTING

```text
Patient
  ↓  views/patient/consent.py revoke_dialog()
  ↓  consent_service.revoke(session, actor, consent_id)
  ↓    ownership check (consent.patient_id == own patient) → else AccessDenied
  ↓    _revoke: Consent.status = "revoked", revoked_at = now
  ↓    audit_service.log(CONSENT_REVOKED, details{consent_id, reason, scope_type, categories})
  ↓  commit
Doctor
  ↓  access_service.authorize → no active consent → AccessDecision(allowed=False)
  ↓  access_service.require   → AccessDenied + audit ACCESS_DENIED
AI Clinical Copilot (doctor-triggered)
  ↓  copilot_service._require_doctor → access_service.require → AccessDenied
  ↓  agents.copilot never runs; Record Retrieval Agent never receives data
```

## 4. Patient-created entry — TO IMPLEMENT

```text
Patient
  ↓  dialog on Home / My Health
  ↓  services/patient_entry_service.add_entry(session, actor, entry_type, title, details)   (NEW module)
  ↓    access_service.require_self(own patient id)
  ↓    validate (04_patient_permissions.md)
  ↓    INSERT PatientEntry
  ↓    activity_service.record(actor, patient_id, event="patient_entry", category="documents",
  ↓                            resource_type="patient_entries", resource_id, summary=title,
  ↓                            source_type="patient")                     ← requires A1
  ↓      → TimelineEvent(source_type="patient", organization_id=None, actor_id=<patient user>)
  ↓      → AuditLog(RECORD_CREATED, actor_type="patient", provider_id=None)
  ↓  commit → toast → entry visible
```

## 5. Patient document upload — TO IMPLEMENT

```text
Patient
  ↓  upload dialog
  ↓  document_service.upload_own(session, actor, file_name, data, doc_type, title, description)   (NEW function)
  ↓    require_self · shared validation (type/size/title) · write file to UPLOAD_DIR/patient_<id>/<uuid><ext>
  ↓    INSERT Document(source_type="patient", uploaded_by=<patient user>, organization_id=None,
  ↓                    record_category="documents")
  ↓    activity_service.record(event="document_added", source_type="patient", ...)     ← requires A1
  ↓  commit
```
If the file write succeeds but the DB transaction fails, the orphan file is acceptable for the MVP (document it); the
DB row is the source of truth.

## 6. Patient sends an issued prescription (D5) — TO IMPLEMENT

```text
Patient → views/patient/prescriptions.py → prescription_service.send_to_pharmacy(session, actor, rx_id, pharmacy_id)
  ↓  NEW patient branch: own prescription (rx.patient.user_id == actor.id), status == "issued",
  ↓  target Organization.org_type == "pharmacy"
  ↓  rx.pharmacy = pharmacy; status = "sent"; sent_at = now
  ↓  activity_service.record(event="prescription_sent", source_type="patient", organization_id=pharmacy) ← A1
  ↓  commit → pharmacy queue (pharmacy_service.list_prescriptions) shows it
```
The existing doctor branch (prescriber, at prescribing organization, with active consent) must remain unchanged.

## Models touched by the Patient workflow

| Model | Read | Written by patient actions |
|---|---|---|
| `Patient` | ✅ | ❌ |
| `Consent`, `ConsentScope` | ✅ | ✅ (grant, revoke) — EXISTING |
| `PatientEntry` | ✅ | ✅ TO IMPLEMENT |
| `Document` | ✅ | ✅ TO IMPLEMENT (patient source) |
| `Prescription` | ✅ | ✅ only `issued → sent` (D5) |
| `TimelineEvent` | ✅ | ✅ via `activity_service` (source `patient`) |
| `AuditLog` | ✅ (filtered) | ✅ via services only |
| everything else | ✅ (per rules) | ❌ |
