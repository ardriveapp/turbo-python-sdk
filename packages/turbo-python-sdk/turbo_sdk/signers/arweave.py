from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
import base64


class ArweaveSigner:
    signature_type = 1
    signature_length = 512
    owner_length = 512

    def __init__(self, jwk: dict):
        """
        Initialize with Arweave JWK (JSON Web Key)

        Args:
            jwk: Arweave wallet JWK as dictionary
        """
        self.jwk = jwk
        self.public_key = self._jwk_to_public_key_bytes(jwk)  # Validate length first
        self.private_key = self._jwk_to_rsa_key(jwk)

    def _jwk_to_rsa_key(self, jwk: dict):
        """Convert JWK to RSA private key"""

        def b64url_decode(s):
            padding = 4 - len(s) % 4
            if padding != 4:
                s += "=" * padding
            return base64.urlsafe_b64decode(s)

        # Extract RSA components
        n = int.from_bytes(b64url_decode(jwk["n"]), "big")
        e = int.from_bytes(b64url_decode(jwk["e"]), "big")
        d = int.from_bytes(b64url_decode(jwk["d"]), "big")
        p = int.from_bytes(b64url_decode(jwk["p"]), "big")
        q = int.from_bytes(b64url_decode(jwk["q"]), "big")

        # Create RSA private key
        return rsa.RSAPrivateNumbers(
            p=p,
            q=q,
            d=d,
            dmp1=int.from_bytes(b64url_decode(jwk["dp"]), "big"),
            dmq1=int.from_bytes(b64url_decode(jwk["dq"]), "big"),
            iqmp=int.from_bytes(b64url_decode(jwk["qi"]), "big"),
            public_numbers=rsa.RSAPublicNumbers(e=e, n=n),
        ).private_key()

    def _jwk_to_public_key_bytes(self, jwk: dict) -> bytearray:
        """Extract 512-byte public key from JWK"""

        def b64url_decode(s):
            padding = 4 - len(s) % 4
            if padding != 4:
                s += "=" * padding
            return base64.urlsafe_b64decode(s)

        n_bytes = b64url_decode(jwk["n"])
        if len(n_bytes) != 512:
            raise ValueError(f"Invalid Arweave public key length: {len(n_bytes)} (expected 512)")
        return bytearray(n_bytes)

    def sign(self, message: bytearray) -> bytearray:
        """Sign using RSA-PSS SHA-256"""
        signature = self.private_key.sign(
            bytes(message),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        return bytearray(signature)

    @staticmethod
    def verify(pubkey: bytearray, message: bytearray, signature: bytearray) -> bool:
        """Verify RSA-PSS signature"""
        try:
            # Convert modulus bytes to RSA public key
            n = int.from_bytes(pubkey, "big")
            e = 65537  # Arweave always uses e=65537
            public_key = rsa.RSAPublicNumbers(e, n).public_key()

            public_key.verify(
                bytes(signature),
                bytes(message),
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False
