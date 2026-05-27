import json

import pytest
from base58 import b58encode, b58decode
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from turbo_sdk.signers.solana import SolanaSigner


# ---------------------------------------------------------------------------
# Fixed known-answer key material.
#
# RFC 8032 Ed25519 Test Vector 1 (https://www.rfc-editor.org/rfc/rfc8032).
# Solana's ed25519 is the standard RFC 8032 scheme, so these pin the
# derivation exactly. SECRET (seed) and the corresponding PUBLIC key are both
# published in the RFC; we assert the SDK derives PUBLIC from SECRET so a typo
# in either constant fails loudly rather than passing silently.
# ---------------------------------------------------------------------------
RFC8032_TEST1_SEED_HEX = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
RFC8032_TEST1_PUBLIC_HEX = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
# Signature over the empty message under the TEST 1 key (RFC 8032 §7.1).
RFC8032_TEST1_SIG_HEX = (
    "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
    "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
)


def _ref_b58encode(b: bytes) -> str:
    """Independent reference base58 (Bitcoin alphabet) encoder for cross-check."""
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = int.from_bytes(b, "big")
    out = ""
    while n > 0:
        n, rem = divmod(n, 58)
        out = alphabet[rem] + out
    # Preserve leading zero bytes as leading '1's.
    pad = 0
    for byte in b:
        if byte == 0:
            pad += 1
        else:
            break
    return "1" * pad + out


def _derive_pubkey(seed: bytes) -> bytes:
    priv = Ed25519PrivateKey.from_private_bytes(seed)
    return priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


@pytest.fixture
def seed() -> bytes:
    return bytes.fromhex(RFC8032_TEST1_SEED_HEX)


@pytest.fixture
def cli_keypair(seed) -> list:
    """Solana CLI id.json layout: 64 ints = 32-byte seed || 32-byte pubkey."""
    pub = _derive_pubkey(seed)
    return list(seed + pub)


@pytest.fixture
def signer(seed) -> SolanaSigner:
    return SolanaSigner(seed)


class TestSolanaSigner:
    """Solana signer functionality, mirroring the arweave/ethereum signer tests."""

    def test_class_attributes(self):
        # Solana uses signature type 2 (raw ED25519), not 4 (HexInjectedSolana).
        assert SolanaSigner.signature_type == 2
        assert SolanaSigner.signature_length == 64
        assert SolanaSigner.owner_length == 32

    def test_instance_attributes(self, signer):
        assert signer.signature_type == 2
        assert signer.signature_length == 64
        assert signer.owner_length == 32

    def test_public_key_is_32_bytes(self, signer):
        assert len(signer.public_key) == 32
        assert isinstance(signer.public_key, bytearray)

    def test_public_key_consistency(self, seed):
        assert SolanaSigner(seed).public_key == SolanaSigner(seed).public_key

    def test_different_seeds_different_public_keys(self):
        s1 = SolanaSigner(bytes([1] * 32))
        s2 = SolanaSigner(bytes([2] * 32))
        assert s1.public_key != s2.public_key

    # --- constructor format support ---------------------------------------

    def test_init_from_32_byte_seed(self, seed):
        s = SolanaSigner(seed)
        assert len(s.public_key) == 32

    def test_init_from_64_byte_secret_key(self, seed):
        pub = _derive_pubkey(seed)
        s = SolanaSigner(seed + pub)
        assert bytes(s.public_key) == pub

    def test_init_from_cli_keypair_list(self, cli_keypair, seed):
        s = SolanaSigner(cli_keypair)
        assert bytes(s.public_key) == _derive_pubkey(seed)

    def test_init_from_cli_keypair_json_string(self, cli_keypair, seed):
        s = SolanaSigner(json.dumps(cli_keypair))
        assert bytes(s.public_key) == _derive_pubkey(seed)

    def test_init_from_file(self, tmp_path, cli_keypair, seed):
        p = tmp_path / "id.json"
        p.write_text(json.dumps(cli_keypair))
        s = SolanaSigner.from_file(str(p))
        assert bytes(s.public_key) == _derive_pubkey(seed)

    def test_init_from_base58_secret_key(self, seed):
        pub = _derive_pubkey(seed)
        b58_secret = b58encode(seed + pub).decode()
        s = SolanaSigner(b58_secret)
        assert bytes(s.public_key) == pub

    def test_init_rejects_mismatched_pubkey(self, seed):
        wrong_pub = bytes([0] * 32)
        with pytest.raises(ValueError, match="does not match"):
            SolanaSigner(seed + wrong_pub)

    def test_init_rejects_bad_length(self):
        with pytest.raises(ValueError, match="Invalid Solana secret key length"):
            SolanaSigner(bytes([0] * 33))

    def test_init_rejects_bad_type(self):
        with pytest.raises(TypeError):
            SolanaSigner(12345)

    # --- signing -----------------------------------------------------------

    def test_sign_basic(self, signer):
        sig = signer.sign(bytearray(b"Hello, Solana!"))
        assert isinstance(sig, bytearray)
        assert len(sig) == 64

    def test_sign_empty_message(self, signer):
        sig = signer.sign(bytearray())
        assert len(sig) == 64

    def test_sign_deterministic(self, seed):
        msg = bytearray(b"deterministic")
        assert SolanaSigner(seed).sign(msg) == SolanaSigner(seed).sign(msg)

    def test_sign_different_messages_differ(self, signer):
        assert signer.sign(bytearray(b"a")) != signer.sign(bytearray(b"b"))

    def test_sign_verify_roundtrip(self, signer):
        msg = bytearray(b"round trip me")
        sig = signer.sign(msg)
        assert SolanaSigner.verify(signer.public_key, msg, sig) is True

    def test_verify_rejects_tampered_message(self, signer):
        sig = signer.sign(bytearray(b"original"))
        assert SolanaSigner.verify(signer.public_key, bytearray(b"tampered"), sig) is False

    def test_verify_rejects_tampered_signature(self, signer):
        msg = bytearray(b"original")
        sig = signer.sign(msg)
        sig[0] ^= 0xFF
        assert SolanaSigner.verify(signer.public_key, msg, sig) is False

    def test_verify_with_garbage_returns_bool_false(self):
        assert (
            SolanaSigner.verify(bytearray(b"\x00" * 32), bytearray(b"m"), bytearray(b"\x00" * 64))
            is False
        )

    # --- wallet address ----------------------------------------------------

    def test_wallet_address_is_base58_of_pubkey(self, signer):
        addr = signer.get_wallet_address()
        assert addr == b58encode(bytes(signer.public_key)).decode()
        # Round-trips back to the 32-byte public key.
        assert b58decode(addr) == bytes(signer.public_key)

    def test_known_answer_rfc8032_pubkey(self, seed):
        """Known-answer: RFC 8032 Test 1 seed derives the published public key."""
        s = SolanaSigner(seed)
        assert bytes(s.public_key).hex() == RFC8032_TEST1_PUBLIC_HEX

    def test_known_answer_rfc8032_address(self, seed):
        """Known-answer: the Solana address is base58(public key), pinned twice."""
        s = SolanaSigner(seed)
        expected_addr = b58encode(bytes.fromhex(RFC8032_TEST1_PUBLIC_HEX)).decode()
        assert s.get_wallet_address() == expected_addr
        # Cross-check the base58 against an independent reference encoder.
        assert s.get_wallet_address() == _ref_b58encode(bytes.fromhex(RFC8032_TEST1_PUBLIC_HEX))

    def test_known_answer_rfc8032_signature(self, seed):
        """Known-answer: signing the empty message yields the RFC 8032 signature."""
        s = SolanaSigner(seed)
        sig = s.sign(bytearray())
        assert len(RFC8032_TEST1_SIG_HEX) == 128  # 64-byte signature as hex
        assert bytes(sig).hex() == RFC8032_TEST1_SIG_HEX
        assert SolanaSigner.verify(s.public_key, bytearray(), sig) is True

    def test_address_base58_crosscheck_independent_encoder(self, signer):
        """Address from base58 lib must equal an independent reference encoder."""
        assert signer.get_wallet_address() == _ref_b58encode(bytes(signer.public_key))

    def test_create_signed_headers(self, signer):
        headers = signer.create_signed_headers()
        assert set(headers) == {"x-signature", "x-nonce", "x-public-key"}


class TestSolanaDataItem:
    """Full construct -> sign -> serialize -> parse -> verify loop for Solana."""

    @pytest.fixture
    def signer(self) -> SolanaSigner:
        return SolanaSigner(bytes.fromhex(RFC8032_TEST1_SEED_HEX))

    def test_dataitem_roundtrip(self, signer):
        from turbo_sdk.bundle.create import create_data
        from turbo_sdk.bundle.sign import sign, get_signature_data
        from turbo_sdk.bundle.dataitem import DataItem

        data = bytearray(b"solana data item payload")
        tags = [
            {"name": "Content-Type", "value": "application/octet-stream"},
            {"name": "App-Name", "value": "turbo-sdk-solana-test"},
        ]

        item = create_data(data, signer, tags=tags)
        sign(item, signer)

        # Re-parse from the raw bytes exactly as a downstream reader would.
        parsed = DataItem(bytearray(item.get_raw()))

        assert parsed.signature_type == 2
        assert len(parsed.raw_signature) == 64
        assert len(parsed.raw_owner) == 32
        assert bytes(parsed.raw_owner) == bytes(signer.public_key)
        assert parsed.raw_data == data
        assert parsed.get_tags_count() == 2
        assert parsed.is_valid() is True

        # The embedded ed25519 signature must verify against the embedded owner
        # over the data item's deep-hash signing bytes.
        signing_bytes = get_signature_data(parsed)
        assert SolanaSigner.verify(parsed.raw_owner, signing_bytes, parsed.raw_signature) is True

        # Wrong key must NOT verify (negative control).
        other = SolanaSigner(bytes([7] * 32))
        assert SolanaSigner.verify(other.public_key, signing_bytes, parsed.raw_signature) is False

    def test_dataitem_turbo_token_mapping(self, signer):
        """Turbo() must accept a SolanaSigner and map it to the 'solana' token."""
        from turbo_sdk.client import Turbo

        turbo = Turbo(signer)
        assert turbo.token == "solana"

    def test_dataitem_conformance_against_arbundles(self, signer):
        """Cross-implementation conformance against @dha-team/arbundles 1.0.4.

        The pinned signing-data (deep hash) and signature below were produced
        by arbundles' canonical ``SolanaSigner`` for the same fixed seed, tags,
        data, and anchor, then confirmed byte-identical to this SDK's output.
        arbundles is the library Turbo's upload backend validates with, so this
        is the authoritative regression guard. It specifically locks in
        signature type **2** (raw ED25519) — labeling Solana as type 4
        (HexInjectedSolana) produces a different deep hash and is rejected by
        the backend as "Invalid Data Item".
        """
        from turbo_sdk.bundle.create import create_data
        from turbo_sdk.bundle.sign import sign, get_signature_data

        anchor = bytes.fromhex(
            "0102030405060708090a0b0c0d0e0f10" "1112131415161718191a1b1c1d1e1f20"
        )
        # Cross-verified byte-for-byte against @dha-team/arbundles@1.0.4.
        EXPECTED_SIGDATA = (
            "82d7633c0ac2ede1bd88934a588fd4b6d6eb966aaec40e4953cc1fd6"
            "7958d4bf833e56e6b31bf33787c174ea51c3651a"
        )
        EXPECTED_SIG = (
            "c6148e3cc59ac617268f7e194dc4e3d15e7a0c1b18e270ef902f74b6"
            "be9d3f239b265f95483e37687783b01fbd979a69d3a2e69996865b6c"
            "856ea5dca1488f01"
        )

        item = create_data(
            bytearray(b"hello-solana"),
            signer,
            tags=[{"name": "App-Name", "value": "ario-solana-ref"}],
            anchor=anchor,
        )
        signing_bytes = get_signature_data(item)
        sign(item, signer)

        assert item.signature_type == 2
        assert bytes(signing_bytes).hex() == EXPECTED_SIGDATA
        assert bytes(item.raw_signature).hex() == EXPECTED_SIG
