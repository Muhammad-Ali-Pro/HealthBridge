# 10 — Patient Demo Scenario (hackathon script)

**Story:** "One patient. One connected health journey." Ahmed Khan controls exactly which doctor, at which organization,
sees which records — and can take that access back.

**Before the demo:** reset demo data (profile menu → *Reset demo data*, or `python -m data.seed`). No Gemini key is needed.
Duration ≈ 6–7 minutes. Items marked **(TO IMPLEMENT)** become live once the Patient workflow is built; until then skip them.

## Seeded facts the demo relies on (EXISTING)

| Fact | Value |
|---|---|
| Patient | Ahmed Khan · HB-000001 · 48 · male |
| Clinician-documented | Allergy *Penicillin*; condition *Type 2 diabetes* |
| Patient-provided | Note *Home glucose readings*; allergy *Shellfish (self-reported)* |
| Organizations on his timeline | Clifton Family Clinic, Clifton Medical Centre, City Hospital, HealthLab Diagnostics, HealthPlus Pharmacy |
| Consents | Dr. Ayesha Malik @ Clifton Family Clinic — active, all records; Dr. Ayesha @ City Hospital — expired; Dr. Arif Hassan @ Clifton Medical Centre — expired; Dr. Imran Qureshi @ Gulshan Medical Centre — revoked |
| Dr. Arif @ South City Hospital | **No consent** at the start (locked) |

## Script

| # | Presenter does | Audience sees | Talking point |
|---|---|---|---|
| 1 | Landing → **Continue as Ahmed Khan** | Home: "Hello, Ahmed", ownership message | Patient-first; demo sign-in is simulated |
| 2 | Scroll Home | Health summary, recent activity with sources, current medicines, latest lab report, active consents | One summary across many providers |
| 3 | **Medical Timeline** | Events from Clifton Family Clinic, Clifton Medical Centre, City Hospital, HealthLab Diagnostics, HealthPlus Pharmacy, and "Added by you" | Every entry keeps its provenance |
| 4 | Click filters *Labs* then *Pharmacy* | Lab report published; verified / dispensed / invoice | One longitudinal record |
| 5 | **My Health → Add a health note** (TO IMPLEMENT) "Blood pressure at home 130/85" | Note under "Information I added" with *Patient-provided* badge; timeline "Added by you" | Patient-provided ≠ clinician-verified |
| 6 | **Add allergy or information → Allergy** "Ibuprofen — rash" (TO IMPLEMENT) | New patient-reported allergy, clinician list (Penicillin) unchanged | Never overwrites the clinical record |
| 7 | **Upload a document** "BP diary.pdf" (TO IMPLEMENT) | Document with *Added by you* source | Patient can contribute documents |
| 8 | **Care Network** | Doctors and organizations; what each doctor can see now | Who is in my care |
| 9 | **Consent & Access** | Active: Dr. Ayesha (all records). Past: expired/revoked consents | Consent is per doctor **and** organization |
| 10 | **Share Records with a Doctor** | Dialog defaults to *Dr. Arif Hassan — South City Hospital*; "Only Dr. Arif at South City Hospital will get access…" | Same doctor elsewhere ≠ access here |
| 11 | Tick **Previous consultations**, **Prescriptions**, **Current medications**; leave others | Privacy summary: will see / will NOT see (labs, hospital records, imaging, documents) | Selective sharing |
| 12 | (Optional) select *Share all* to show the warning, then switch back to *selected* | "Full medical record access" warning; button "Confirm & Share All Records" | Explicit confirmation for everything |
| 13 | **Share selected records** | Success card with Consent ID; Dr. Arif appears under People with access | Audited (CONSENT_GRANTED) |
| 14 | **Home page → Continue as Dr. Arif** (Working at South City Hospital) → Patients → Ahmed | "Patient has granted you access"; consultations, prescriptions, medications visible; labs/documents/hospital records **locked** | Doctor sees only what was shared |
| 15 | (Optional) Working at → Clifton Medical Centre | Ahmed "ACCESS RESTRICTED" | Organization-specific |
| 16 | **Home page → Continue as Ahmed Khan → Consent & Access** | Dr. Arif active; **View access** shows when he opened the record | Transparency |
| 17 | **Revoke access** → confirm | Moves to Past access "Revoked …"; History shows *Consent revoked* | Patient stays in control; records not deleted |
| 18 | **Continue as Dr. Arif** → Ahmed | "ACCESS RESTRICTED"; AI Clinical Copilot unavailable | Revocation is immediate, AI included |
| 19 | **Continue as Ahmed → Consent & Access → History** | Granted · Record opened · Revoked · (Access blocked) | Full audit trail |

## Fallbacks

| Problem | Recovery |
|---|---|
| Wrong doctor/organization picked | Revoke and grant again (new consent supersedes) |
| Demo state messy | Profile menu → Reset demo data |
| Placeholders not yet implemented (steps 5–7) | Show the seeded patient-provided note/allergy instead |
