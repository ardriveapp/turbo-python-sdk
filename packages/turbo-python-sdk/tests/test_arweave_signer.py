import pytest
import base64
from unittest.mock import Mock, patch
from turbo_sdk.signers.arweave import ArweaveSigner


class TestArweaveSigner:
    """Test Arweave signer functionality"""

    def test_class_attributes(self):
        """Test class-level attributes"""
        assert ArweaveSigner.signature_type == 1
        assert ArweaveSigner.signature_length == 512
        assert ArweaveSigner.owner_length == 512

    def test_jwk_invalid_n_length(self):
        """Test JWK with invalid modulus length"""
        invalid_jwk = {
            "kty": "RSA",
            "n": base64.urlsafe_b64encode(b"x" * 256).decode().rstrip("="),  # Too short
            "e": base64.urlsafe_b64encode(b"\x01\x00\x01").decode().rstrip("="),
            "d": base64.urlsafe_b64encode(b"y" * 256).decode().rstrip("="),
            "p": base64.urlsafe_b64encode(b"p" * 128).decode().rstrip("="),
            "q": base64.urlsafe_b64encode(b"q" * 128).decode().rstrip("="),
            "dp": base64.urlsafe_b64encode(b"d" * 128).decode().rstrip("="),
            "dq": base64.urlsafe_b64encode(b"e" * 128).decode().rstrip("="),
            "qi": base64.urlsafe_b64encode(b"i" * 128).decode().rstrip("="),
        }

        with pytest.raises(ValueError, match="Invalid Arweave public key length"):
            ArweaveSigner(invalid_jwk)

    def test_jwk_missing_components(self):
        """Test JWK with missing components"""
        incomplete_jwk = {
            "kty": "RSA",
            "n": base64.urlsafe_b64encode(b"x" * 512).decode().rstrip("="),
            "e": base64.urlsafe_b64encode(b"\x01\x00\x01").decode().rstrip("="),
            # Missing d, p, q, dp, dq, qi
        }

        with pytest.raises(KeyError):
            ArweaveSigner(incomplete_jwk)

    @patch("turbo_sdk.signers.arweave.rsa.RSAPrivateNumbers")
    def test_init_with_valid_jwk(self, mock_rsa_numbers):
        """Test initialization with valid JWK"""
        # Mock RSA key creation
        mock_private_key = Mock()
        mock_rsa_instance = Mock()
        mock_rsa_instance.private_key.return_value = mock_private_key
        mock_rsa_numbers.return_value = mock_rsa_instance

        test_jwk = {
            "kty": "RSA",
            "n": base64.urlsafe_b64encode(b"n" * 512).decode().rstrip("="),  # 512-byte modulus
            "e": base64.urlsafe_b64encode(b"\x01\x00\x01").decode().rstrip("="),  # 65537
            "d": base64.urlsafe_b64encode(b"d" * 512).decode().rstrip("="),  # private exponent
            "p": base64.urlsafe_b64encode(b"p" * 256).decode().rstrip("="),  # prime p
            "q": base64.urlsafe_b64encode(b"q" * 256).decode().rstrip("="),  # prime q
            "dp": base64.urlsafe_b64encode(b"dp" * 128).decode().rstrip("="),  # d mod (p-1)
            "dq": base64.urlsafe_b64encode(b"dq" * 128).decode().rstrip("="),  # d mod (q-1)
            "qi": base64.urlsafe_b64encode(b"qi" * 128).decode().rstrip("="),  # q^-1 mod p
        }

        signer = ArweaveSigner(test_jwk)

        assert signer.signature_type == 1
        assert signer.signature_length == 512
        assert signer.owner_length == 512
        assert len(signer.public_key) == 512
        assert signer.jwk == test_jwk
        assert signer.private_key == mock_private_key

    @patch("turbo_sdk.signers.arweave.rsa.RSAPrivateNumbers")
    def test_sign_method_interface(self, mock_rsa_numbers):
        """Test sign method interface"""
        # Mock RSA key creation and signing
        mock_signature = b"x" * 512  # 512-byte signature
        mock_private_key = Mock()
        mock_private_key.sign.return_value = mock_signature
        mock_rsa_instance = Mock()
        mock_rsa_instance.private_key.return_value = mock_private_key
        mock_rsa_numbers.return_value = mock_rsa_instance

        test_jwk = {
            "kty": "RSA",
            "n": base64.urlsafe_b64encode(b"n" * 512).decode().rstrip("="),
            "e": base64.urlsafe_b64encode(b"\x01\x00\x01").decode().rstrip("="),
            "d": base64.urlsafe_b64encode(b"d" * 512).decode().rstrip("="),
            "p": base64.urlsafe_b64encode(b"p" * 256).decode().rstrip("="),
            "q": base64.urlsafe_b64encode(b"q" * 256).decode().rstrip("="),
            "dp": base64.urlsafe_b64encode(b"dp" * 128).decode().rstrip("="),
            "dq": base64.urlsafe_b64encode(b"dq" * 128).decode().rstrip("="),
            "qi": base64.urlsafe_b64encode(b"qi" * 128).decode().rstrip("="),
        }

        signer = ArweaveSigner(test_jwk)
        message = bytearray(b"Hello, Arweave!")

        signature = signer.sign(message)

        assert isinstance(signature, bytearray)
        assert len(signature) == 512
        assert bytes(signature) == mock_signature

        # Verify the mock was called correctly
        mock_private_key.sign.assert_called_once()

    def test_verify_static_method_interface(self):
        """Test verify static method interface"""
        # Test the method exists and has correct signature
        pubkey = bytearray(b"x" * 512)
        message = bytearray(b"test message")
        signature = bytearray(b"y" * 512)

        # This will likely return False due to invalid data, but tests interface
        result = ArweaveSigner.verify(pubkey, message, signature)
        assert isinstance(result, bool)

    def test_verify_with_invalid_data(self):
        """Test verify with clearly invalid data"""
        pubkey = bytearray(b"\x00" * 512)  # Invalid public key
        message = bytearray(b"test message")
        signature = bytearray(b"\x00" * 512)  # Invalid signature

        # Should return False for invalid data
        result = ArweaveSigner.verify(pubkey, message, signature)
        assert result is False
