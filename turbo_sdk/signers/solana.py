import json
from typing import Any, Union

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
from base58 import b58encode, b58decode

from turbo_sdk.signers.signer import Signer
from turbo_sdk.bundle.constants import SIG_CONFIG


class SolanaSigner(Signer):
    """
    Solana (ed25519) signer for ANS-104 data items.

    Solana accounts are ed25519 keypairs; the on-chain address is simply the
    base58 encoding of the 32-byte ed25519 public key. This signer produces
    signature_type 2 (raw ED25519) data items, which Turbo bills as the
    ``solana`` token.

    Accepted secret-key formats (passed to the constructor):

    * **Solana CLI keypair** (``id.json``): a JSON array of 64 integers, being
      the 32-byte ed25519 seed (private scalar source) followed by the 32-byte
      public key. May be supplied as the parsed ``list``/``bytes`` itself or as
      a path/JSON string (see ``from_file`` / the constructor's ``str`` branch).
    * **Raw 64-byte secret key**: ``bytes``/``bytearray`` of seed(32) ‖ pub(32),
      i.e. the same layout the CLI file decodes to.
    * **Raw 32-byte seed**: ``bytes``/``bytearray`` of just the ed25519 seed;
      the public key is derived from it.
    * **Base58-encoded secret key** (``str``): a base58 string decoding to a
      32- or 64-byte secret key, the form exported by Phantom and other wallets.

    Only the 32-byte seed is cryptographically required; when a 64-byte key is
    supplied the trailing public key is used to sanity-check the derivation and
    a ``ValueError`` is raised on mismatch.
    """

    public_key = (
        None  # set in __init__; shadows the base abstract property (matches EthereumSigner)
    )
    # Solana data items use signature type 2 (raw ED25519 over the deep hash),
    # NOT type 4. Type 4 is HexInjectedSolanaSigner — a browser-injected-wallet
    # variant that signs a hex-encoded message, which the backend validates
    # differently. The canonical server-side Solana signer (arbundles
    # SolanaSigner) is type 2; Turbo bills type-2 ed25519 items uploaded to
    # /tx/solana as the solana token.
    signature_type = 2
    signature_length = SIG_CONFIG[2]["sigLength"]  # 64
    owner_length = SIG_CONFIG[2]["pubLength"]  # 32

    def __init__(self, secret_key: Union[bytes, bytearray, list, str]):
        seed, embedded_pub = self._normalize_secret_key(secret_key)

        self._private_key = Ed25519PrivateKey.from_private_bytes(bytes(seed))
        derived_pub = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        if embedded_pub is not None and bytes(embedded_pub) != derived_pub:
            raise ValueError(
                "Solana secret key public-key half does not match the key "
                "derived from the seed (corrupt or mismatched keypair)"
            )

        self.public_key = bytearray(derived_pub)

    @classmethod
    def from_file(cls, path: str) -> "SolanaSigner":
        """Load a Solana CLI ``id.json`` keypair file (JSON array of ints)."""
        with open(path, "r") as f:
            return cls(json.load(f))

    @staticmethod
    def _normalize_secret_key(secret_key):
        """
        Return ``(seed32, embedded_pub_or_None)`` from any accepted input.
        """
        # JSON array (Solana CLI id.json), already parsed or as a JSON string.
        if isinstance(secret_key, str):
            stripped = secret_key.strip()
            if stripped.startswith("["):
                secret_key = json.loads(stripped)
            else:
                # Base58-encoded secret key (Phantom export, etc.)
                secret_key = b58decode(stripped)

        if isinstance(secret_key, list):
            secret_key = bytes(secret_key)

        if isinstance(secret_key, (bytes, bytearray)):
            raw = bytes(secret_key)
            if len(raw) == 64:
                return raw[:32], raw[32:]
            if len(raw) == 32:
                return raw, None
            raise ValueError(
                f"Invalid Solana secret key length: {len(raw)} "
                "(expected 32-byte seed or 64-byte secret key)"
            )

        raise TypeError(
            "Unsupported Solana secret key type: "
            f"{type(secret_key).__name__} (expected bytes, list, or str)"
        )

    def sign(self, message: bytearray, **opts: Any) -> bytearray:
        """
        Sign the raw message bytes with ed25519.

        Ed25519 hashes internally (SHA-512), so the message must be passed
        through verbatim with no extra pre-hashing — this matches the
        arbundles / ANS-104 deep-hash signing flow.
        """
        signature = self._private_key.sign(bytes(message))
        return bytearray(signature)

    @staticmethod
    def verify(pubkey: bytearray, message: bytearray, signature: bytearray, **opts: Any) -> bool:
        """Verify an ed25519 signature against a 32-byte public key."""
        try:
            public_key = Ed25519PublicKey.from_public_bytes(bytes(pubkey))
            public_key.verify(bytes(signature), bytes(message))
            return True
        except (InvalidSignature, ValueError):
            return False

    def get_wallet_address(self) -> str:
        """
        The Solana address is the base58 encoding of the 32-byte public key.
        """
        return b58encode(bytes(self.public_key)).decode("utf-8")
