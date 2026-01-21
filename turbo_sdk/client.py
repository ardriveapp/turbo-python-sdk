import requests
from typing import BinaryIO, List, Dict, Optional, Union

from .types import (
    TurboUploadResponse,
    TurboBalanceResponse,
    ChunkingParams,
    ProgressCallback,
)
from .bundle import create_data, sign
from .chunked import ChunkedUploader


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
        data: Union[bytes, BinaryIO],
        tags: Optional[List[Dict[str, str]]] = None,
        on_progress: Optional[ProgressCallback] = None,
        chunking: Optional[ChunkingParams] = None,
        data_size: Optional[int] = None,
    ) -> TurboUploadResponse:
        """
        Upload data with automatic signing

        Args:
            data: Data to upload (bytes or file-like object)
            tags: Optional metadata tags
            on_progress: Optional callback for progress reporting (processed_bytes, total_bytes)
            chunking: Optional chunking configuration (defaults to auto mode)
            data_size: Required when data is a file-like object

        Returns:
            TurboUploadResponse with transaction details

        Raises:
            Exception: If upload fails
            UnderfundedError: If account balance is insufficient
        """
        # Determine data size
        if isinstance(data, bytes):
            size = len(data)
        elif data_size is not None:
            size = data_size
        else:
            raise ValueError("data_size is required when data is a file-like object")

        # Determine chunking mode
        params = chunking or ChunkingParams()
        use_chunked = self._should_use_chunked_upload(size, params)

        if use_chunked:
            return self._upload_chunked(data, size, tags, on_progress, params)
        else:
            return self._upload_single(data, size, tags, on_progress)

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
        data: Union[bytes, BinaryIO],
        size: int,
        tags: Optional[List[Dict[str, str]]],
        on_progress: Optional[ProgressCallback],
    ) -> TurboUploadResponse:
        """Upload using single request (for small files)"""
        # Read data if it's a stream
        if not isinstance(data, bytes):
            data = data.read()

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
            )
        else:
            raise Exception(f"Upload failed: {response.status_code} - {response.text}")

    def _upload_chunked(
        self,
        data: Union[bytes, BinaryIO],
        size: int,
        tags: Optional[List[Dict[str, str]]],
        on_progress: Optional[ProgressCallback],
        params: ChunkingParams,
    ) -> TurboUploadResponse:
        """Upload using chunked/multipart upload (for large files)"""
        # Read data if stream (needed for signing)
        # TODO: In future, implement true streaming with sign_stream
        if not isinstance(data, bytes):
            data = data.read()

        # Create and sign DataItem
        data_item = create_data(bytearray(data), self.signer, tags)
        sign(data_item, self.signer)

        # Get signed data
        signed_data = bytes(data_item.get_raw())

        # Create chunked uploader
        uploader = ChunkedUploader(
            upload_url=self.upload_url,
            token=self.token,
            chunking_params=params,
        )

        # Perform chunked upload
        return uploader.upload(
            data=signed_data,
            total_size=len(signed_data),
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
