import io
import os
import pytest
from unittest.mock import Mock, patch
import requests
from turbo_sdk import Turbo
from turbo_sdk.signers.ethereum import EthereumSigner
from turbo_sdk.signers.arweave import ArweaveSigner


class TestTurbo:
    """Test Turbo class functionality (non-network tests)"""

    @pytest.fixture
    def ethereum_signer(self):
        """Mock Ethereum signer"""
        signer = Mock()
        signer.signature_type = 3
        signer.public_key = b"\x04" + b"x" * 64  # 65 bytes total
        signer.get_wallet_address.return_value = "0x1234567890abcdef1234567890abcdef12345678"
        return signer

    @pytest.fixture
    def arweave_signer(self):
        """Mock Arweave signer"""
        signer = Mock()
        signer.signature_type = 1
        signer.public_key = bytearray(b"y" * 512)  # 512 bytes
        signer.get_wallet_address.return_value = "mock_arweave_address_base64url"
        return signer

    def test_init_with_ethereum_signer(self, ethereum_signer):
        """Test initialization with Ethereum signer"""
        turbo = Turbo(ethereum_signer, network="mainnet")

        assert turbo.signer == ethereum_signer
        assert turbo.network == "mainnet"
        assert turbo.token == "ethereum"
        assert turbo.upload_url == "https://upload.ardrive.io"
        assert turbo.payment_url == "https://payment.ardrive.io"

    def test_init_with_arweave_signer(self, arweave_signer):
        """Test initialization with Arweave signer"""
        turbo = Turbo(arweave_signer, network="testnet")

        assert turbo.signer == arweave_signer
        assert turbo.network == "testnet"
        assert turbo.token == "arweave"
        assert turbo.upload_url == "https://upload.ardrive.dev"
        assert turbo.payment_url == "https://payment.ardrive.dev"

    def test_init_with_unsupported_signer(self):
        """Test initialization with unsupported signer type"""
        unsupported_signer = Mock()
        unsupported_signer.signature_type = 99  # Invalid type

        with pytest.raises(ValueError, match="Unsupported signer type: 99"):
            Turbo(unsupported_signer)

    def test_default_network(self, ethereum_signer):
        """Test default network is mainnet"""
        turbo = Turbo(ethereum_signer)

        assert turbo.network == "mainnet"
        assert "ardrive.io" in turbo.upload_url  # mainnet URLs

    def test_testnet_urls(self, ethereum_signer):
        """Test testnet URLs are used correctly"""
        turbo = Turbo(ethereum_signer, network="testnet")

        assert "ardrive.dev" in turbo.upload_url
        assert "ardrive.dev" in turbo.payment_url

    def test_mainnet_urls(self, arweave_signer):
        """Test mainnet URLs are used correctly"""
        turbo = Turbo(arweave_signer, network="mainnet")

        assert "ardrive.io" in turbo.upload_url
        assert "ardrive.io" in turbo.payment_url

    def test_token_detection_ethereum(self, ethereum_signer):
        """Test token detection for Ethereum signer"""
        turbo = Turbo(ethereum_signer)
        assert turbo.token == "ethereum"

    def test_token_detection_arweave(self, arweave_signer):
        """Test token detection for Arweave signer"""
        turbo = Turbo(arweave_signer)
        assert turbo.token == "arweave"

    def test_get_wallet_address_ethereum(self):
        """Test wallet address generation for Ethereum signer"""
        test_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        signer = EthereumSigner(test_key)

        address = signer.get_wallet_address()

        # Should be 0x + 40 hex chars (checksum address)
        assert address.startswith("0x")
        assert len(address) == 42

    @patch("turbo_sdk.signers.arweave.rsa.RSAPrivateNumbers")
    def test_get_wallet_address_arweave(self, mock_rsa_numbers):
        """Test wallet address generation for Arweave signer"""
        import base64

        # Mock RSA key creation
        mock_private_key = Mock()
        mock_rsa_instance = Mock()
        mock_rsa_instance.private_key.return_value = mock_private_key
        mock_rsa_numbers.return_value = mock_rsa_instance

        test_arweave_jwk = {
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

        signer = ArweaveSigner(test_arweave_jwk)
        address = signer.get_wallet_address()

        # Should be base64url encoded (no padding)
        assert isinstance(address, str)
        assert len(address) > 0
        # Base64url chars only
        import string

        valid_chars = string.ascii_letters + string.digits + "-_"
        assert all(c in valid_chars for c in address)

    def test_service_urls_structure(self):
        """Test SERVICE_URLS has correct structure"""
        urls = Turbo.SERVICE_URLS

        assert "mainnet" in urls
        assert "testnet" in urls

        for network, endpoints in urls.items():
            assert "upload" in endpoints
            assert "payment" in endpoints
            assert endpoints["upload"].startswith("https://")
            assert endpoints["payment"].startswith("https://")

    def test_real_ethereum_signer_integration(self):
        """Test integration with real EthereumSigner"""
        # Use a test private key
        test_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        signer = EthereumSigner(test_key)

        turbo = Turbo(signer)

        assert turbo.token == "ethereum"
        assert turbo.signer == signer
        assert turbo.network == "mainnet"

    @patch("turbo_sdk.signers.arweave.rsa.RSAPrivateNumbers")
    def test_real_arweave_signer_integration(self, mock_rsa_numbers):
        """Test integration with real ArweaveSigner"""
        # Mock RSA key creation
        mock_private_key = Mock()
        mock_rsa_instance = Mock()
        mock_rsa_instance.private_key.return_value = mock_private_key
        mock_rsa_numbers.return_value = mock_rsa_instance

        import base64

        test_arweave_jwk = {
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

        signer = ArweaveSigner(test_arweave_jwk)
        turbo = Turbo(signer, network="testnet")

        assert turbo.token == "arweave"
        assert turbo.signer == signer
        assert turbo.network == "testnet"

    def test_create_signed_headers(self):
        """Test creation of signed headers on signer"""
        import base64

        test_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        signer = EthereumSigner(test_key)

        headers = signer.create_signed_headers()

        # Check headers exist
        assert "x-signature" in headers
        assert "x-nonce" in headers
        assert "x-public-key" in headers

        # Check values are base64 encoded strings
        assert isinstance(headers["x-signature"], str)
        assert isinstance(headers["x-nonce"], str)
        assert isinstance(headers["x-public-key"], str)

        # Verify nonce is hex string
        nonce = headers["x-nonce"]
        assert len(nonce) == 32  # 16 bytes as hex = 32 chars
        assert all(c in "0123456789abcdef" for c in nonce)

        # Verify we can decode the base64 values
        try:
            base64.b64decode(headers["x-signature"])
            base64.b64decode(headers["x-public-key"])
        except Exception:
            pytest.fail("Headers should contain valid base64 data")

    @patch("turbo_sdk.client.requests.get")
    def test_get_balance_404_returns_zero(self, mock_get, ethereum_signer):
        """Test that 404 errors return zero balance instead of raising"""
        # Mock the signer's sign method
        ethereum_signer.sign.return_value = bytearray(b"mock_signature")

        turbo = Turbo(ethereum_signer)

        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)
        mock_get.return_value = mock_response

        # Should return zero balance, not raise
        balance = turbo.get_balance()
        assert balance.winc == "0"
        assert balance.controlled_winc == "0"
        assert balance.effective_balance == "0"

    @patch("turbo_sdk.client.requests.get")
    def test_get_balance_other_errors_raise(self, mock_get, ethereum_signer):
        """Test that non-404 errors are still raised"""
        # Mock the signer's sign method
        ethereum_signer.sign.return_value = bytearray(b"mock_signature")

        turbo = Turbo(ethereum_signer)

        # Mock 500 response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)
        mock_get.return_value = mock_response

        # Should raise the error
        with pytest.raises(requests.HTTPError):
            turbo.get_balance()


class TestTurboUpload:
    """Test Turbo upload method with different input types"""

    # Test private key (not a real key, just for testing)
    TEST_PRIVATE_KEY = "0x" + "ab" * 32

    @pytest.fixture
    def signer(self):
        """Create a real Ethereum signer for testing."""
        return EthereumSigner(self.TEST_PRIVATE_KEY)

    @pytest.fixture
    def turbo(self, signer):
        """Create a Turbo client for testing."""
        return Turbo(signer, network="testnet")

    @patch("turbo_sdk.client.requests.post")
    def test_upload_with_bytes(self, mock_post, turbo):
        """Test upload with raw bytes data"""
        test_data = b"Hello, Turbo!" * 10

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test_tx_id",
            "owner": "test_owner",
            "dataCaches": ["cache1"],
            "fastFinalityIndexes": ["index1"],
            "winc": "1000",
        }
        mock_post.return_value = mock_response

        result = turbo.upload(data=test_data, tags=[{"name": "Test", "value": "bytes"}])

        assert result.id == "test_tx_id"
        assert result.owner == "test_owner"
        mock_post.assert_called_once()

    @patch("turbo_sdk.client.requests.post")
    def test_upload_with_stream(self, mock_post, turbo):
        """Test upload with file-like stream object"""
        test_data = b"Hello, streaming Turbo!" * 10
        stream = io.BytesIO(test_data)

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test_tx_id_stream",
            "owner": "test_owner",
            "dataCaches": [],
            "fastFinalityIndexes": [],
            "winc": "500",
        }
        mock_post.return_value = mock_response

        result = turbo.upload(
            data=stream,
            data_size=len(test_data),
            tags=[{"name": "Test", "value": "stream"}],
        )

        assert result.id == "test_tx_id_stream"
        mock_post.assert_called_once()

    @patch("turbo_sdk.client.requests.post")
    def test_upload_with_stream_factory(self, mock_post, turbo):
        """Test upload with stream_factory callable"""
        test_data = b"Hello, factory Turbo!" * 10
        call_count = [0]

        def stream_factory():
            call_count[0] += 1
            return io.BytesIO(test_data)

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test_tx_id_factory",
            "owner": "test_owner",
            "dataCaches": [],
            "fastFinalityIndexes": [],
            "winc": "750",
        }
        mock_post.return_value = mock_response

        result = turbo.upload(
            stream_factory=stream_factory,
            data_size=len(test_data),
            tags=[{"name": "Test", "value": "factory"}],
        )

        assert result.id == "test_tx_id_factory"
        # Factory should have been called at least once
        assert call_count[0] >= 1
        mock_post.assert_called_once()

    @patch("turbo_sdk.client.requests.post")
    def test_upload_with_file(self, mock_post, turbo, tmp_path):
        """Test upload with actual file from disk"""
        # Create a temporary file
        test_file = tmp_path / "test_upload.bin"
        test_data = os.urandom(1000)
        test_file.write_bytes(test_data)

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test_tx_id_file",
            "owner": "test_owner",
            "dataCaches": [],
            "fastFinalityIndexes": [],
            "winc": "250",
        }
        mock_post.return_value = mock_response

        # Use stream_factory to open the file fresh each time
        def open_file():
            return open(test_file, "rb")

        result = turbo.upload(
            stream_factory=open_file,
            data_size=len(test_data),
            tags=[{"name": "Test", "value": "file"}],
        )

        assert result.id == "test_tx_id_file"
        mock_post.assert_called_once()

    def test_upload_requires_data_or_stream_factory(self, turbo):
        """Test that upload raises error if neither data nor stream_factory provided"""
        with pytest.raises(ValueError, match="Must specify either data or stream_factory"):
            turbo.upload(tags=[{"name": "Test", "value": "nothing"}])

    def test_upload_rejects_both_data_and_stream_factory(self, turbo):
        """Test that upload raises error if both data and stream_factory provided"""
        with pytest.raises(ValueError, match="Cannot specify both data and stream_factory"):
            turbo.upload(
                data=b"test",
                stream_factory=lambda: io.BytesIO(b"test"),
            )

    def test_upload_requires_data_size_for_stream(self, turbo):
        """Test that upload raises error if stream provided without data_size"""
        stream = io.BytesIO(b"test data")

        with pytest.raises(ValueError, match="data_size is required"):
            turbo.upload(data=stream)

    def test_upload_requires_data_size_for_stream_factory(self, turbo):
        """Test that upload raises error if stream_factory provided without data_size"""
        with pytest.raises(ValueError, match="data_size is required"):
            turbo.upload(stream_factory=lambda: io.BytesIO(b"test"))

    @patch("turbo_sdk.client.requests.post")
    def test_upload_bytes_auto_detects_size(self, mock_post, turbo):
        """Test that upload automatically detects size for bytes input"""
        test_data = b"auto size detection"

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test_id",
            "owner": "owner",
            "dataCaches": [],
            "fastFinalityIndexes": [],
        }
        mock_post.return_value = mock_response

        # Should work without specifying data_size
        result = turbo.upload(data=test_data)
        assert result.id == "test_id"
