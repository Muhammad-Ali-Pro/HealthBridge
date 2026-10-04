"""KPI aggregates for the role dashboards — all counted from the database."""

from sqlalchemy.orm import Session

from datetime import timedelta

from core.models import FlagStatus, LabOrderStatus, PrescriptionStatus, utcnow
from core.schemas import Actor
from services import clinical_service, insight_service, patient_service, provider_service, record_service


def doctor_kpis(session: Session, actor: Actor) -> dict[str, int]:
    rxs = provider_service.my_prescriptions(session, actor, include_drafts=True)
    labs = provider_service.my_lab_orders(session, actor)
    since = utcnow() - timedelta(days=30)
    return {
        "patients_with_access": len(patient_service.with_access(session, actor)),
        "consultations_today": len(provider_service.my_consultations(session, actor, today_only=True, this_org_only=True)),
        "draft_consultations": len(clinical_service.list_drafts(session, actor)),
        "draft_prescriptions": sum(rx.status == PrescriptionStatus.DRAFT for rx in rxs),
        "issued_prescriptions": sum(rx.status == PrescriptionStatus.ISSUED for rx in rxs),
        "active_prescriptions": sum(record_service.is_current(rx) for rx in rxs),
        "awaiting_pharmacy": sum(rx.status in (PrescriptionStatus.SENT, PrescriptionStatus.VERIFIED) for rx in rxs),
        "follow_ups": len(provider_service.pending_follow_ups(session, actor)),
        "results_ready": sum(o.status == LabOrderStatus.PUBLISHED for o in labs),
        "tests_pending": sum(o.status != LabOrderStatus.PUBLISHED for o in labs),
        "open_alerts": len(insight_service.list_flags(session, actor, status=FlagStatus.OPEN)),
        # Issued (and possibly sent on) at this organization in the last 30 days.
        "prescriptions_issued_30d": sum(rx.issued_at is not None and rx.issued_at >= since
                                        and rx.organization_name == actor.organization.name for rx in rxs),
        "ai_review_items": len(insight_service.list_flags(session, actor, status=FlagStatus.OPEN)),
    }
