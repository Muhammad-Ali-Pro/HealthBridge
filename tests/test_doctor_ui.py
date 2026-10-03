"""Doctor workflow through the real Streamlit pages (AppTest): forms, detail pages and the Copilot."""

from sqlalchemy import select
from streamlit.testing.v1 import AppTest

from core.config import ROOT_DIR
from core.db import get_session
from core.models import Consultation, Prescription, Role

APP = str(ROOT_DIR / "app.py")
AYESHA, AHMED = 1, 1  # Dr. Ayesha Malik (user 1) has an all-records consent for Ahmed Khan (patient 1)


def run(path: str, **state) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["hb_entered"] = True
    at.session_state["hb_role"] = Role.DOCTOR
    at.session_state["hb_user_id"] = AYESHA
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    at.switch_page(path)
    at.run()
    return at


def markup(at: AppTest) -> str:
    return " ".join(m.value for m in at.markdown)


def test_consultation_form_saves_a_final_record_and_opens_details():
    at = run("views/doctor/consultation_editor.py", sel_patient=AHMED)
    assert not at.exception, [e.value for e in at.exception]
    next(t for t in at.text_input if t.label == "Reason for visit *").set_value("UI test: persistent cough")
    next(t for t in at.text_area if t.label == "Assessment").set_value("Likely post-viral cough")
    next(b for b in at.button if b.label == "Save consultation").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "UI test: persistent cough" in markup(at)          # consultation details page
    with get_session() as s:
        c = s.scalar(select(Consultation).where(Consultation.complaint == "UI test: persistent cough"))
        assert c.status == "final" and c.organization_id == 1  # Clifton Family Clinic, from working context


def test_consultation_form_shows_inline_validation():
    at = run("views/doctor/consultation_editor.py", sel_patient=AHMED)
    next(b for b in at.button if b.label == "Save consultation").click()
    at.run()
    assert "Reason for visit is required." in markup(at)


def test_prescription_form_issue_flow_with_confirmation():
    at = run("views/doctor/prescription_editor.py", sel_patient=AHMED)
    assert not at.exception, [e.value for e in at.exception]
    next(s for s in at.selectbox if s.label == "Medicine name *").set_value("Metformin")
    next(t for t in at.text_input if t.label == "Strength *").set_value("500 mg")
    next(t for t in at.text_input if t.label == "Frequency *").set_value("twice daily")
    next(n for n in at.number_input if n.label == "Duration (days) *").set_value(30)
    next(n for n in at.number_input if n.label == "Quantity *").set_value(60)
    next(b for b in at.button if b.label == "Issue Prescription").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "about to issue this prescription to" in " ".join(m.value for m in at.markdown)  # confirmation dialog
    [b for b in at.button if b.label == "Issue Prescription"][-1].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    with get_session() as s:
        rx = s.scalar(select(Prescription).where(Prescription.provider_id == AYESHA, Prescription.status == "issued"))
        assert rx is not None and rx.items[0].drug_name == "Metformin" and rx.issued_at is not None
    assert f"Prescription RX-{rx.id:05d}" in markup(at)  # landed on the details page


def test_prescription_form_validation_blocks_issue():
    at = run("views/doctor/prescription_editor.py", sel_patient=AHMED)
    next(b for b in at.button if b.label == "Issue Prescription").click()
    at.run()
    assert "Medicine name is required." in markup(at)


def test_workflow_pages_render():
    with get_session() as s:
        cid = s.scalar(select(Consultation.id).where(Consultation.provider_id == AYESHA, Consultation.status == "final"))
        rx_id = s.scalar(select(Prescription.id).where(Prescription.provider_id == AYESHA))
    for path, state in [("views/doctor/consultation_detail.py", {"sel_consultation": cid}),
                        ("views/doctor/prescription_editor.py", {"sel_patient": AHMED}),
                        ("views/doctor/prescription_detail.py", {"sel_rx": rx_id})]:
        at = run(path, **state)
        assert not at.exception, (path, [e.value for e in at.exception])
        assert 'class="hb-page-title"' in markup(at)


def test_patient_profile_tabs_and_ai_insights_generate():
    at = run("views/doctor/patients.py", sel_patient=AHMED)
    assert not at.exception
    assert "Patient has granted you access" in markup(at)
    assert {"New consultation", "Create prescription", "Generate Clinical Summary"} <= {b.label for b in at.button}

    at = run("views/doctor/ai_insights.py", sel_patient=AHMED)
    next(b for b in at.button if b.label == "Generate Clinical Summary").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    html = markup(at)
    assert "AI-generated summary for clinician review" in html
    assert "Potential medication documentation discrepancy" in html and "Sources" in html
