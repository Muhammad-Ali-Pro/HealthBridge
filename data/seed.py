"""Synthetic demo data. All people, records and organisations here are fictional.

Demo story starting point: Ahmed Khan has NOT yet shared his records with Dr. Arif at South City
Hospital — the patient grants that consent live during the demo.

Run directly to reset the database:  python -m data.seed
"""

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.models import (
    BILLING_CATEGORY,
    AuditAction,
    ClinicalNote,
    Consent,
    ConsentDuration,
    ConsentScope,
    ConsentScopeType,
    ConsentStatus,
    Consultation,
    Dispensing,
    DispensingStatus,
    Document,
    DocumentType,
    EventType,
    Invoice,
    LabOrder,
    LabOrderStatus,
    LabReport,
    LabResult,
    LabTestCategory,
    NoteType,
    Organization,
    OrgType,
    Patient,
    PatientEntry,
    PatientEntryType,
    PaymentStatus,
    Prescription,
    PrescriptionItem,
    PrescriptionStatus,
    ProviderOrganization,
    RecordCategory,
    Role,
    SourceType,
    User,
    local_day_start_utc,
    utcnow,
)
from services import audit_service, timeline_service

_RX_STEPS = [PrescriptionStatus.ISSUED, PrescriptionStatus.SENT, PrescriptionStatus.VERIFIED, PrescriptionStatus.DISPENSED]
_LAB_STEPS = [LabOrderStatus.ORDERED, LabOrderStatus.RECEIVED, LabOrderStatus.RESULTED,
              LabOrderStatus.VERIFIED, LabOrderStatus.PUBLISHED]
C = RecordCategory


def is_seeded(session: Session) -> bool:
    return session.scalar(select(func.count()).select_from(User)) > 0


def seed_if_empty(session: Session) -> bool:
    if is_seeded(session):
        return False
    seed(session)
    return True


def _record(session, *, patient_id, event_type, category, ref_table, ref_id, actor_id, organization_id, summary,
            when, source=SourceType.PROVIDER, actor_type=Role.DOCTOR):
    """Timeline event + RECORD_CREATED audit entry, with full provenance."""
    timeline_service.append_event(
        session, patient_id=patient_id, event_type=event_type, record_category=category, ref_table=ref_table,
        ref_id=ref_id, actor_id=actor_id, organization_id=organization_id, summary=summary,
        source_type=source, occurred_at=when)
    audit_service.log(session, action=AuditAction.RECORD_CREATED, actor_id=actor_id, actor_type=actor_type,
                      patient_id=patient_id, provider_id=actor_id if actor_type == Role.DOCTOR else None,
                      organization_id=organization_id, resource_type=ref_table, resource_id=ref_id,
                      timestamp=when, details={"event": event_type, "summary": summary})


def seed(session: Session) -> None:
    now = utcnow()
    day_start = local_day_start_utc()  # "today" = the viewer's local calendar day

    def days_ago(n: float) -> datetime:
        return now - timedelta(days=n)

    def today(hours_ago: float) -> datetime:
        # Keep "today" events inside the current (UTC) day so dashboard counts are stable.
        return max(now - timedelta(hours=hours_ago), day_start + timedelta(minutes=5))

    # --- Organizations -----------------------------------------------------
    def org(name, org_type, address):
        o = Organization(name=name, org_type=org_type, address=address)
        session.add(o)
        return o

    clifton_fc = org("Clifton Family Clinic", OrgType.CLINIC, "Block 5, Clifton, Karachi")
    clifton_mc = org("Clifton Medical Centre", OrgType.CLINIC, "Block 4, Clifton, Karachi")
    gulshan = org("Gulshan Medical Centre", OrgType.CLINIC, "Block 13-D, Gulshan-e-Iqbal, Karachi")
    city_hospital = org("City Hospital", OrgType.HOSPITAL, "Shahrah-e-Faisal, Karachi")
    south_city = org("South City Hospital", OrgType.HOSPITAL, "Shahrah-e-Firdousi, Clifton, Karachi")
    healthlab = org("HealthLab Diagnostics", OrgType.LABORATORY, "Tariq Road, PECHS, Karachi")
    healthplus = org("HealthPlus Pharmacy", OrgType.PHARMACY, "Khayaban-e-Ittehad, DHA Phase 6, Karachi")
    carepoint = org("CarePoint Pharmacy", OrgType.PHARMACY, "University Road, Gulshan-e-Iqbal, Karachi")
    session.flush()

    # --- Providers (a provider can work at several organizations) -----------
    def staff(name, role, specialty, *orgs):
        u = User(name=name, role=role, specialty=specialty)
        session.add(u)
        session.flush()
        for i, (o, title) in enumerate(orgs):
            session.add(ProviderOrganization(provider_id=u.id, organization_id=o.id, title=title, is_primary=i == 0))
        return u

    ayesha = staff("Dr. Ayesha Malik", Role.DOCTOR, "Family Medicine",
                   (clifton_fc, "Family Physician"), (city_hospital, "Visiting Consultant"))
    imran = staff("Dr. Imran Qureshi", Role.DOCTOR, "Internal Medicine",
                  (gulshan, "Consultant Physician"), (city_hospital, "Consultant Physician"))
    arif = staff("Dr. Arif Hassan", Role.DOCTOR, "Cardiology",
                 (south_city, "Consultant Cardiologist"), (clifton_mc, "Visiting Cardiologist"))
    sana = staff("Sana Iqbal", Role.PHARMACIST, None, (healthplus, "Pharmacist in charge"))
    hamza = staff("Hamza Sheikh", Role.PHARMACIST, None, (carepoint, "Pharmacist"))
    nadia = staff("Nadia Farooq", Role.LAB, "Clinical Pathology", (healthlab, "Laboratory Scientist"))

    # --- Patients ------------------------------------------------------------
    def patient(name, dob, sex, allergies, conditions, phone) -> Patient:
        u = User(name=name, role=Role.PATIENT)
        session.add(u)
        session.flush()
        p = Patient(user_id=u.id, name=name, dob=dob, sex=sex, allergies=allergies, conditions=conditions, phone=phone)
        session.add(p)
        session.flush()
        return p

    # Synthetic phone numbers (fictional).
    ahmed = patient("Ahmed Khan", date(1978, 4, 12), "male", ["Penicillin"], ["Type 2 diabetes"], "+92 300 555 0101")
    fatima = patient("Fatima Raza", date(1965, 9, 3), "female", [], ["Hypertension"], "+92 321 555 0102")
    usman = patient("Usman Siddiqui", date(1999, 1, 22), "male", ["Sulfonamide"], ["Asthma"], "+92 333 555 0103")
    zainab = patient("Zainab Hussain", date(1988, 6, 30), "female", [], ["Migraine"], "+92 345 555 0104")
    bilal = patient("Bilal Chaudhry", date(1958, 11, 8), "male", ["NSAIDs"], ["Hypertension", "Hyperlipidaemia"],
                    "+92 301 555 0105")
    hira = patient("Hira Baig", date(1992, 2, 14), "female", [], ["Hypothyroidism"], "+92 312 555 0106")
    saad = patient("Saad Mirza", date(1985, 7, 19), "male", [], ["GERD"], "+92 334 555 0107")

    # --- Consents (patient → provider @ organization → scope → duration) -----
    every, sel = ConsentScopeType.ALL, ConsentScopeType.SELECTED

    def consent(p, provider, organization, scope, categories=(), *, granted, duration=ConsentDuration.UNTIL_REVOKED,
                revoked=None, purpose=""):
        expires = granted + timedelta(hours=24) if duration == ConsentDuration.ONE_CONSULTATION else None
        c = Consent(patient_id=p.id, provider_id=provider.id, organization_id=organization.id, scope_type=scope,
                    duration=duration, granted_at=granted, expires_at=expires, purpose=purpose, created_by=p.user_id,
                    status=ConsentStatus.REVOKED if revoked else ConsentStatus.ACTIVE, revoked_at=revoked,
                    scopes=[ConsentScope(record_category=cat) for cat in categories])
        session.add(c)
        session.flush()
        cats = [x.value for x in C] if scope == every else list(categories)
        common = dict(actor_id=p.user_id, actor_type=Role.PATIENT, patient_id=p.id, provider_id=provider.id,
                      organization_id=organization.id, resource_type="consent", resource_id=c.id)
        audit_service.log(session, action=AuditAction.CONSENT_GRANTED, timestamp=granted, **common,
                          details={"consent_id": f"CON-{c.id:06d}", "scope_type": scope, "all_records": scope == every,
                                   "categories": cats, "duration": duration, "purpose": purpose})
        if revoked:
            audit_service.log(session, action=AuditAction.CONSENT_REVOKED, timestamp=revoked, **common,
                              details={"consent_id": f"CON-{c.id:06d}", "reason": "revoked by patient", "categories": cats})
        return c

    # Ahmed: full access for his family doctor; past one-visit consents have expired; one revoked.
    # No consent yet for Dr. Arif at South City Hospital — granted live in the demo.
    consent(ahmed, ayesha, clifton_fc, every, granted=days_ago(120), purpose="Regular family doctor")
    consent(ahmed, ayesha, city_hospital, sel, [C.CONSULTATIONS, C.PRESCRIPTIONS, C.MEDICATIONS, C.LAB_REPORTS],
            granted=days_ago(25) - timedelta(hours=1), duration=ConsentDuration.ONE_CONSULTATION, purpose="Day-unit visit")
    consent(ahmed, arif, clifton_mc, sel, [C.CONSULTATIONS, C.MEDICATIONS],
            granted=days_ago(30) - timedelta(hours=1), duration=ConsentDuration.ONE_CONSULTATION, purpose="Cardiology review")
    consent(ahmed, imran, gulshan, sel, [C.PRESCRIPTIONS, C.MEDICATIONS], granted=days_ago(90), revoked=days_ago(15),
            purpose="Second opinion")
    consent(fatima, imran, gulshan, every, granted=days_ago(120))
    consent(fatima, ayesha, clifton_fc, sel, [C.CONSULTATIONS, C.PRESCRIPTIONS, C.MEDICATIONS], granted=days_ago(100))
    consent(fatima, arif, south_city, every, granted=days_ago(15), purpose="Palpitations referral")
    consent(usman, ayesha, clifton_fc, every, granted=days_ago(200))
    consent(zainab, ayesha, clifton_fc, every, granted=days_ago(150))
    consent(bilal, ayesha, clifton_fc, sel, [C.PRESCRIPTIONS, C.MEDICATIONS, C.LAB_REPORTS], granted=days_ago(90))
    consent(bilal, arif, south_city, sel, [C.CONSULTATIONS, C.PRESCRIPTIONS, C.MEDICATIONS, C.LAB_REPORTS],
            granted=today(5), purpose="Chest pain assessment")
    consent(hira, ayesha, clifton_fc, every, granted=days_ago(180))
    consent(saad, imran, gulshan, every, granted=days_ago(60))

    # --- Care episodes ------------------------------------------------------
    at_cfc = dict(doctor=ayesha, organization=clifton_fc)
    at_gulshan = dict(doctor=imran, organization=gulshan)
    at_south = dict(doctor=arif, organization=south_city)
    hp = dict(pharmacy=healthplus, pharmacist=sana)
    cp = dict(pharmacy=carepoint, pharmacist=hamza)
    lab = dict(lab=healthlab, scientist=nadia)

    # Ahmed Khan — one patient, many providers and organizations.
    # The 150-day-old metformin record documents a different strength/frequency than the later one:
    # a deliberate documentation discrepancy for the Clinical Copilot to surface for clinician review.
    c = _consultation(session, ahmed, **at_cfc, when=days_ago(150), complaint="New diagnosis of type 2 diabetes",
                      notes="Polyuria and fatigue for 2 months.", observations="Random glucose 214 mg/dL. BMI 29.",
                      assessment="Hyperglycaemia consistent with type 2 diabetes.", diagnosis="Type 2 diabetes mellitus",
                      plan="Start metformin; diabetes education.", follow_up="Review in 3 months with HbA1c.")
    _prescription(session, c, **hp, upto=PrescriptionStatus.DISPENSED, unit_price=8.0,
                  item=dict(drug_name="Metformin", strength="850 mg", dosage="1 tablet", frequency="once daily",
                            duration_days=90, quantity=90, instructions="Take with the evening meal."))
    c = _consultation(session, ahmed, **at_cfc, when=days_ago(60), complaint="Routine diabetes review",
                      notes="Good adherence to diet. No hypoglycaemia.", observations="BP 128/82. BMI 28.",
                      assessment="Suboptimal glycaemic control.", diagnosis="Type 2 diabetes mellitus",
                      plan="Start metformin. Dietary advice.", follow_up="Repeat HbA1c in 3 months.")
    _prescription(session, c, **hp, upto=PrescriptionStatus.DISPENSED, unit_price=6.0,
                  item=dict(drug_name="Metformin", strength="500 mg", dosage="1 tablet", frequency="twice daily",
                            duration_days=90, quantity=180, instructions="Take with meals."))
    _lab_order(session, ahmed, **at_cfc, **lab, consultation=c, when=days_ago(60) + timedelta(minutes=20),
                       test="HbA1c", upto=LabOrderStatus.PUBLISHED, notes="Diabetes monitoring.",
                       values=[dict(analyte="HbA1c", value="8.1", unit="%", reference="< 5.7", flag="high"),
                               dict(analyte="Fasting glucose", value="156", unit="mg/dL", reference="70–99", flag="high")],
                       interpretation="Elevated HbA1c consistent with suboptimal glycaemic control.")
    _note(session, ahmed, **at_cfc, consultation=c, note_type=NoteType.FOLLOW_UP, when=days_ago(57),
          content="Reviewed HbA1c 8.1%. Reinforced dietary advice; continue metformin and recheck in 3 months.")
    c2 = _consultation(session, ahmed, doctor=arif, organization=clifton_mc, when=days_ago(30),
                       complaint="Chest discomfort on exertion", notes="Intermittent, resolves with rest.",
                       observations="ECG: normal sinus rhythm. BP 132/84.", assessment="Atypical chest pain, low risk.",
                       diagnosis="Atypical chest pain", plan="Lifestyle advice.", follow_up="Review if symptoms recur.")
    _note(session, ahmed, doctor=arif, organization=clifton_mc, consultation=c2, note_type=NoteType.OBSERVATION,
          when=days_ago(30) + timedelta(minutes=25), content="Resting ECG unremarkable. Consider stress test if recurrent.")
    _consultation(session, ahmed, doctor=ayesha, organization=city_hospital, when=days_ago(25),
                  complaint="Dizziness on standing", notes="Observed in day unit.",
                  observations="Orthostatic BP drop of 25 mmHg, resolved with fluids.",
                  assessment="Postural hypotension, resolved.", diagnosis="Orthostatic hypotension",
                  plan="Oral fluids. Continue current medication.", follow_up="GP review in 2 weeks.")
    _document(session, ahmed, uploader=ayesha, organization=city_hospital, source=SourceType.PROVIDER,
              doc_type=DocumentType.DISCHARGE_SUMMARY, title="Day-unit discharge summary",
              description="City Hospital day-unit observation, dizziness on standing.", when=days_ago(25) + timedelta(hours=4))
    _lab_order(session, ahmed, **at_cfc, **lab, consultation=None, when=days_ago(1), test="HbA1c (repeat)",
               upto=LabOrderStatus.RECEIVED, notes="3-month follow-up on metformin.")
    _document(session, ahmed, uploader_user_id=ahmed.user_id, organization=None, source=SourceType.PATIENT,
              doc_type=DocumentType.LAB_REPORT, title="External lab report (2025)", file_name="lab_report_2025.pdf",
              description="Lipid profile from a previous laboratory.", when=days_ago(40))
    _patient_entry(session, ahmed, PatientEntryType.NOTE, "Home glucose readings",
                   "Fasting readings 130–150 mg/dL this week.", days_ago(5))
    _patient_entry(session, ahmed, PatientEntryType.ALLERGY, "Shellfish (self-reported)",
                   "Itchy rash after prawns, 2019. Not confirmed by a doctor.", days_ago(3))

    # Fatima Raza — clinic + hospital, CarePoint pharmacy.
    c = _consultation(session, fatima, **at_gulshan, when=days_ago(45), complaint="Blood pressure follow-up",
                      notes="Home BP readings around 150/95.", observations="Clinic BP 152/94.",
                      assessment="Essential hypertension.", diagnosis="Essential hypertension",
                      plan="Start amlodipine.", follow_up="BP check in 6 weeks.")
    _prescription(session, c, **cp, upto=PrescriptionStatus.DISPENSED, unit_price=12.0,
                  item=dict(drug_name="Amlodipine", strength="5 mg", dosage="1 tablet", frequency="once daily",
                            duration_days=90, quantity=90, instructions="Take in the morning."))
    _lab_order(session, fatima, **at_gulshan, **lab, consultation=c, when=days_ago(45) + timedelta(minutes=15),
               test="Renal function panel", upto=LabOrderStatus.PUBLISHED, notes="Baseline before antihypertensive.",
               values=[dict(analyte="Creatinine", value="0.9", unit="mg/dL", reference="0.6–1.1"),
                       dict(analyte="eGFR", value="78", unit="mL/min/1.73m²", reference="> 60"),
                       dict(analyte="Potassium", value="4.2", unit="mmol/L", reference="3.5–5.1")],
               interpretation="Renal function within normal limits.")
    c = _consultation(session, fatima, **at_south, when=days_ago(10), complaint="Palpitations",
                      notes="Brief episodes at rest for 2 weeks.", observations="Holter: occasional ectopic beats.",
                      assessment="Benign ventricular ectopy.", diagnosis="Ventricular ectopic beats",
                      plan="Low-dose beta blocker.", follow_up="Cardiology review in 3 months.")
    _prescription(session, c, **cp, upto=PrescriptionStatus.DISPENSED, unit_price=15.0, paid=False,
                  item=dict(drug_name="Bisoprolol", strength="2.5 mg", dosage="1 tablet", frequency="once daily",
                            duration_days=90, quantity=90, instructions="Do not stop suddenly."))

    # Bilal Chaudhry — seen by Dr. Arif today; prescription issued, waiting for a pharmacy choice.
    c = _consultation(session, bilal, **at_cfc, when=days_ago(20), complaint="Lipid profile review",
                      notes="No muscle pain reported.", observations="BP 138/86.", assessment="LDL above target.",
                      diagnosis="Hyperlipidaemia", plan="Start atorvastatin.", follow_up="Lipid panel in 3 weeks.")
    _prescription(session, c, **hp, upto=PrescriptionStatus.DISPENSED, unit_price=25.0,
                  item=dict(drug_name="Atorvastatin", strength="20 mg", dosage="1 tablet", frequency="once daily at night",
                            duration_days=30, quantity=30, instructions="Take at bedtime."))
    _lab_order(session, bilal, **at_cfc, **lab, consultation=None, when=days_ago(2), test="Lipid panel",
               upto=LabOrderStatus.RESULTED, notes="On atorvastatin 20 mg for 3 weeks.",
               values=[dict(analyte="LDL cholesterol", value="128", unit="mg/dL", reference="< 100", flag="high"),
                       dict(analyte="HDL cholesterol", value="44", unit="mg/dL", reference="> 40"),
                       dict(analyte="Triglycerides", value="165", unit="mg/dL", reference="< 150", flag="high")],
               interpretation="LDL above target.")
    c = _consultation(session, bilal, **at_south, when=today(4), complaint="Chest tightness on exertion",
                      notes="Two episodes this week climbing stairs.", observations="ECG: no acute changes.",
                      assessment="Possible stable angina.", diagnosis="Suspected stable angina",
                      plan="Sublingual GTN as needed; exercise stress test.", follow_up="Cardiology clinic in 1 week.")
    _prescription(session, c, pharmacy=None, pharmacist=None, upto=PrescriptionStatus.ISSUED, quick=True,
                  item=dict(drug_name="Glyceryl trinitrate spray", strength="400 mcg/dose", dosage="1–2 sprays",
                            route="sublingual", frequency="as needed for chest pain", duration_days=30, quantity=1,
                            instructions="Sit down before use. Seek help if pain lasts over 5 minutes."))

    # A draft prescription Dr. Arif started for Fatima at South City Hospital (private until issued).
    session.add(Prescription(patient_id=fatima.id, provider_id=arif.id, organization_id=south_city.id,
                             status=PrescriptionStatus.DRAFT, created_at=days_ago(1), notes="Consider after Holter review.",
                             items=[PrescriptionItem(drug_name="Bisoprolol", strength="5 mg", dosage="1 tablet",
                                                     frequency="once daily", duration_days=30, quantity=30,
                                                     instructions="Dose increase — confirm before issuing.")]))

    # Saad Mirza — CarePoint queue.
    c = _consultation(session, saad, **at_gulshan, when=days_ago(2), complaint="Heartburn after meals",
                      notes="Worse when lying down.", observations="Abdomen soft, non-tender.",
                      assessment="Gastro-oesophageal reflux.", diagnosis="GERD", plan="PPI trial.",
                      follow_up="Review in 4 weeks.")
    _prescription(session, c, **cp, upto=PrescriptionStatus.SENT,
                  item=dict(drug_name="Omeprazole", strength="20 mg", dosage="1 capsule", frequency="once daily before breakfast",
                            duration_days=28, quantity=28, instructions="Take 30 minutes before breakfast."))

    # Today at Clifton Family Clinic — prescriptions and tests at every stage.
    c = _consultation(session, hira, **at_cfc, when=today(5), complaint="Thyroid function review",
                      notes="Tiredness improving.", observations="Pulse 68, regular.", assessment="Dose review.",
                      diagnosis="Hypothyroidism", plan="Continue levothyroxine.", follow_up="TSH in 6 weeks.")
    _prescription(session, c, **hp, upto=PrescriptionStatus.DISPENSED, quick=True, unit_price=4.0, paid="partial",
                  item=dict(drug_name="Levothyroxine", strength="50 mcg", dosage="1 tablet", frequency="once daily",
                            duration_days=60, quantity=60, instructions="Take on an empty stomach."))
    _lab_order(session, hira, **at_cfc, **lab, consultation=c, when=today(5) + timedelta(minutes=15), test="TSH",
               upto=LabOrderStatus.VERIFIED, notes="Dose titration.", quick=True,
               values=[dict(analyte="TSH", value="5.8", unit="mIU/L", reference="0.4–4.0", flag="high")],
               interpretation="Mildly raised TSH.")
    c = _consultation(session, zainab, **at_cfc, when=today(3.5), complaint="Recurrent headaches",
                      notes="Episodic, 2–3 times a month.", observations="Neurological exam normal.",
                      assessment="Migraine without aura.", diagnosis="Migraine", plan="Simple analgesia.",
                      follow_up="Headache diary; review in 2 months.")
    _prescription(session, c, **hp, upto=PrescriptionStatus.VERIFIED, quick=True,
                  item=dict(drug_name="Paracetamol", strength="500 mg", dosage="2 tablets", frequency="up to four times daily as needed",
                            duration_days=10, quantity=20, instructions="Do not exceed 8 tablets in 24 hours."))
    c = _consultation(session, usman, **at_cfc, when=today(2), complaint="Night-time wheezing",
                      notes="Wheeze on exertion and at night for one week.", observations="Scattered wheeze, SpO2 97%.",
                      assessment="Asthma, partially controlled.", diagnosis="Asthma", plan="Reliever inhaler; chest X-ray.",
                      follow_up="Review in 2 weeks.")
    _prescription(session, c, **hp, upto=PrescriptionStatus.SENT, quick=True,
                  item=dict(drug_name="Salbutamol", strength="100 mcg/puff", dosage="2 puffs", route="inhaled",
                            frequency="as needed", duration_days=30, quantity=1, instructions="Use with spacer."))
    _lab_order(session, usman, **at_cfc, **lab, consultation=c, when=today(2) + timedelta(minutes=10),
               test="Chest X-ray (PA view)", category=LabTestCategory.IMAGING, upto=LabOrderStatus.ORDERED,
               notes="Exclude infection; persistent wheeze.", priority="urgent")

    # --- Provider access history (shown to the patient under Consent & Access) ---
    def accessed(p, provider, organization, when, view, scope):
        audit_service.log(session, action=AuditAction.RECORD_ACCESSED, actor_id=provider.id, actor_type=Role.DOCTOR,
                          patient_id=p.id, provider_id=provider.id, organization_id=organization.id,
                          resource_type=view, timestamp=when, details={"scope": scope})

    accessed(ahmed, imran, gulshan, days_ago(80), "patient_record", ["prescriptions", "medications"])
    accessed(ahmed, ayesha, clifton_fc, days_ago(60), "patient_record", "all")
    accessed(ahmed, arif, clifton_mc, days_ago(30) - timedelta(minutes=30), "medical_timeline", ["consultations", "medications"])
    accessed(ahmed, ayesha, city_hospital, days_ago(25), "medical_timeline",
             ["consultations", "prescriptions", "medications", "lab_reports"])
    session.flush()


# ---------------------------------------------------------------------------
# Episode helpers
# ---------------------------------------------------------------------------


def _consultation(session, p, *, doctor, organization, when, complaint, notes, assessment,
                  observations="", diagnosis="", plan="", follow_up="") -> Consultation:
    c = Consultation(patient_id=p.id, provider_id=doctor.id, organization_id=organization.id, date=when,
                     complaint=complaint, notes=notes, observations=observations, assessment=assessment,
                     diagnosis=diagnosis, treatment_plan=plan, follow_up=follow_up)
    session.add(c)
    session.flush()
    category = C.HOSPITAL_RECORDS if organization.org_type == OrgType.HOSPITAL else C.CONSULTATIONS
    _record(session, patient_id=p.id, event_type=EventType.CONSULTATION, category=category, ref_table="consultations",
            ref_id=c.id, actor_id=doctor.id, organization_id=organization.id, when=when,
            summary=f"{complaint} — {assessment}")
    return c


def _note(session, p, *, doctor, organization, consultation, note_type, when, content) -> ClinicalNote:
    n = ClinicalNote(patient_id=p.id, provider_id=doctor.id, organization_id=organization.id,
                     consultation_id=consultation.id if consultation else None, note_type=note_type,
                     content=content, created_at=when)
    session.add(n)
    session.flush()
    category = C.HOSPITAL_RECORDS if organization.org_type == OrgType.HOSPITAL else C.CONSULTATIONS
    _record(session, patient_id=p.id, event_type=EventType.CLINICAL_NOTE, category=category, ref_table="clinical_notes",
            ref_id=n.id, actor_id=doctor.id, organization_id=organization.id, when=when, summary=content)
    return n


def _prescription(session, consult: Consultation, *, pharmacy, pharmacist, upto, item, quick=False,
                  unit_price: float = 10.0, paid: bool | str = True) -> Prescription:
    gaps = (timedelta(minutes=10), timedelta(minutes=40), timedelta(minutes=70)) if quick else (
        timedelta(minutes=10), timedelta(hours=2), timedelta(hours=3))
    when = consult.date
    reached = _RX_STEPS[: _RX_STEPS.index(upto) + 1]
    sent = PrescriptionStatus.SENT in reached
    rx = Prescription(consultation_id=consult.id, patient_id=consult.patient_id, provider_id=consult.provider_id,
                      organization_id=consult.organization_id, pharmacy_id=pharmacy.id if sent else None, status=upto,
                      created_at=when, issued_at=when + timedelta(minutes=5),
                      sent_at=when + gaps[0] if sent else None, items=[PrescriptionItem(**item)])
    session.add(rx)
    session.flush()
    label = f"{item['drug_name']} {item['strength']}"
    common = dict(patient_id=consult.patient_id, category=C.PRESCRIPTIONS, ref_table="prescriptions", ref_id=rx.id)

    _record(session, **common, event_type=EventType.PRESCRIPTION_ISSUED, actor_id=consult.provider_id,
            organization_id=consult.organization_id, when=when + timedelta(minutes=5), summary=f"{label} prescribed")
    if sent:
        _record(session, **common, event_type=EventType.PRESCRIPTION_SENT, actor_id=consult.provider_id,
                organization_id=consult.organization_id, when=when + gaps[0], summary=f"{label} sent to {pharmacy.name}")
    org_kw = dict(source=SourceType.ORGANIZATION, actor_type=Role.PHARMACIST)
    if PrescriptionStatus.VERIFIED in reached:
        _record(session, **common, event_type=EventType.PRESCRIPTION_VERIFIED, actor_id=pharmacist.id,
                organization_id=pharmacy.id, when=when + gaps[1], summary=f"{label} verified by the pharmacist", **org_kw)
    if PrescriptionStatus.DISPENSED in reached:
        qty = item["quantity"]
        disp = Dispensing(prescription_id=rx.id, pharmacist_id=pharmacist.id, organization_id=pharmacy.id,
                          dispensed_at=when + gaps[2], status=DispensingStatus.DISPENSED,
                          items_dispensed=[{"drug_name": item["drug_name"], "quantity_prescribed": qty, "quantity_dispensed": qty}])
        session.add(disp)
        session.flush()
        _record(session, patient_id=consult.patient_id, category=C.PRESCRIPTIONS, ref_table="dispensings", ref_id=disp.id,
                event_type=EventType.DISPENSING, actor_id=pharmacist.id, organization_id=pharmacy.id,
                when=disp.dispensed_at, summary=f"{item['drug_name']} ×{qty} dispensed", **org_kw)

        total = round(unit_price * qty, 2)
        amount_paid = total if paid is True else round(total / 2, 2) if paid == "partial" else 0.0
        status = PaymentStatus.PAID if paid is True else PaymentStatus.PARTIALLY_PAID if paid == "partial" else PaymentStatus.PENDING
        number = f"INV-{when.year}-{rx.id:05d}"
        inv = Invoice(invoice_number=number, prescription_id=rx.id, dispensing_id=disp.id, patient_id=consult.patient_id,
                      organization_id=pharmacy.id, created_by=pharmacist.id, total=total, amount_paid=amount_paid,
                      payment_status=status, created_at=disp.dispensed_at + timedelta(minutes=2),
                      items=[{"description": f"{label} ({item['dosage'] or 'unit'})", "quantity": qty,
                              "unit_price": unit_price, "total": total}])
        session.add(inv)
        session.flush()
        _record(session, patient_id=consult.patient_id, category=BILLING_CATEGORY, ref_table="invoices", ref_id=inv.id,
                event_type=EventType.INVOICE_ISSUED, actor_id=pharmacist.id, organization_id=pharmacy.id,
                when=inv.created_at, summary=f"Invoice {number} · PKR {total:,.0f} · {status.replace('_', ' ')}", **org_kw)
    return rx


def _lab_order(session, p, *, doctor, organization, lab, scientist, consultation, when, test, upto, notes,
               values=(), interpretation="", category=LabTestCategory.LAB, priority="routine", quick=False) -> LabOrder:
    o = LabOrder(patient_id=p.id, provider_id=doctor.id, organization_id=organization.id, lab_id=lab.id,
                 consultation_id=consultation.id if consultation else None, test_name=test, test_category=category,
                 priority=priority, clinical_notes=notes, status=upto, ordered_at=when)
    session.add(o)
    session.flush()
    record_category = C.IMAGING_REPORTS if category == LabTestCategory.IMAGING else C.LAB_REPORTS
    _record(session, patient_id=p.id, event_type=EventType.LAB_ORDERED, category=record_category, ref_table="lab_orders",
            ref_id=o.id, actor_id=doctor.id, organization_id=organization.id, when=when,
            summary=f"{test} ordered from {lab.name}")

    reached = _LAB_STEPS[: _LAB_STEPS.index(upto) + 1]
    if LabOrderStatus.RESULTED in reached:
        step = timedelta(minutes=30) if quick else timedelta(hours=20)
        r = LabResult(lab_order_id=o.id, organization_id=lab.id, entered_by=scientist.id, entered_at=when + step,
                      values=list(values), interpretation=interpretation)
        if LabOrderStatus.VERIFIED in reached:
            r.verified_by, r.verified_at = scientist.id, when + step * 2
        session.add(r)
        session.flush()
        if LabOrderStatus.PUBLISHED in reached:
            published = when + step * 3
            doc = _document(session, p, uploader=scientist, organization=lab, source=SourceType.ORGANIZATION,
                            doc_type=DocumentType.LAB_REPORT, title=f"{test} report", file_name=f"{test.lower()}_report.pdf",
                            category=record_category, when=published, log=False)
            rep = LabReport(report_number=f"RPT-{when.year}-{o.id:05d}", lab_order_id=o.id, patient_id=p.id,
                            organization_id=lab.id, published_by=scientist.id, published_at=published,
                            conclusion=interpretation, document_id=doc.id)
            session.add(rep)
            session.flush()
            _record(session, patient_id=p.id, event_type=EventType.LAB_REPORT_PUBLISHED, category=record_category,
                    ref_table="lab_reports", ref_id=rep.id, actor_id=scientist.id, organization_id=lab.id,
                    when=published, summary=f"{test} report published", source=SourceType.ORGANIZATION, actor_type=Role.LAB)
    return o


def _document(session, p, *, organization, source, doc_type, title, when, uploader=None, uploader_user_id=None,
              description="", file_name=None, category=RecordCategory.DOCUMENTS, log=True) -> Document:
    d = Document(patient_id=p.id, source_type=source, uploaded_by=uploader.id if uploader else uploader_user_id,
                 organization_id=organization.id if organization else None, doc_type=doc_type, title=title,
                 description=description, file_name=file_name or f"{title.lower().replace(' ', '_')}.pdf",
                 mime_type="application/pdf", size_bytes=None, storage_path=None,  # metadata only in demo data
                 record_category=category, created_at=when)
    session.add(d)
    session.flush()
    if log:
        actor_type = Role.PATIENT if source == SourceType.PATIENT else (uploader.role if uploader else Role.DOCTOR)
        _record(session, patient_id=p.id, event_type=EventType.DOCUMENT_ADDED, category=category, ref_table="documents",
                ref_id=d.id, actor_id=d.uploaded_by, organization_id=d.organization_id, when=when,
                summary=f"{title} added", source=source, actor_type=actor_type)
    return d


def _patient_entry(session, p, entry_type, title, details, when) -> PatientEntry:
    e = PatientEntry(patient_id=p.id, entry_type=entry_type, title=title, details=details, created_at=when)
    session.add(e)
    session.flush()
    _record(session, patient_id=p.id, event_type=EventType.PATIENT_ENTRY, category=C.DOCUMENTS, ref_table="patient_entries",
            ref_id=e.id, actor_id=p.user_id, organization_id=None, when=when, summary=f"{title}: {details}",
            source=SourceType.PATIENT, actor_type=Role.PATIENT)
    return e


if __name__ == "__main__":
    from core.db import get_session, reset_db

    reset_db()
    with get_session() as s:
        seed(s)
    print("Database reset and seeded with synthetic demo data.")
