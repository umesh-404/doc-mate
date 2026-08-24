"""Light FHIR shaping helpers.

Maps internal :class:`ClinicalItemKind` values onto FHIR R4 resource names and
back. Intentionally minimal — used for internal labelling and for the
"ABDM-ready" story (see PROJECT.md sections 3 and 9). This is not a full FHIR
serializer.
"""

from __future__ import annotations

from app.db.models import ClinicalItemKind, DocumentType

# ClinicalItemKind -> FHIR R4 resource name.
KIND_TO_FHIR: dict[ClinicalItemKind, str] = {
    ClinicalItemKind.observation: "Observation",
    ClinicalItemKind.medication: "MedicationRequest",
    ClinicalItemKind.allergy: "AllergyIntolerance",
    ClinicalItemKind.condition: "Condition",
    ClinicalItemKind.procedure: "Procedure",
}

FHIR_TO_KIND: dict[str, ClinicalItemKind] = {
    name: kind for kind, name in KIND_TO_FHIR.items()
}


def fhir_resource_for(kind: ClinicalItemKind | str) -> str:
    """Return the FHIR resource name for a clinical item kind."""
    if isinstance(kind, str):
        kind = ClinicalItemKind(kind)
    return KIND_TO_FHIR[kind]


def kind_for_fhir(resource: str) -> ClinicalItemKind:
    """Return the internal kind for a FHIR resource name."""
    return FHIR_TO_KIND[resource]


# A neutral, human-readable label for the type of source document. Used to
# build citation labels (e.g. "Rx", "Lab", "Discharge").
DOC_TYPE_CITATION_PREFIX: dict[DocumentType, str] = {
    DocumentType.prescription: "Rx",
    DocumentType.lab_report: "Lab",
    DocumentType.discharge_summary: "Discharge",
    DocumentType.scan_film: "Scan",
    DocumentType.typed_note: "Note",
    DocumentType.other: "Doc",
}


def citation_prefix_for(doc_type: DocumentType | str) -> str:
    """Return the short citation prefix for a document type."""
    if isinstance(doc_type, str):
        doc_type = DocumentType(doc_type)
    return DOC_TYPE_CITATION_PREFIX.get(doc_type, "Doc")
