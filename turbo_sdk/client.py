import io
import logging
from typing import BinaryIO, List, Dict, Optional, Union

import requests

from .types import (
    TurboUploadResponse,
    TurboBalanceResponse,
    ChunkingParams,
    ProgressCallback,
)
from .bundle import create_data, sign, StreamingDataItem, StreamFactory
from .chunked import ChunkedUploader


logger = logging.getLogger(__name__)


class Turbo:
    """Main Turbo client for uploading data and managing payments"""

    SERVICE_URLS = {
        "mainnet": {"upload": "https://upload.ardrive.io", "payment": "https://payment.ardrive.io"},
        "testnet": {
            "upload": "https://upload.ardrive.dev",
            "payment": "https://payment.ardrive.dev",
        },
    }

    # Map signature types to token names
    TOKEN_MAP = {
        1: "arweave",  # Arweave RSA-PSS
        3: "ethereum",  # Ethereum ECDSA
    }

    def __init__(
        self,
        signer,
        network: str = "mainnet",
        upload_url: Optional[str] = None,
        payment_url: Optional[str] = None,
    ):
        """
        Initialize Turbo client

        Args:
            signer: Signer instance (ArweaveSigner or EthereumSigner)
            network: Network ("mainnet" or "testnet") - used for default URLs
            upload_url: Optional custom upload service URL (overrides network default)
            payment_url: Optional custom payment service URL (overrides network default)
        """
        self.signer = signer
        self.network = network
        self.upload_url = upload_url or self.SERVICE_URLS[network]["upload"]
        self.payment_url = payment_url or self.SERVICE_URLS[network]["payment"]

        # Determine token type from signer using lookup
        self.token = self.TOKEN_MAP.get(signer.signature_type)
        if not self.token:
            raise ValueError(f"Unsupported signer type: {signer.signature_type}")

    # Default threshold for auto-chunking (5 MiB)
    CHUNKING_THRESHOLD = 5 * 1024 * 1024

    def upload(
        self,
        data: Optional[Union[bytes, BinaryIO]] = None,
        tags: Optional[List[Dict[str, str]]] = None,
        on_progress: Optional[ProgressCallback] = None,
        chunking: Optional[ChunkingParams] = None,
        data_size: Optional[int] = None,
        stream_factory: Optional[StreamFactory] = None,
    ) -> TurboUploadResponse:
        """
        Upload data with automatic signing

        Args:
            data: Data to upload (bytes or file-like object). Mutually exclusive
                  with stream_factory.
            tags: Optional metadata tags
            on_progress: Optional callback for progress reporting (processed_bytes, total_bytes)
            chunking: Optional chunking configuration (defaults to auto mode)
            data_size: Required when using stream_factory or file-like object
            stream_factory: A callable that returns a fresh BinaryIO stream each time.
                           Useful for non-seekable streams or when you want control
                           over stream lifecycle. Mutually exclusive with data.

        Returns:
            TurboUploadResponse with transaction details

        Raises:
            Exception: If upload fails
            UnderfundedError: If account balance is insufficient
        """
        # Validate inputs
        if data is not None and stream_factory is not None:
            raise ValueError("Cannot specify both data and stream_factory")
        if data is None and stream_factory is None:
            raise ValueError("Must specify either data or stream_factory")

        # Determine data size and create stream factory
        if stream_factory is not None:
            if data_size is None:
                raise ValueError("data_size is required when using stream_factory")
            size = data_size
            factory = stream_factory
        elif isinstance(data, bytes):
            size = len(data)

            def factory():
                return io.BytesIO(data)

        else:
            # data is a BinaryIO – read into bytes so the factory can
            # produce independent streams (sign() closes the signing stream).
            if data_size is None:
                raise ValueError("data_size is required when data is a file-like object")
            size = data_size
            if size >= self.CHUNKING_THRESHOLD:
                logger.warning(
                    "Large file (%d bytes) passed as data will be read entirely "
                    "into memory. Consider providing stream_factory instead, e.g. "
                    "turbo.upload(stream_factory=lambda: open('my-file.bin', 'rb'), "
                    "data_size=%d)",
                    size,
                    size,
                )
            raw = data.read()

            def factory():
                return io.BytesIO(raw)

        # Determine chunking mode
        params = chunking or ChunkingParams()
        use_chunked = self._should_use_chunked_upload(size, params)

        if use_chunked:
            return self._upload_chunked(factory, size, tags, on_progress, params)
        else:
            return self._upload_single(factory, size, tags, on_progress)

    def _should_use_chunked_upload(self, size: int, params: ChunkingParams) -> bool:
        """Determine if chunked upload should be used"""
        if params.chunking_mode == "disabled":
            return False
        if params.chunking_mode == "force":
            return True
        # Auto mode: use chunked for files >= threshold
        return size >= self.CHUNKING_THRESHOLD

    def _upload_single(
        self,
        stream_factory: StreamFactory,
        size: int,
        tags: Optional[List[Dict[str, str]]],
        on_progress: Optional[ProgressCallback],
    ) -> TurboUploadResponse:
        """Upload using single request (for small files)"""
        # Read all data from stream
        stream = stream_factory()
        data = stream.read()
        if hasattr(stream, "close"):
            stream.close()

        # Create and sign DataItem
        data_item = create_data(bytearray(data), self.signer, tags)
        sign(data_item, self.signer)

        # Report signing complete (half the work)
        if on_progress:
            on_progress(size // 2, size)

        # Upload to Turbo endpoint
        url = f"{self.upload_url}/tx/{self.token}"
        raw_data = data_item.get_raw()
        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(raw_data)),
        }

        response = requests.post(url, data=raw_data, headers=headers)

        if on_progress:
            on_progress(size, size)

        if response.status_code == 200:
            result = response.json()
            return TurboUploadResponse(
                id=result["id"],
                owner=result["owner"],
                data_caches=result.get("dataCaches", []),
                fast_finality_indexes=result.get("fastFinalityIndexes", []),
                winc=result.get("winc", "0"),
                timestamp=result.get("timestamp"),
                signature=result.get("signature"),
                public=result.get("public"),
                version=result.get("version"),
                deadline_height=result.get("deadlineHeight"),
            )
        else:
            raise Exception(f"Upload failed: {response.status_code} - {response.text}")

    def _upload_chunked(
        self,
        stream_factory: StreamFactory,
        size: int,
        tags: Optional[List[Dict[str, str]]],
        on_progress: Optional[ProgressCallback],
        params: ChunkingParams,
    ) -> TurboUploadResponse:
        """Upload using chunked/multipart upload (for large files)"""
        # Use StreamingDataItem for all chunked uploads
        # This signs data by streaming through it, avoiding memory duplication
        streaming_item = StreamingDataItem(
            stream_factory=stream_factory,
            data_size=size,
            tags=tags,
        )

        # Sign the data (streaming) and build the header
        streaming_item.sign(self.signer)
        total_size = streaming_item.total_size

        # Create chunked uploader
        uploader = ChunkedUploader(
            upload_url=self.upload_url,
            token=self.token,
            chunking_params=params,
        )

        # Upload using the streaming item as a file-like object
        return uploader.upload(
            data=streaming_item,
            total_size=total_size,
            on_progress=on_progress,
        )

    def get_balance(self, address: Optional[str] = None) -> TurboBalanceResponse:
        """
        Get winston credit balance using signed request

        Args:
            address: Address to check balance for (defaults to signer address)

        Returns:
            TurboBalanceResponse with balance details
        """
        # Use the /balance endpoint with signed headers
        url = f"{self.payment_url}/v1/balance"

        try:
            if address:
                # If address provided, use query parameter (no signature needed)
                params = {"address": address}
                response = requests.get(url, params=params)
            else:
                # Use signed headers for authenticated request
                headers = self.signer.create_signed_headers()
                response = requests.get(url, headers=headers)

            response.raise_for_status()
            result = response.json()

            return TurboBalanceResponse(
                winc=result.get("winc", "0"),
                controlled_winc=result.get("controlledWinc", "0"),
                effective_balance=result.get("effectiveBalance", "0"),
            )
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                # Return zero balance for unfunded/unregistered wallets
                return TurboBalanceResponse(
                    winc="0",
                    controlled_winc="0",
                    effective_balance="0",
                )
            else:
                # Re-raise other HTTP errors
                raise

    def get_upload_price(self, byte_count: int) -> int:
        """
        Get upload cost in winston credits

        Args:
            byte_count: Number of bytes to upload

        Returns:
            Cost in winston credits
        """
        url = f"{self.payment_url}/v1/price/{self.token}/{byte_count}"

        # Add signed headers for authenticated request
        headers = self.signer.create_signed_headers()
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        result = response.json()

        # Handle different response formats
        if isinstance(result, dict):
            return int(result.get("winc", "0"))
        else:
            # If result is a simple value, return it directly
            return int(result)
