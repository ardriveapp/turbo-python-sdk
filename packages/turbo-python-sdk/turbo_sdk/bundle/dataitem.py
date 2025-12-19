import struct
from .constants import SIG_CONFIG
from .utils import long_to_8_byte_array


class DataItem:
    def __init__(self, signature_type: int = 1):
        self.signature_type = signature_type
        self.signature = bytearray()
        self.owner = bytearray()
        self.target = bytearray(32)  # 32 bytes for target
        self.anchor = bytearray(32)  # 32 bytes for anchor
        self.tags = bytearray()
        self.data = bytearray()

        # Get signature config
        if signature_type in SIG_CONFIG:
            config = SIG_CONFIG[signature_type]
            self.signature = bytearray(config["sigLength"])
            self.owner = bytearray(config["pubLength"])
        else:
            raise ValueError(f"Unsupported signature type: {signature_type}")

    def get_raw(self) -> bytearray:
        """Serialize DataItem to bytes"""
        result = bytearray()

        # Signature type (2 bytes)
        result.extend(struct.pack("<H", self.signature_type))

        # Signature
        result.extend(self.signature)

        # Owner
        result.extend(self.owner)

        # Target (present flag + 32 bytes)
        has_target = any(b != 0 for b in self.target)
        result.append(1 if has_target else 0)
        if has_target:
            result.extend(self.target)

        # Anchor (present flag + 32 bytes)
        has_anchor = any(b != 0 for b in self.anchor)
        result.append(1 if has_anchor else 0)
        if has_anchor:
            result.extend(self.anchor)

        # Number of tags (8 bytes)
        result.extend(long_to_8_byte_array(len(self.tags)))

        # Tags data
        result.extend(self.tags)

        # Data
        result.extend(self.data)

        return result

    def id(self) -> str:
        """Get DataItem ID (SHA-256 of signature)"""
        import hashlib
        import base64

        hash_result = hashlib.sha256(self.signature).digest()
        return base64.urlsafe_b64encode(hash_result).decode().rstrip("=")

    def is_valid(self) -> bool:
        """Check if DataItem is valid"""
        # Check if signature has non-zero bytes (not just length)
        has_signature = any(b != 0 for b in self.signature)
        # Check if owner has non-zero bytes (not just length)
        has_owner = any(b != 0 for b in self.owner)
        # Check if data is present
        has_data = len(self.data) > 0

        return has_signature and has_owner and has_data
