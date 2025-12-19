import pytest
from turbo_sdk.signers.ethereum import EthereumSigner


class TestEthereumSigner:
    """Test Ethereum signer functionality"""

    @pytest.fixture
    def test_private_key(self):
        """Test private key for consistent testing"""
        # Test private key (not for production use)
        return "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

    @pytest.fixture
    def signer(self, test_private_key):
        """Create test signer instance"""
        return EthereumSigner(test_private_key)

    def test_init_with_0x_prefix(self, test_private_key):
        """Test initialization with 0x prefix"""
        signer = EthereumSigner(test_private_key)

        assert signer.signature_type == 3
        assert signer.signature_length == 65
        assert signer.owner_length == 65
        assert len(signer.public_key) == 65
        assert signer.public_key[0] == 0x04  # Uncompressed public key prefix

    def test_init_without_0x_prefix(self, test_private_key):
        """Test initialization without 0x prefix"""
        private_key_no_prefix = test_private_key[2:]  # Remove 0x
        signer = EthereumSigner(private_key_no_prefix)

        assert signer.signature_type == 3
        assert len(signer.public_key) == 65
        assert signer.public_key[0] == 0x04

    def test_class_attributes(self):
        """Test class-level attributes"""
        assert EthereumSigner.signature_type == 3
        assert EthereumSigner.signature_length == 65
        assert EthereumSigner.owner_length == 65

    def test_public_key_format(self, signer):
        """Test public key format"""
        # Should be 65 bytes: 0x04 + 32 bytes x + 32 bytes y
        assert len(signer.public_key) == 65
        assert signer.public_key[0] == 0x04  # Uncompressed format
        assert isinstance(signer.public_key, bytes)

    def test_public_key_consistency(self, test_private_key):
        """Test that same private key produces same public key"""
        signer1 = EthereumSigner(test_private_key)
        signer2 = EthereumSigner(test_private_key)

        assert signer1.public_key == signer2.public_key

    def test_different_keys_different_public_keys(self):
        """Test that different private keys produce different public keys"""
        key1 = "0x1111111111111111111111111111111111111111111111111111111111111111"
        key2 = "0x2222222222222222222222222222222222222222222222222222222222222222"

        signer1 = EthereumSigner(key1)
        signer2 = EthereumSigner(key2)

        assert signer1.public_key != signer2.public_key

    def test_sign_basic(self, signer):
        """Test basic signing functionality"""
        message = bytearray(b"Hello, World!")
        signature = signer.sign(message)

        # Ethereum signatures are 65 bytes (r + s + v)
        assert len(signature) == 65
        assert isinstance(signature, bytearray)

    def test_sign_different_messages(self, signer):
        """Test that different messages produce different signatures"""
        message1 = bytearray(b"Hello, World!")
        message2 = bytearray(b"Goodbye, World!")

        sig1 = signer.sign(message1)
        sig2 = signer.sign(message2)

        assert sig1 != sig2
        assert len(sig1) == 65
        assert len(sig2) == 65

    def test_sign_same_message_consistent(self, signer):
        """Test that signing same message produces same signature"""
        message = bytearray(b"Consistent message")

        sig1 = signer.sign(message)
        sig2 = signer.sign(message)

        # Should produce the same signature for deterministic signing
        assert sig1 == sig2

    def test_sign_empty_message(self, signer):
        """Test signing empty message"""
        message = bytearray()
        signature = signer.sign(message)

        assert len(signature) == 65
        assert isinstance(signature, bytearray)

    def test_sign_large_message(self, signer):
        """Test signing large message"""
        # Create 1MB message
        large_message = bytearray(b"x" * (1024 * 1024))
        signature = signer.sign(large_message)

        assert len(signature) == 65
        assert isinstance(signature, bytearray)

    def test_sign_unicode_message(self, signer):
        """Test signing message with unicode characters"""
        message = bytearray("Hello 世界! 🚀".encode("utf-8"))
        signature = signer.sign(message)

        assert len(signature) == 65
        assert isinstance(signature, bytearray)

    def test_invalid_private_key_length(self):
        """Test initialization with invalid private key length"""
        # Too short
        short_key = "0x1234"
        with pytest.raises(Exception):
            EthereumSigner(short_key)

        # Too long
        long_key = "0x" + "1234567890abcdef" * 5  # 80 chars instead of 64
        with pytest.raises(Exception):
            EthereumSigner(long_key)

    def test_invalid_private_key_format(self):
        """Test initialization with invalid private key format"""
        # Invalid hex characters
        invalid_key = "0x123456789gabcdefg123456789abcdef123456789abcdef123456789abcdef"
        with pytest.raises(Exception):
            EthereumSigner(invalid_key)

    def test_signature_deterministic(self, test_private_key):
        """Test that signature is deterministic for same input"""
        message = bytearray(b"Deterministic test message")

        # Create multiple signers with same key
        signer1 = EthereumSigner(test_private_key)
        signer2 = EthereumSigner(test_private_key)

        sig1 = signer1.sign(message)
        sig2 = signer2.sign(message)

        # Should produce same signature
        assert sig1 == sig2

    def test_signature_components(self, signer):
        """Test signature has proper structure"""
        message = bytearray(b"Test signature structure")
        signature = signer.sign(message)

        # Should be 65 bytes: 32 bytes r + 32 bytes s + 1 byte v
        assert len(signature) == 65

        # Extract components (this is implementation detail, but good to verify structure)
        r = signature[0:32]
        s = signature[32:64]
        v = signature[64]

        # r and s should not be all zeros
        assert not all(b == 0 for b in r)
        assert not all(b == 0 for b in s)

        # v should be recovery id (typically 27, 28 or 0, 1 depending on implementation)
        assert isinstance(v, int)
