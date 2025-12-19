from dataclasses import dataclass
from typing import List


@dataclass
class TurboUploadResponse:
    """Response from Turbo upload endpoint"""

    id: str  # Transaction ID
    owner: str  # Owner address
    data_caches: List[str]  # Cache endpoints
    fast_finality_indexes: List[str]  # Fast finality
    winc: str  # Winston credits cost


@dataclass
class TurboBalanceResponse:
    """Response from Turbo balance endpoint"""

    winc: str  # Available credits
    controlled_winc: str  # Controlled amount
    effective_balance: str  # Including shared credits
