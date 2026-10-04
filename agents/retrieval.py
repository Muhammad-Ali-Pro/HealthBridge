"""Record Retrieval Agent — the ONLY way the AI obtains patient data.

It does not hold a database session and cannot run queries. It receives a `ScopedRecordSource`: a handle
created by the service layer AFTER the consent check, bound to one doctor, one organization and one
patient. Calling `fetch()` goes back through the consent service (record_service), so a revoked or expired
consent — or an organization switch — yields no data.
"""

from typing import Protocol

from agents import organizer
from agents.schemas import SourceRef
from core.schemas import AuthorizedRecord


class ScopedRecordSource(Protocol):
    patient_id: int
    provider_id: int
    organization_id: int

    def fetch(self) -> AuthorizedRecord:
        """Return the patient's record filtered to the consent scope (raises if access is not granted)."""
        ...


class RetrievalViolation(PermissionError):
    pass


def retrieve(source: ScopedRecordSource) -> tuple[dict, list[SourceRef], dict[str, int], list[str]]:
    record = source.fetch()
    # Defence in depth: the record must be exactly the authorized patient, under an active consent.
    if record.patient.id != source.patient_id or not record.access.allowed:
        raise RetrievalViolation("Retrieved record does not match the authorized scope")
    dataset, sources = organizer.organize(record)
    return dataset, sources, organizer.retrieval_counts(dataset), list(record.access.categories)
