from datetime import datetime
from knowledge_engine.evidence_record import EvidenceRecord

def test_evidence_record_initialization():
    record = EvidenceRecord(id="123", source_doi="10.1/example")
    assert record.id == "123"
    assert record.source_doi == "10.1/example"
    assert record.extracted_at is not None
    assert record.extracted_count == 0
    assert record.grounded_at is None
    assert record.grounded_count == 0
    assert record.rejected_at is None
    assert record.rejected_count == 0
    assert record.promoted_at is None
    assert record.promoted_count == 0

def test_evidence_record_update_extraction():
    record = EvidenceRecord(id="123", source_doi="10.1/example")
    record.update_extraction()
    assert record.extracted_at is not None
    assert record.extracted_count == 1

def test_evidence_record_update_grounding():
    record = EvidenceRecord(id="123", source_doi="10.1/example")
    record.update_grounding()
    assert record.grounded_at is not None
    assert record.grounded_count == 1

def test_evidence_record_update_rejection():
    record = EvidenceRecord(id="123", source_doi="10.1/example")
    record.update_rejection()
    assert record.rejected_at is not None
    assert record.rejected_count == 1

def test_evidence_record_update_promotion():
    record = EvidenceRecord(id="123", source_doi="10.1/example")
    record.update_promotion()
    assert record.promoted_at is not None
    assert record.promoted_count == 1
