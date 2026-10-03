"""Headless render of the landing page and every page for every role through the real router (app.py)."""

import pytest
from streamlit.testing.v1 import AppTest

from core.config import ROOT_DIR
from core.models import Role
from ui.shell import DEMO_LABEL, NAV

APP = str(ROOT_DIR / "app.py")
CASES = [(role, item.path) for role, items in NAV.items() for item in items]

# Seed order: Dr. Ayesha Malik = user 1, Dr. Arif Hassan = user 3; South City Hospital = org 5.
AYESHA, ARIF, SOUTH_CITY = 1, 3, 5


def run(role: str, path: str | None = None, **state) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["hb_entered"] = True
    at.session_state["hb_role"] = role
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    if path and path != NAV[role][0].path:
        at.switch_page(path)
        at.run()
    return at


def markup(at: AppTest) -> str:
    return " ".join(m.value for m in at.markdown)


def test_landing_page_offers_four_demo_personas():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    html = markup(at)
    assert "One connected health journey" in html and DEMO_LABEL in html
    assert "CREATE" in html and "CONNECT" in html and "CONTROL" in html
    labels = [b.label for b in at.button]
    assert labels == ["Continue as Ahmed Khan", "Continue as Dr. Arif", "Continue as HealthPlus Pharmacy",
                      "Continue as HealthLab Diagnostics"]


def test_continue_as_doctor_enters_dr_arif_at_south_city():
    at = AppTest.from_file(APP, default_timeout=30).run()
    next(b for b in at.button if b.label == "Continue as Dr. Arif").click().run()
    assert not at.exception
    actor = at.session_state["hb_actor"]
    assert actor.user.name == "Dr. Arif Hassan" and actor.organization.name == "South City Hospital"
    assert 'class="hb-page-title"' in markup(at)


@pytest.mark.parametrize("label", ["Back to home page", "Home page"])
def test_every_workspace_can_return_to_the_landing_page(label):
    at = run(Role.PHARMACIST, "views/pharmacy/billing.py")
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception
    assert at.session_state["hb_entered"] is False
    assert any(b.label == "Continue as Ahmed Khan" for b in at.button)


@pytest.mark.parametrize(("role", "path"), CASES, ids=[f"{r}-{p.split('/', 1)[1]}" for r, p in CASES])
def test_page_renders_without_error(role, path):
    at = run(role, path)
    assert not at.exception, [e.value for e in at.exception]
    html = markup(at)
    assert 'class="hb-page-title"' in html
    assert DEMO_LABEL in html


def test_role_specific_navigation():
    labels = {role: [n.label for n in items] for role, items in NAV.items()}
    assert labels[Role.PATIENT] == ["Home", "My Health", "Medical Timeline", "Prescriptions", "Medications",
                                    "Lab Reports", "Care Network", "Consent & Access"]
    assert labels[Role.DOCTOR] == ["Dashboard", "Patients", "Consultations", "Prescriptions", "Medical Timeline",
                                   "Reports & Documents", "My Organizations", "AI Insights"]
    assert labels[Role.PHARMACIST] == ["Dashboard", "Prescriptions", "Pending Verification", "Dispensing", "Billing", "Patients"]
    assert labels[Role.LAB] == ["Dashboard", "Test Orders", "Pending Reports", "Published Reports", "Patients"]
    assert "Care Network" not in labels[Role.DOCTOR]


def test_doctor_sees_authorized_record_with_scope_banner():
    at = run(Role.DOCTOR, "views/doctor/patients.py", sel_patient=1, hb_user_id=AYESHA)
    assert not at.exception
    html = markup(at)
    assert "Patient has granted you access" in html and 'class="hb-timeline"' in html


def test_doctor_without_consent_sees_locked_view():
    # Demo start: Ahmed has not shared his records with Dr. Arif at South City Hospital.
    at = run(Role.DOCTOR, "views/doctor/patients.py", sel_patient=1, hb_user_id=ARIF, hb_org_id=SOUTH_CITY)
    assert not at.exception
    html = markup(at)
    assert "ACCESS RESTRICTED" in html and "has not granted you access" in html
    assert 'class="hb-timeline"' not in html
    assert not any(b.label == "New consultation" for b in at.button)  # no write actions without consent


def test_patient_consent_page_shows_access_and_history():
    at = run(Role.PATIENT, "views/patient/consent.py")
    assert not at.exception
    html = markup(at)
    assert "Dr. Ayesha Malik" in html and "Consent granted" in html and "Record opened" in html
    assert any(b.label == "Share Records with a Doctor" for b in at.button)
