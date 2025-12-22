import pytest
import hashlib
from turbo_sdk.bundle.dataitem import DataItem
from turbo_sdk.bundle.create import create_data
from turbo_sdk.bundle.constants import SIG_CONFIG
from unittest.mock import Mock


class TestDataItem:
    """Test DataItem class functionality using Irys format"""

    def create_mock_signer(self, signature_type=1):
        """Create a mock signer for testing"""
        signer = Mock()
        signer.signature_type = signature_type

        if signature_type == 1:  # Arweave
            signer.public_key = bytearray(b"A" * 512)  # Mock 512-byte public key
        elif signature_type == 3:  # Ethereum
            signer.public_key = bytearray(b"E" * 65)  # Mock 65-byte public key

        return signer

    def test_create_dataitem_arweave(self):
        """Test DataItem creation with Arweave signer"""
        signer = self.create_mock_signer(signature_type=1)
        data = bytearray(b"Hello, Arweave!")

        dataitem = create_data(data, signer)

        assert dataitem.signature_type == 1
        assert len(dataitem.raw_owner) == 512  # Arweave owner length
        assert dataitem.raw_data == data
        assert isinstance(dataitem.binary, bytearray)

    def test_create_dataitem_ethereum(self):
        """Test DataItem creation with Ethereum signer"""
        signer = self.create_mock_signer(signature_type=3)
        data = bytearray(b"Hello, Ethereum!")

        dataitem = create_data(data, signer)

        assert dataitem.signature_type == 3
        assert len(dataitem.raw_owner) == 65  # Ethereum owner length
        assert dataitem.raw_data == data

    def test_create_dataitem_with_tags(self):
        """Test DataItem creation with tags"""
        signer = self.create_mock_signer()
        data = bytearray(b"Hello, world!")
        tags = [
            {"name": "Content-Type", "value": "text/plain"},
            {"name": "App-Name", "value": "Test"},
        ]

        dataitem = create_data(data, signer, tags=tags)

        assert dataitem.get_tags_count() == 2
        assert len(dataitem.tags) == 2
        assert dataitem.tags[0]["name"] == "Content-Type"
        assert dataitem.tags[0]["value"] == "text/plain"

    def test_create_dataitem_with_target(self):
        """Test DataItem creation with target"""
        signer = self.create_mock_signer()
        data = bytearray(b"Hello, target!")
        target = "0x1234567890abcdef1234567890abcdef12345678"

        dataitem = create_data(data, signer, target=target)

        assert len(dataitem.raw_target) == 32
        assert dataitem.raw_target[:20] == bytes.fromhex("1234567890abcdef1234567890abcdef12345678")

    def test_create_dataitem_with_anchor(self):
        """Test DataItem creation with anchor"""
        signer = self.create_mock_signer()
        data = bytearray(b"Hello, anchor!")
        anchor = "test-anchor"

        dataitem = create_data(data, signer, anchor=anchor)

        assert len(dataitem.raw_anchor) == 32
        assert dataitem.raw_anchor[: len(anchor)] == anchor.encode("utf-8")

    def test_dataitem_properties(self):
        """Test DataItem properties"""
        signer = self.create_mock_signer()
        data = bytearray(b"Test data")

        dataitem = create_data(data, signer)

        # Test basic properties
        assert dataitem.signature_length == 512
        assert dataitem.owner_length == 512
        assert len(dataitem.raw_signature) == 512
        assert len(dataitem.raw_owner) == 512
        assert dataitem.raw_data == data

    def test_dataitem_id_generation(self):
        """Test DataItem ID generation"""
        signer = self.create_mock_signer()
        data = bytearray(b"Test data")

        dataitem = create_data(data, signer)

        # Before signing, signature is all zeros
        assert len(dataitem.raw_signature) == 512
        assert all(b == 0 for b in dataitem.raw_signature)

        # ID should be base58 encoded SHA256 of signature
        expected_id_bytes = hashlib.sha256(dataitem.raw_signature).digest()
        from base58 import b58encode

        expected_id = b58encode(expected_id_bytes).decode("utf-8")
        assert dataitem.id == expected_id

    def test_dataitem_binary_structure(self):
        """Test DataItem binary structure matches expected format"""
        signer = self.create_mock_signer(signature_type=1)
        data = bytearray(b"Test")
        tags = [{"name": "test", "value": "value"}]

        dataitem = create_data(data, signer, tags=tags)
        binary = dataitem.get_raw()

        # Check binary structure
        offset = 0

        # Signature type (2 bytes)
        sig_type = int.from_bytes(binary[offset : offset + 2], "little")
        assert sig_type == 1
        offset += 2

        # Signature (512 bytes for Arweave)
        signature = binary[offset : offset + 512]
        assert len(signature) == 512
        offset += 512

        # Owner (512 bytes for Arweave)
        owner = binary[offset : offset + 512]
        assert len(owner) == 512
        assert owner == signer.public_key
        offset += 512

        # Target present flag (1 byte) - should be 0
        target_present = binary[offset]
        assert target_present == 0
        offset += 1

        # Anchor present flag (1 byte) - should be 1
        anchor_present = binary[offset]
        assert anchor_present == 1
        offset += 1

        # Anchor (32 bytes)
        anchor = binary[offset : offset + 32]
        assert len(anchor) == 32
        offset += 32

        # Number of tags (8 bytes)
        tag_count = int.from_bytes(binary[offset : offset + 8], "little")
        assert tag_count == 1
        offset += 8

        # Tag data length (8 bytes)
        tag_length = int.from_bytes(binary[offset : offset + 8], "little")
        assert tag_length > 0
        offset += 8

        # Tag data
        tag_data = binary[offset : offset + tag_length]
        assert len(tag_data) == tag_length
        offset += tag_length

        # Data
        data_content = binary[offset:]
        assert data_content == data

    def test_dataitem_tags_parsing(self):
        """Test DataItem tag parsing"""
        signer = self.create_mock_signer()
        data = bytearray(b"Test")
        tags = [
            {"name": "Content-Type", "value": "text/plain"},
            {"name": "App-Name", "value": "Test-App"},
        ]

        dataitem = create_data(data, signer, tags=tags)

        # Test tag count and size
        assert dataitem.get_tags_count() == 2
        assert dataitem.get_tags_size() > 0

        # Test tag parsing
        parsed_tags = dataitem.tags
        assert len(parsed_tags) == 2
        assert parsed_tags[0]["name"] == "Content-Type"
        assert parsed_tags[0]["value"] == "text/plain"
        assert parsed_tags[1]["name"] == "App-Name"
        assert parsed_tags[1]["value"] == "Test-App"

    def test_dataitem_empty_tags(self):
        """Test DataItem with empty tags"""
        signer = self.create_mock_signer()
        data = bytearray(b"Test")

        dataitem = create_data(data, signer, tags=[])

        assert dataitem.get_tags_count() == 0
        assert len(dataitem.tags) == 0

    def test_dataitem_verification(self):
        """Test DataItem verification"""
        signer = self.create_mock_signer()
        data = bytearray(b"Test")

        dataitem = create_data(data, signer)
        binary = dataitem.get_raw()

        # Basic verification should pass (we simplified it to not require actual signature verification)
        assert DataItem.verify(binary) is True

        # Too short binary should fail
        short_binary = bytearray(50)  # Less than MIN_BINARY_SIZE
        assert DataItem.verify(short_binary) is False

    def test_signature_config_compatibility(self):
        """Test that signature configs work correctly"""
        # Test Arweave config
        signer_arweave = self.create_mock_signer(signature_type=1)
        dataitem_arweave = create_data(bytearray(b"test"), signer_arweave)

        assert dataitem_arweave.signature_type == 1
        assert dataitem_arweave.signature_length == SIG_CONFIG[1]["sigLength"]
        assert dataitem_arweave.owner_length == SIG_CONFIG[1]["pubLength"]

        # Test Ethereum config
        signer_ethereum = self.create_mock_signer(signature_type=3)
        dataitem_ethereum = create_data(bytearray(b"test"), signer_ethereum)

        assert dataitem_ethereum.signature_type == 3
        assert dataitem_ethereum.signature_length == SIG_CONFIG[3]["sigLength"]
        assert dataitem_ethereum.owner_length == SIG_CONFIG[3]["pubLength"]
