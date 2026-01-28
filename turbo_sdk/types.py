from dataclasses import dataclass, field
from typing import List, Callable, Literal, Optional

# Type aliases
ChunkingMode = Literal["auto", "force", "disabled"]
ProgressCallback = Callable[[int, int], None]  # (processed_bytes, total_bytes)


@dataclass
class ChunkingParams:
    """Configuration for chunked/multipart uploads"""

    chunk_size: int = 5 * 1024 * 1024  # 5 MiB default
    max_chunk_concurrency: int = 1
    chunking_mode: ChunkingMode = "auto"
    max_finalize_ms: int = 150_000  # 2.5 minutes per GiB

    def __post_init__(self):
        min_chunk = 5 * 1024 * 1024  # 5 MiB
        max_chunk = 500 * 1024 * 1024  # 500 MiB
        if not (min_chunk <= self.chunk_size <= max_chunk):
            raise ValueError(f"chunk_size must be between {min_chunk} and {max_chunk} bytes")
        if self.max_chunk_concurrency < 1:
            raise ValueError("max_chunk_concurrency must be at least 1")


@dataclass
class ChunkedUploadInit:
    """Response from chunked upload initiation"""

    id: str  # Upload session ID
    min: int  # Minimum chunk size
    max: int  # Maximum chunk size
    chunk_size: int  # Requested chunk size


@dataclass
class TurboUploadStatus:
    """Status of an upload (used for chunked upload polling)"""

    status: str  # VALIDATING, ASSEMBLING, FINALIZING, FINALIZED, INVALID, UNDERFUNDED
    timestamp: int
    id: Optional[str] = None
    owner: Optional[str] = None
    data_caches: List[str] = field(default_factory=list)
    fast_finality_indexes: List[str] = field(default_factory=list)
    winc: Optional[str] = None


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
