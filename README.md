# HealthBridge

**One patient. One connected health journey.**

HealthBridge is a consent-based connected health record. Clinics, hospitals, laboratories and pharmacies
contribute to one longitudinal patient timeline, and the patient decides which doctor — at which
organization — may see which records, for how long. An AI Clinical Copilot summarises only the records a
doctor is authorized to see and flags possible documentation discrepancies for clinician review.

> **Hackathon MVP · synthetic data only · sign-in is simulated (DEMO MODE).**
> The AI organises, summarises and flags. It never diagnoses, prescribes or changes treatment.

## 🚀 Hackathon Demo

> **Demo:** Coming soon (Streamlit Community Cloud — see the Deployment section below).

The demo shows a patient (Ahmed Khan), a doctor working at two organizations (Dr. Arif Hassan), a pharmacy
(HealthPlus Pharmacy) and a laboratory (HealthLab Diagnostics) connected through one consent-controlled
timeline — and a multi-agent AI copilot that can only see what the patient shared.

## 🎯 Problem

A patient's care is spread across clinics, hospitals, laboratories and pharmacies whose records are not
connected. Doctors often lack the medication and visit history they need at the point of care, patients end up
carrying paper and repeating their history, and sharing data safely — with the right person, for the right
purpose — is hard.

## 💡 Solution

- **One timeline** built from digital events at source (consultations, prescriptions, lab reports, dispensing),
  each with its provenance (organization, clinician, timestamp, source type).
- **Patient-controlled consent** — per doctor **and** organization, per record category, time-limited and revocable.
- **Minimum-necessary access** for pharmacies and laboratories.
- **A consent-bound AI copilot** for doctors, with every statement linked to a source record.

## ✨ Current Features

### Patient
- Home dashboard, **My Health**, **Medical Timeline** (filters; every entry shows its source), **Medications**, **Lab Reports**.
- **Documents** page — provider, laboratory and own documents; upload (PDF/PNG/JPG, 10 MB) and download.
- **Patient-provided information** — health notes and **patient-reported allergies** (append-only, always labelled
  *Patient-provided*; they never change the clinician-documented allergy list).
- **Prescriptions** with plain-language status; **choose a pharmacy** for an issued prescription and send it.
- **Additional notes** from consultations are visible; **internal clinician notes are never shown**.
- **Care Network** — every doctor and organization connected to the patient.
- **Consent & Access** — share selected categories or all records (explicit warning + confirmation), choose a
  duration (until revoked, one consultation, 24 h, 7 days), see who opened the record, revoke at any time.

### Doctor
- Dashboard (today's consultations, follow-ups, prescriptions issued, AI review items, recent patients).
- Patient search (identity only until consent) and a **patient workspace** limited to consented categories.
- **"Working at" organization switcher** — access is re-checked per organization.
- Consultations (editable visit time, clinical fields, patient-visible additional notes, internal notes,
  attachments) and multi-medicine e-prescriptions (allergy warnings, send to a pharmacy).

### AI Clinical Copilot
- Three agents in a **LangGraph** graph, over consent-filtered records only.
- **Google Gemini** through a provider abstraction, with **bring-your-own-key** (BYOK).
- Structured, validated output; every item cites its source records.
- AI flags with **Accept / Dismiss** and **View source**.
- Works without a key: a deterministic response clearly labelled *"Demo AI response — live model unavailable"*.

### Pharmacy *(minimum — the full workflow is not implemented yet)*
- Receives prescriptions sent to it (by the doctor or the patient) in its queue.
- Read-only dashboard, prescription list, pending-verification view, dispensing log, billing table and patients
  view — showing only what is needed to dispense (identity, allergies, medicines, prescriber).
- Verify, reject, dispense, invoice and payment **actions are placeholders** (see the Roadmap section below).

### Laboratory *(read-only demo pages with seeded data; workflow is future)*

## 🤖 AI Architecture

```text
Doctor
  ↓  Consent / authorization  — no active consent → no agent runs
  ↓  Record Retrieval Agent   — receives only the consent-filtered record (no database access)
  ↓  Clinical Summary Agent   — AIProvider.generate_structured → Pydantic validation
  ↓  Safety / Consistency Agent — rule-based checks + model checks
  ↓  Assemble & validate      — citations to unknown records are removed
  ↓  Doctor review            — Accept / Dismiss / View source
```

- **LangGraph** orchestrates the agents (`agents/copilot.py`).
- **Provider abstraction:** agents depend only on `AIProvider` (`agents/providers.py`);
  `GeminiProvider` (official `google-genai` SDK) is the implemented provider. Another provider can be added as a
  subclass without changing the agents, graph, UI or schemas.
- **Structured output:** JSON-schema responses validated against Pydantic models (`agents/schemas.py`).
- AI writes only AI summaries and AI flags — never clinical records.

## 🔐 Security & Privacy

- **Consent-based authorization**, scoped to patient + doctor + organization + record categories, enforced
  **server-side** in the service layer (`services/access_service.py`, `services/record_service.py`) — not by hiding buttons.
- **AI data boundary:** patient data is filtered by the consent layer *before* the AI graph runs; agents and the
  Gemini provider never get a database session or unrestricted data. Revocation immediately blocks the AI too.
- **Role separation:** pharmacies see only prescriptions sent to them and cannot browse the medical record;
  doctors never see pharmacy billing; patients never see internal clinician notes.
- **Provenance & audit:** every record keeps its source; consent changes, record access, denials, record
  creation and AI generation/review are audited (without record content, prompts or keys).
- **Gemini key:** held only in the user's Streamlit session — never stored in the database, logs or audit
  entries, never committed. `.env` and Streamlit secrets files are git-ignored.
- **Demo limitation:** authentication is simulated; this is not production-grade security.

## 🏗️ Architecture

```text
Streamlit UI                     views/ (pages per role) · ui/ (shell, components, dialogs)
   ↓
Service layer                    services/ — business rules, validation, server-side authorization
   ↓
Authorization / consent          access_service · record_service (the only read path to a record)
   ↓
Domain models → SQLite           core/models.py (SQLAlchemy) · data/healthbridge.db (seeded on first start)
   ↓ (consent-filtered record)
LangGraph AI layer               agents/ — retrieval, summary, safety/consistency, assemble
   ↓
AIProvider → GeminiProvider      Google Gemini API (bring your own key)
```

## 📁 Project Structure

```text
app.py        Streamlit entry point and router
agents/       LangGraph copilot, agent rules, Pydantic AI schemas, AI provider abstraction (Gemini)
core/         configuration, database setup, SQLAlchemy models, Pydantic DTOs
services/     access control, consent, records, clinical, prescriptions, documents, pharmacy, audit, copilot
ui/           app shell, theme, shared components, patient dialogs, AI settings (BYOK)
views/        pages for patient, doctor, pharmacy and laboratory
data/         demo seed script and synthetic drug catalog
tests/        service, authorization, AI and Streamlit AppTest UI tests
docs/         workflow specifications (docs/workflows/)
```

## 🧪 Testing

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pyflakes agents core services ui views tests data app.py
```

Current status: **182 tests passing** (verified on Python 3.14 locally and on Python 3.12 in a fresh environment).
Gemini is tested with an offline fake client; no real key is used in tests.

## ⚙️ Local Setup

```powershell
git clone https://github.com/Muhammad-Ali-Pro/HealthBridge.git
cd HealthBridge
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m data.seed          # optional — the app also creates and seeds the demo database on first start
streamlit run app.py         # http://localhost:8501
```

Python 3.12 or newer. Optional local configuration: `copy .env.example .env` (no key is required).

<details><summary>Windows Smart App Control note</summary>

If importing SQLAlchemy fails with `DLL load failed ... An Application Control policy has blocked this file`,
reinstall it as pure Python:

```powershell
$env:DISABLE_SQLALCHEMY_CEXT = "1"
pip install --force-reinstall --no-deps --no-binary sqlalchemy sqlalchemy
```
</details>

## 🔑 Gemini API

- **Optional.** Without a key the copilot runs in a clearly labelled demo/fallback mode.
- **Bring your own key:** Doctor → patient → **AI Clinical Copilot** → **Configure AI** → paste a key from
  [Google AI Studio](https://aistudio.google.com/apikey) → **Connect & Test**. The key stays in that browser session;
  **Clear API Key** removes it.
- **Models:** default `gemini-3.8-flash`; `gemini-3.5-flash` and `gemini-3.5-flash-lite` are selectable
  (or set `GEMINI_MODEL`). Google's pricing page listed these on the Gemini API free tier when checked on
  4 Oct 2026 — check your own limits in AI Studio.
- Local developers may set `GEMINI_API_KEY` in `.env` (see `.env.example`). **Never commit a key**, and do **not**
  add a shared Gemini secret to the public Streamlit deployment — every visitor would use it.
- A successful live Gemini call has not yet been verified with a real key; the integration is covered by offline tests.

## ☁️ Deployment

Streamlit Community Cloud: **Create app** → repository `Muhammad-Ali-Pro/HealthBridge` → branch `main` →
main file `app.py` → **Advanced settings:** Python **3.12**, leave Secrets empty → **Deploy**.

- Dependencies come from `requirements.txt`; theme and navigation settings from `.streamlit/config.toml`.
- The SQLite demo database is created and seeded automatically. On Community Cloud it is **shared by all
  visitors and temporary** — it resets when the app restarts. *Reset demo data* (profile menu) resets it for everyone.
- Open the app shortly before judging; Community Cloud apps sleep after a period without traffic.

## 🧭 Demo Workflow

### Patient
1. Landing page → **Continue as Ahmed Khan**.
2. **My Health** → **Medical Timeline** (sources from several organizations).
3. **Add a health note** and **Add allergy or information** → both labelled *Patient-provided*.
4. **Documents** → **Upload a document** → download it.
5. **Prescriptions** → choose **HealthPlus Pharmacy** for an issued prescription → status *Sent*.
   (Ask the doctor to issue one first if none is waiting.)
6. **Consent & Access** → share **Consultations, Prescriptions, Current medications** with
   *Dr. Arif Hassan — South City Hospital*; later **Revoke access**.

### Doctor
1. **Continue as Dr. Arif** (working at South City Hospital) → **Patients** → open Ahmed.
2. Only the consented categories are visible; patient-reported allergies are labelled.
3. **AI Clinical Copilot** → optionally **Configure AI** with your Gemini key → **Generate Clinical Summary**
   (or *Run demo analysis*) → agent stages, *Based on N consented records*, flags → **View source**, **Accept / Dismiss**.
4. **New consultation** → **Save & create prescription** → issue → send to a pharmacy.
5. **Working at → Clifton Medical Centre** → Ahmed is *ACCESS RESTRICTED* (organization isolation).

### Pharmacy
1. **Continue as HealthPlus Pharmacy** → the sent prescription appears under **Pending Verification**, with
   identity, allergies and medicines only. (Verification, dispensing and billing actions are not implemented yet.)

Deep links skip the landing page: `/?as=patient`, `/?as=doctor`, `/?as=pharmacist`, `/?as=lab`.

## 🗺️ Roadmap

**Completed**
- Phase 1 — foundation, demo data, consent model, role workspaces.
- Phase 2 — doctor workflow and multi-agent AI Clinical Copilot (Gemini BYOK).
- Patient workflow — patient entries, allergies, documents, pharmacy choice, consent management.

**Next**
- Full pharmacy workflow — verification/rejection, full and partial dispensing, unavailable medicines,
  substitution requests (never automatic), invoicing and payments.
- Read-only pharmacy dispensing status for doctors.

**Future**
- Laboratory workflow, real authentication, production hosting (PostgreSQL), HL7 FHIR integrations, OCR import of paper records.

## ⚠️ Demo Limitations

- Authentication is simulated (persona switching); not production security.
- SQLite demo persistence; on Streamlit Community Cloud the data is shared and temporary.
- Live AI needs the user's own Gemini key; the real-key path is not yet verified end to end.
- The full pharmacy workflow is not implemented yet.
- Production deployment and security hardening are still required.

## 📄 Documentation

- Workflow specifications (source of truth for implementation): [`docs/workflows/`](docs/workflows/README.md)
  — [patient](docs/workflows/patient/) and [pharmacy](docs/workflows/pharmacy/).
- The product requirements document (PRD v2.1) is maintained outside this repository.
