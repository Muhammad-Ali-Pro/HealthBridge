# HealthBridge

**One patient. One longitudinal health timeline. Multiple connected healthcare providers.**

HealthBridge connects clinics, hospitals, laboratories and pharmacies around a single patient-owned
timeline. Patients decide which doctor — at which organization — can see which records, for how long.
Hackathon MVP: Streamlit + SQLite + SQLAlchemy + Pydantic + LangGraph + Google Gemini (bring your own key).

> **Synthetic data only.** AI organises, summarises and flags *possible* discrepancies.
> It never diagnoses, makes treatment decisions or changes medication. Agents may only write
> `AIFlag` and `AISummary` records.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env          # optional: developer GEMINI_API_KEY (testers can enter their own in the app)
```

**Windows Smart App Control note:** if importing SQLAlchemy fails with
`DLL load failed ... An Application Control policy has blocked this file`, reinstall it as pure Python:

```powershell
$env:DISABLE_SQLALCHEMY_CEXT = "1"
.\.venv\Scripts\python.exe -m pip install --force-reinstall --no-deps --no-binary sqlalchemy sqlalchemy
```

## Run and test

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py      # http://localhost:8501
.\.venv\Scripts\python.exe -m data.seed                 # reset to the demo data
.\.venv\Scripts\python.exe -m pytest -q
```

The app opens on the **landing page** ("One patient. One connected health journey.") with four demo
personas: Patient **Ahmed Khan**, Doctor **Dr. Arif** (South City Hospital & Clifton Medical Centre),
**HealthPlus Pharmacy** and **HealthLab Diagnostics**. Use the profile menu to switch role, the **Working at** selector in the top bar to switch the
organization a doctor is working at, reset demo data, or exit to the landing page.

The SQLite DB is created and seeded on first load. A DB from an older schema version is rebuilt
automatically (demo data only — there are no migrations).

Deep links skip the landing page: `/?as=patient`, `/consent?as=patient`, `/patients?as=doctor`,
`/billing?as=pharmacist`, `/pending?as=lab`.

**Demo starting point:** Ahmed has *not* yet shared his records with Dr. Arif at South City Hospital —
grant it live from Consent & Access, then switch to the doctor.

## Doctor workflow (Phase 2)

Find patient (name / HB-ID / phone) → consent check for *this doctor at this organization* → patient
clinical workspace (Overview · Consultations · Prescriptions · Medical Timeline · Reports & Documents ·
AI Clinical Copilot).

- **Consultations:** editable visit date/time (up to 30 days back), assessment, plan, *Additional notes*,
  and an optional **internal clinician note**. Internal notes are filtered out in the service layer
  for the patient (record, timeline, history), not just hidden in the UI. Use **Save & create prescription**
  to open a prescription already linked to the new consultation.
- **Prescriptions:** draft → issue (with confirmation) → choose a demo pharmacy → **Send prescription**
  → status `sent` ("Sent to HealthPlus Pharmacy"). Dispensing and billing happen on the pharmacy side
  (Phase 3).
- **Working at** switcher in the top bar (doctors with more than one organization): switching re-checks
  consent right away. The same patient can be open at one organization and locked at the other.
- **Dashboard:** KPIs (today's consultations, total patients, pending follow-ups, prescriptions issued,
  AI review items), today's consultations, recent patients with their access status here, and drafts.
- **Medical timeline:** filters (All · Consultations · Prescriptions · Labs · Hospital · Pharmacy ·
  Documents). Only filters for categories the patient shared are offered; the rest are shown as not shared.

**HealthBridge Clinical Copilot** (the AI Clinical Copilot tab, or Doctor → AI Insights). Each agent
has one narrow job:

Doctor → consent check → **Record Retrieval Agent** → **Clinical Summary Agent** →
**Safety / Consistency Agent** → doctor review

- **Record Retrieval Agent:** reads only through `record_service.get_authorized_record`; it never
  queries the database directly.
- **Clinical Summary Agent:** builds the history, medications, prescriptions, important changes and
  follow-up. Every item cites a record ID, and unsupported statements are removed.
- **Safety / Consistency Agent:** flags possible discrepancies (allergy conflicts, duplicate or
  overlapping prescriptions, missing documentation, date inconsistencies). It never recommends treatment.

The doctor can **Accept** or **Dismiss** each flag, and use **View source** to see the record,
organization, author and timestamp. Sources are re-read through consent. AI writes only `AISummary` /
`AIFlag` rows, never clinical records.

## AI provider — Google Gemini, bring your own key

| | |
|---|---|
| Provider | Google Gemini API, via the official `google-genai` SDK (the only AI dependency) |
| Default model | `gemini-3.8-flash`, configurable. Also offered: `gemini-3.5-flash`, `gemini-3.5-flash-lite` |
| Why this model | On 2026-10-04, Google's [pricing page](https://ai.google.dev/gemini-api/docs/pricing) listed it as *free of charge* on the Gemini API free tier, and the [models page](https://ai.google.dev/gemini-api/docs/models) listed it as the current stable Flash model. It is fast enough for an interactive demo and supports JSON-schema output. Free-tier rate limits depend on your account; check them in [AI Studio](https://aistudio.google.com/rate-limit). |
| Structured output | `response_mime_type="application/json"` + `response_json_schema` built from the Pydantic models, then Pydantic validation |

**Get a key:** go to [Google AI Studio](https://aistudio.google.com/apikey), sign in, and choose
**Get API key → Create API key**. It is free and needs no billing.

**Use it in the demo (BYOK):** go to Doctor → patient → **AI Clinical Copilot** tab (or AI Insights) →
**Configure AI**. Choose Google Gemini and a model, paste the key, then click **Connect & Test**. One
small request, with no patient data, checks the key. The panel then shows *✓ AI provider connected ·
Active model*. **Clear API Key** removes it.

**Local developer configuration** (optional) in `.env`. A key entered in the UI takes precedence for that
browser session. `GEMINI_API_KEY` in `.streamlit/secrets.toml` is also read.

```ini
AI_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.8-flash
```

**Key handling:**
- The key is held only in that browser session's `st.session_state`, in server memory, for one session.
- It is never written to SQLite, logs, audit entries, patient records or URLs, and never shared with another session.
- Only its last four characters are ever displayed.
- Provider errors are reduced to safe messages, so raw responses that could echo request details are never shown.
- `.env`, `.env.*` and `.streamlit/secrets.toml` are git-ignored.

**No key, quota exhausted, or model unavailable:** HealthBridge keeps working. The Copilot shows
*AI is not connected* and a **Configure AI** button. You can still run a deterministic analysis. It is
always labelled **"Demo AI response — live model unavailable"** and is never presented as model output.

**Adding OpenAI later:**
- Agents depend only on `agents/providers.AIProvider` (`generate_structured`, `test_connection`,
  `get_model_name`). Only `agents/providers.py` imports a vendor SDK.
- To add OpenAI, write an `OpenAIProvider(AIProvider)` subclass and register it in `PROVIDERS`.
- Consent logic, the LangGraph workflow, the agents, the UI and the Pydantic schemas stay unchanged.

## Core model

```
Patient ──< Consent >── Provider (User) ──< ProviderOrganization >── Organization
               │                                                    (clinic | hospital |
               └──< ConsentScope (record category)                   laboratory | pharmacy)

Clinical records: Consultation, ClinicalNote, Prescription(+Items), Dispensing, Invoice,
LabOrder → LabResult → LabReport, Document, PatientEntry (patient-provided), TimelineEvent.
Each keeps patient + provider (where applicable) + organization + timestamp + record category
+ source (patient / provider / organization). Billing is never shareable with doctors.
```

**Access rules (enforced in `services/access_service.py`, not the UI):**

* Patients always see their own full record.
* A doctor sees a patient's record only with an active consent for **that doctor at that organization**
  (not revoked, not expired), and only the consented categories: consultations, prescriptions,
  current medications, laboratory reports, hospital records, imaging reports.
* Pharmacies see only prescriptions routed to them (no diagnoses or wider record).
  Laboratories see only test orders routed to them.
* Every consent grant/revoke, every consent-based record access, and every denied attempt is audited.

## Demo identities — DEMO MODE, authentication simulated

| Role | User | Organization(s) |
|---|---|---|
| Patient | **Ahmed Khan** (+ 6 more) | — |
| Doctor | **Dr. Ayesha Malik** | Clifton Family Clinic (primary), City Hospital |
| Doctor | Dr. Imran Qureshi | Gulshan Medical Centre, City Hospital |
| Doctor | **Dr. Arif Hassan** | South City Hospital (primary), Clifton Medical Centre |
| Pharmacist | Sana Iqbal / Hamza Sheikh | HealthPlus Pharmacy / CarePoint Pharmacy |
| Laboratory | Nadia Farooq | HealthLab Diagnostics |

Ahmed's consents: Dr. Ayesha @ Clifton Family Clinic — all records; Dr. Ayesha @ City Hospital and
Dr. Arif @ Clifton Medical Centre — one consultation (expired); Dr. Imran @ Gulshan — revoked;
Dr. Arif @ South City Hospital — **none yet** (granted live in the demo).

## Layout

```
app.py              router + app shell
ui/landing.py       public front page + demo role selection
views/patient/      Home, My Health, Medical Timeline, Prescriptions, Medications, Lab Reports,
                    Care Network, Consent & Access
views/doctor/       Dashboard, Patients, Consultations, Prescriptions, Medical Timeline,
                    Reports & Documents, My Organizations, AI Insights
views/pharmacy/     Dashboard, Prescriptions, Pending Verification, Dispensing, Billing, Patients
views/lab/          Dashboard, Test Orders, Pending Reports, Published Reports, Patients
core/               config, db, ORM models, Pydantic schemas
services/           access control, consent, records, provider/pharmacy/lab views, audit
data/               seed script, synthetic drug catalog
ui/                 theme, components, sections, workflows, shell
tests/
```
