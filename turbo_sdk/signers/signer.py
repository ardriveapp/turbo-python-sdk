from abc import abstractmethod
from typing import Any, Dict
import base64
import secrets


class Signer:

    @property
    @abstractmethod
    def public_key(self) -> bytearray:
        pass

    @property
    @abstractmethod
    def signature_type(self) -> int:
        pass

    @property
    @abstractmethod
    def signature_length(self) -> int:
        pass

    @property
    @abstractmethod
    def owner_length(self) -> int:
        pass

    @abstractmethod
    def sign(self, message: bytearray, **opts: Any) -> bytearray:
        pass

    @abstractmethod
    # @staticmethod
    def verify(pubkey: bytearray, message: bytearray, signature: bytearray, **opts: Any) -> bool:
        pass

    @abstractmethod
    def get_wallet_address(self) -> str:
        pass

    def create_signed_headers(self) -> Dict[str, str]:
        """Create signed headers for authenticated API requests"""
        nonce = secrets.token_hex(16)
        message = f"{nonce}".encode("utf-8")
        signature = self.sign(bytearray(message))
        signature_b64 = base64.b64encode(signature).decode("utf-8")
        public_key_b64 = base64.b64encode(self.public_key).decode("utf-8")
        return {"x-signature": signature_b64, "x-nonce": nonce, "x-public-key": public_key_b64}
