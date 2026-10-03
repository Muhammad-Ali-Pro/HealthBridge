# HealthBridge

**One patient. One longitudinal health timeline. Multiple connected healthcare providers.**

HealthBridge connects clinics, hospitals, laboratories and pharmacies around a single patient-owned
timeline. Patients decide which doctor — at which organization — can see which records, for how long.
Hackathon MVP: Streamlit + SQLite + SQLAlchemy + Pydantic (+ LangGraph/OpenAI in a later phase).

> **Synthetic data only.** AI (later phase) organises, summarises and flags *possible* discrepancies.
> It never diagnoses, makes treatment decisions or changes medication. Agents may only write
> `AIFlag` and `AISummary` records.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env          # optional: OPENAI_API_KEY / OPENAI_MODEL for a later phase
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
**HealthPlus Pharmacy** and **HealthLab Diagnostics**. Use the profile menu to switch role, switch the
organization a doctor is working at, reset demo data, or exit to the landing page.

The SQLite DB is created and seeded on first load. A DB from an older schema version is rebuilt
automatically (demo data only — there are no migrations).

Deep links skip the landing page: `/?as=patient`, `/consent?as=patient`, `/patients?as=doctor`,
`/billing?as=pharmacist`, `/pending?as=lab`.

**Demo starting point:** Ahmed has *not* yet shared his records with Dr. Arif at South City Hospital —
grant it live from Consent & Access, then switch to the doctor.

## Doctor workflow (Phase 2)

Find patient (name / HB-ID / phone) → consent check for *this doctor at this organization* → authorized
profile (Overview · Timeline · Consultations · Prescriptions · Documents) → new consultation (draft or final,
optional PDF/PNG/JPG attachment) → clinical notes → multi-medicine prescription (draft → issue with
confirmation) → patient timeline + audit log update automatically.

**HealthBridge Clinical Copilot** (Doctor → AI Insights, or "Generate Clinical Summary" on a profile):
consent service → authorized record → LangGraph `organize_records → clinical_summary → consistency_review →
assemble`. Output is Pydantic-validated, every item cites a record ID, unsupported statements are removed,
and the review step never recommends treatment. Set `OPENAI_API_KEY` and `OPENAI_MODEL` in `.env` to use
OpenAI; without them (or if the API fails) a deterministic rule-based summary is shown instead.

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
