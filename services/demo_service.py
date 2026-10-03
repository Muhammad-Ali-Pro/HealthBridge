"""Demo housekeeping: overview counts and a one-click reset to the seeded state."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.db import get_session, reset_db
from core.models import (
    AuditLog,
    Consent,
    Consultation,
    LabOrder,
    Organization,
    Patient,
    Prescription,
    TimelineEvent,
    User,
)
from data.seed import seed


def overview_counts(session: Session) -> dict[str, int]:
    def count(model) -> int:
        return session.scalar(select(func.count()).select_from(model))

    return {
        "Patients": count(Patient), "Users": count(User), "Organizations": count(Organization),
        "Consents": count(Consent), "Consultations": count(Consultation), "Prescriptions": count(Prescription),
        "Lab orders": count(LabOrder), "Timeline events": count(TimelineEvent), "Audit entries": count(AuditLog),
    }


def reset_demo_data() -> None:
    reset_db()
    with get_session() as session:
        seed(session)
