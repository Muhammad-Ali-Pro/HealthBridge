# 11 — Patient Acceptance Criteria

Format: **Given / When / Then**. Tags: **[E]** already satisfied by existing code (must not regress) ·
**[T]** to implement · **[D]** depends on a decision (default assumed).

## Dashboard (Home)
- **AC-P1 [E]** Given Ahmed is signed in, when he opens Home, then he sees health summary, recent activity (newest first, each with a source), current medications, latest prescription with progress, latest published lab report, active consents and his care network.
- **AC-P2 [T]** Given Ahmed is on Home, when he clicks *Add a health note*, *Add allergy or information* or *Upload a document*, then a working dialog opens (no "coming in phase" placeholder remains).

## My Health
- **AC-P3 [E]** Given a final consultation with additional notes, when Ahmed opens My Health, then *Last visit* shows the additional notes labelled "Additional notes" and never any internal clinician note.
- **AC-P4 [E]** Given more than one visit, when he opens *Earlier visits*, then each earlier visit is listed with the same rules.

## Timeline
- **AC-P5 [E]** Given records from several organizations, when Ahmed opens Medical Timeline, then every event shows its source (patient / organization + clinician / laboratory / pharmacy) and filters All · Consultations · Prescriptions · Labs · Hospital · Pharmacy · Documents work with counts.
- **AC-P6 [E]** Given an internal clinician note exists, then it never appears on the patient timeline, in history, or in any patient API result.
- **AC-P7 [T]** Given Ahmed adds an entry or uploads a document, then it appears on the timeline as "Added by you" with `source_type = patient`.

## Prescriptions
- **AC-P8 [E]** Given prescriptions in different states, when Ahmed opens Prescriptions, then each shows the plain-language status and the tracker Prescribed → Sent → Verified → Dispensed → Billed; drafts never appear.
- **AC-P9 [T][D5]** Given an `issued` prescription, when Ahmed selects HealthPlus Pharmacy and confirms *Send Prescription*, then the status becomes `sent`, `pharmacy = HealthPlus Pharmacy`, the pharmacy queue shows it, and a `RECORD_UPDATED / prescription_sent` audit row exists with actor_type `patient`.
- **AC-P10 [T]** Given a prescription that is not `issued`, or that belongs to another patient, when a send is attempted, then it is refused and nothing changes.

## Medications · Labs
- **AC-P11 [E]** Medications shows current vs previous medicines with prescriber, organization, start and end.
- **AC-P12 [E]** Lab Reports shows published values only; unpublished orders show "Being processed" without values.

## Documents
- **AC-P13 [T][D3]** Given documents from providers, laboratories and Ahmed, when he opens Documents, then each shows title, type, date and source, and can be filtered by source.
- **AC-P14 [T]** Given a valid PDF ≤10 MB with a title, when Ahmed uploads it, then a `Document(source_type=patient, organization_id=null)` exists, the file is stored, and `RECORD_CREATED / document_added` is audited.
- **AC-P15 [T]** Given an `.exe`, an empty file, a file >10 MB or a missing title, when he uploads, then an inline error is shown and nothing is stored.

## Patient-created records
- **AC-P16 [T]** Given Ahmed saves a note, then a `PatientEntry(entry_type=note)` exists, it is shown with the *Patient-provided* badge, and the audit row has `provider_id = null`.
- **AC-P17 [T][D2]** Given Ahmed adds allergy "Ibuprofen", then a `PatientEntry(entry_type=allergy)` exists and `Patient.allergies` is unchanged.
- **AC-P18 [T][D1]** Given Dr. Arif has any active consent, when he opens Ahmed, then patient-reported allergies are visible labelled "patient-provided, not verified".

## Care Network
- **AC-P19 [E]** Care Network lists every doctor and organization connected to Ahmed's timeline or consents, with what each doctor can see now.

## Consent — grant, selective sharing, share all, warning
- **AC-P20 [E]** When Ahmed opens the share dialog, then the default option is *Dr. Arif Hassan — South City Hospital*, and other organizations remain selectable.
- **AC-P21 [E]** Given he selects Consultations, Prescriptions, Current medications and confirms, then a `Consent(scope_type=selected)` with exactly those categories exists for Dr. Arif **at South City Hospital**, and `CONSENT_GRANTED` is audited with those categories.
- **AC-P22 [E]** Given *Share selected* with no category, then the confirm button is disabled and the service refuses.
- **AC-P23 [E]** Given he chooses *Share all*, then the "Full medical record access" warning is shown and the button reads "Confirm & Share All Records"; the service refuses without `confirm_all`.
- **AC-P24 [E]** Given an all-records consent, then the doctor sees all categories except billing, and the audit row has `all_records = true`.
- **AC-P25 [E]** Given an active consent for the same doctor + organization, when he grants again, then the old consent is revoked ("superseded") and a new one is active.

## Doctor access after consent
- **AC-P26 [E]** Given the consent in AC-P21, when Dr. Arif works at South City Hospital, then he sees consultations (clinic), prescriptions and medications, and not lab reports, hospital records, imaging, documents or billing.
- **AC-P27 [E]** Given the same consent, when Dr. Arif works at Clifton Medical Centre, then Ahmed is "ACCESS RESTRICTED" and the attempt is audited as `ACCESS_DENIED`.
- **AC-P28 [E]** Given the same consent, when Dr. Arif runs the AI Copilot, then only consented categories reach the agents.

## Revocation
- **AC-P29 [E]** Given an active consent, when Ahmed revokes it, then status is `revoked`, `revoked_at` is set, `CONSENT_REVOKED` is audited and no record is deleted.
- **AC-P30 [E]** Given a revoked consent, when Dr. Arif opens Ahmed or runs the AI Copilot, then access is denied, no agent runs and the previous AI summary is not shown.
- **AC-P31 [T]** Given the revoke dialog in the browser, when Ahmed confirms, then the consent leaves People with access and appears in Past access in the same session (UI test).

## Expiration
- **AC-P32 [E]** Given a 24-hour or 7-day consent past its `expires_at`, then it is `expired`, appears under Past access, and the doctor is denied.
- **AC-P33 [E]** Given a one-consultation consent, when that doctor records a consultation at that organization and 2 hours pass, then it is `expired`.

## Privacy
- **AC-P34 [E]** Ahmed can never read another patient's record.
- **AC-P35 [T]** Ahmed cannot create/modify consultations, notes, prescriptions, lab results, dispensing, invoices, AI rows or audit rows (service calls raise `AccessDenied`).
- **AC-P36 [E]** Pharmacies and laboratories cannot read Ahmed's longitudinal record.

## Audit
- **AC-P37 [E]** History shows consent granted/revoked/replaced, record opened, access blocked and AI summary generated, with doctor, organization and time.
- **AC-P38 [T]** History "All record activity" shows Ahmed's own notes, allergies and uploads with "You" as the source.
- **AC-P39 [E]** No audit row contains file contents, storage paths, AI prompts/outputs or API keys.
