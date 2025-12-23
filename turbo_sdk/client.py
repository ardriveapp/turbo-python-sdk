import requests
from typing import List, Dict, Optional
from .types import TurboUploadResponse, TurboBalanceResponse
from .bundle import create_data, sign


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

    def __init__(self, signer, network: str = "mainnet"):
        """
        Initialize Turbo client

        Args:
            signer: Signer instance (ArweaveSigner or EthereumSigner)
            network: Network ("mainnet" or "testnet")
        """
        self.signer = signer
        self.network = network
        self.upload_url = self.SERVICE_URLS[network]["upload"]
        self.payment_url = self.SERVICE_URLS[network]["payment"]

        # Determine token type from signer using lookup
        self.token = self.TOKEN_MAP.get(signer.signature_type)
        if not self.token:
            raise ValueError(f"Unsupported signer type: {signer.signature_type}")

    def upload(
        self, data: bytes, tags: Optional[List[Dict[str, str]]] = None
    ) -> TurboUploadResponse:
        """
        Upload data with automatic signing

        Args:
            data: Data to upload
            tags: Optional metadata tags

        Returns:
            TurboUploadResponse with transaction details

        Raises:
            Exception: If upload fails
        """

        # Create and sign DataItem
        data_item = create_data(bytearray(data), self.signer, tags)
        sign(data_item, self.signer)

        # Upload to Turbo endpoint
        url = f"{self.upload_url}/tx/{self.token}"
        raw_data = data_item.get_raw()
        headers = {"Content-Type": "application/octet-stream", "Content-Length": str(len(raw_data))}

        response = requests.post(url, data=raw_data, headers=headers)

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
