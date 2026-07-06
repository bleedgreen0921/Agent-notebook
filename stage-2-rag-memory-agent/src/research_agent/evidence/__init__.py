"""证据登记与引用校验。"""

from .ledger import EvidenceLedger
from .validator import CitationValidator

__all__ = ["CitationValidator", "EvidenceLedger"]
