"""
Turbo SDK for Python

A Python SDK for interacting with the Turbo datachain, supporting both
Ethereum and Arweave signers for permanent data storage.

Basic Usage:
    from turbo_sdk import Turbo, EthereumSigner, ArweaveSigner

    # For Ethereum
    signer = EthereumSigner("0x...")
    turbo = Turbo(signer, network="mainnet")

    # For Arweave
    signer = ArweaveSigner(jwk_dict)
    turbo = Turbo(signer, network="mainnet")

    # Upload data
    result = turbo.upload(b"Hello World", tags=[
        {"name": "Content-Type", "value": "text/plain"}
    ])
"""

from .client import Turbo
from .types import (
    TurboUploadResponse,
    TurboBalanceResponse,
    TurboUploadStatus,
    ChunkingParams,
    ChunkedUploadInit,
    ProgressCallback,
    ChunkingMode,
)
from .signers import EthereumSigner, ArweaveSigner
from .chunked import (
    ChunkedUploader,
    ChunkedUploadError,
    UnderfundedError,
    UploadValidationError,
    UploadFinalizationError,
)

__version__ = "0.1.0"

__all__ = [
    # Client
    "Turbo",
    # Response types
    "TurboUploadResponse",
    "TurboBalanceResponse",
    "TurboUploadStatus",
    # Chunking
    "ChunkingParams",
    "ChunkedUploadInit",
    "ChunkedUploader",
    "ProgressCallback",
    "ChunkingMode",
    # Errors
    "ChunkedUploadError",
    "UnderfundedError",
    "UploadValidationError",
    "UploadFinalizationError",
    # Signers
    "EthereumSigner",
    "ArweaveSigner",
]
