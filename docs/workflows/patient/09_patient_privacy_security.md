# 09 — Patient Privacy & Security

## Principles and where they are enforced

| Principle | Enforcement | Status |
|---|---|---|
| The patient controls access to their record | Only `consent_service.grant/revoke` (patient actor) create or end access | EXISTING |
| Explicit consent | No consent → `authorize` denies every doctor | EXISTING |
| Provider-specific | Consent keyed by `provider_id` | EXISTING |
| Organization-specific | Consent keyed by `organization_id`; doctor acts in one organization context | EXISTING |
| Selective sharing | `AccessDecision.can(category)` filters every query in `record_service` | EXISTING |
| All-record warning | UI warning + service requires `confirm_all=True` | EXISTING |
| Revocation | `status=revoked`; re-checked on every request | EXISTING |
| Expiration | `effective_status` derives `expired` at check time | EXISTING |
| Auditability | `AuditLog` for consent, access, denial, AI, record creation | EXISTING (+ patient events TO IMPLEMENT) |
| Data minimization | Directory search returns identity only; pharmacies get prescription data only; audit details hold no record content | EXISTING |
| No unauthorized access | Single read path (`record_service`); UI never queries models | EXISTING |
| AI cannot bypass consent | Copilot reads only through a consent-bound handle; doctor-only; re-checked per call | EXISTING |
| Pharmacy cannot access unrelated records | `authorize` denies non-doctors; `pharmacy_service` filters by `pharmacy_id` | EXISTING |
| Patient-provided ≠ clinician-provided | Separate tables/sources + labelled UI | EXISTING display; writes TO IMPLEMENT |
| Internal clinician notes never reach the patient | Filters in service layer | EXISTING |

## Attack / misuse scenarios and expected responses

| # | Scenario | Expected response | Status |
|---|---|---|---|
| 1 | Doctor with consent at South City opens the patient while working at Clifton Medical Centre | Locked view; `require` → `ACCESS_DENIED` | EXISTING (tested) |
| 2 | Another doctor at the same organization tries to read the record | Denied (consent is per provider) | EXISTING (tested) |
| 3 | Doctor requests a category not in scope (e.g. lab reports) | That category is empty in the record; direct `require(..., "lab_reports")` → `ACCESS_DENIED` | EXISTING (tested) |
| 4 | Doctor keeps the page open after revocation | Next rerun re-authorizes → locked; no cached data | EXISTING |
| 5 | Doctor runs the AI Copilot after revocation | `AccessDenied`; no agent runs; previous summary not shown | EXISTING (tested) |
| 6 | Patient tries to revoke someone else's consent (forged id) | `AccessDenied("You can only revoke consents on your own record")` | EXISTING (tested) |
| 7 | Crafted call grants "all records" without confirmation | `ConsentError` | EXISTING (tested) |
| 8 | Patient grants consent for a doctor at an organization where they don't work | `ConsentError` | EXISTING (tested) |
| 9 | Patient reads another patient's record | `authorize` denies | EXISTING (tested) |
| 10 | Patient tries to edit a clinician note / prescription / lab result | No write path; services require doctor/lab roles | EXISTING (tests TO IMPLEMENT) |
| 11 | Patient uploads an executable or huge file | Rejected: type allow-list, 10 MB | TO IMPLEMENT (reuse rules) |
| 12 | Patient-entered text contains HTML/script | Escaped on render (`esc()` everywhere in `ui/components.py`) | Must hold for new views |
| 13 | Patient adds an allergy that contradicts the clinician list | Stored separately as patient-provided; never overwrites; AI may flag the documentation discrepancy for the doctor | Partly EXISTING (rule-based flag) |
| 14 | Pharmacy tries to read the patient's timeline | `authorize` denies non-doctors | EXISTING (tested) |
| 15 | Pharmacy sees prescriptions not routed to it | `list_prescriptions` filters by `pharmacy_id` | EXISTING (tested) |
| 16 | Doctor sees billing via "all records" | Billing never shareable | EXISTING (tested) |
| 17 | Patient sees internal note via timeline / history / notes API | Filtered in service | EXISTING (tested) |
| 18 | Uploaded file path leaks via UI or audit | Audit stores no path; download only via `document_service.read_file` with authorization | Must hold for new code |
| 19 | Demo session switching (role switch) leaks previous user's selections | `_clear_selections` on role/user change | EXISTING |
| 20 | Gemini API key exposure | Session-only BYOK, never stored or logged | EXISTING (doctor-side) |

## Known limitations (documented, accepted for the hackathon)

- Authentication is simulated (DEMO MODE); anyone with the app can act as any persona.
- Uploaded files are stored unencrypted on local disk (`UPLOAD_DIR`).
- Expiry is not audited (D4).
- Patient-reported allergies are hidden from doctors unless `documents` is shared — a **safety** concern addressed by D1.
