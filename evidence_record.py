from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass(frozen=True)
class EvidenceRecord:
    """Record of evidence extracted from a scholarly work."""
    id: str
    source_doi: str
    extracted_at: Optional[datetime] = field(default_factory=datetime.now)
    extracted_count: int = 0
    grounded_at: Optional[datetime] = None
    grounded_count: int = 0
    rejected_at: Optional[datetime] = None
    rejected_count: int = 0
    promoted_at: Optional[datetime] = None
    promoted_count: int = 0

    def update_extraction(self):
        self.extracted_at = datetime.now()
        self.extracted_count += 1

    def update_grounding(self):
        self.grounded_at = datetime.now()
        self.grounded_count += 1

    def update_rejection(self):
        self.rejected_at = datetime.now()
        self.rejected_count += 1

    def update_promotion(self):
        self.promoted_at = datetime.now()
        self.promoted_count += 1
