import pytest
import hashlib
import base64
from turbo_sdk.bundle.dataitem import DataItem
from turbo_sdk.bundle.constants import SIG_CONFIG


class TestDataItem:
    """Test DataItem class functionality"""

    def test_init_arweave(self):
        """Test DataItem initialization with Arweave signature type"""
        dataitem = DataItem(signature_type=1)

        assert dataitem.signature_type == 1
        assert len(dataitem.signature) == 512  # Arweave signature length
        assert len(dataitem.owner) == 512  # Arweave owner length
        assert len(dataitem.target) == 32
        assert len(dataitem.anchor) == 32
        assert isinstance(dataitem.tags, bytearray)
        assert isinstance(dataitem.data, bytearray)

    def test_init_ethereum(self):
        """Test DataItem initialization with Ethereum signature type"""
        dataitem = DataItem(signature_type=3)

        assert dataitem.signature_type == 3
        assert len(dataitem.signature) == 65  # Ethereum signature length
        assert len(dataitem.owner) == 65  # Ethereum owner length
        assert len(dataitem.target) == 32
        assert len(dataitem.anchor) == 32
        assert isinstance(dataitem.tags, bytearray)
        assert isinstance(dataitem.data, bytearray)

    def test_init_default(self):
        """Test DataItem initialization with default signature type"""
        dataitem = DataItem()  # Should default to Arweave (type 1)

        assert dataitem.signature_type == 1
        assert len(dataitem.signature) == 512
        assert len(dataitem.owner) == 512

    def test_init_invalid_signature_type(self):
        """Test DataItem initialization with invalid signature type"""
        with pytest.raises(ValueError, match="Unsupported signature type"):
            DataItem(signature_type=99)

    def test_get_raw_basic(self):
        """Test basic serialization of DataItem"""
        dataitem = DataItem(signature_type=1)
        dataitem.data = bytearray(b"Hello World")

        raw = dataitem.get_raw()

        # Should start with signature type (2 bytes, little-endian)
        assert raw[0:2] == b"\x01\x00"  # signature_type = 1

        # Should have proper structure
        assert len(raw) > 2  # More than just signature type
        assert isinstance(raw, bytearray)

    def test_get_raw_with_target(self):
        """Test serialization with target set"""
        dataitem = DataItem(signature_type=3)

        # Set a target (first 20 bytes non-zero)
        test_target = bytearray(32)
        test_target[0:4] = b"\x01\x02\x03\x04"
        dataitem.target = test_target
        dataitem.data = bytearray(b"Test data")

        raw = dataitem.get_raw()

        # Should include target flag and target data
        # Structure: sig_type(2) + signature + owner + target_flag(1) + target(32) + ...
        expected_pos = 2 + len(dataitem.signature) + len(dataitem.owner)

        # Target should be present (flag = 1)
        assert raw[expected_pos] == 1

        # Target data should follow
        target_data = raw[expected_pos + 1 : expected_pos + 33]
        assert target_data == test_target

    def test_get_raw_no_target(self):
        """Test serialization without target"""
        dataitem = DataItem(signature_type=1)
        dataitem.data = bytearray(b"Test data")
        # target remains all zeros

        raw = dataitem.get_raw()

        # Calculate position of target flag
        expected_pos = 2 + len(dataitem.signature) + len(dataitem.owner)

        # Target should not be present (flag = 0)
        assert raw[expected_pos] == 0

        # No target data should follow, so anchor flag should be next
        anchor_flag_pos = expected_pos + 1
        assert anchor_flag_pos < len(raw)

    def test_get_raw_with_anchor(self):
        """Test serialization with anchor set"""
        dataitem = DataItem(signature_type=1)

        # Set an anchor
        test_anchor = bytearray(32)
        test_anchor[0:6] = b"anchor"
        dataitem.anchor = test_anchor
        dataitem.data = bytearray(b"Test data")

        raw = dataitem.get_raw()

        # Find anchor flag position (after sig_type + signature + owner + target_flag + target?)
        pos = 2 + len(dataitem.signature) + len(dataitem.owner) + 1  # +1 for target flag
        # No target data since target is all zeros, so anchor flag is right after target flag

        # Anchor should be present
        assert raw[pos] == 1

        # Anchor data should follow
        anchor_data = raw[pos + 1 : pos + 33]
        assert anchor_data == test_anchor

    def test_id_generation(self):
        """Test DataItem ID generation"""
        dataitem = DataItem(signature_type=1)

        # Set a known signature for testing
        test_signature = bytearray(b"test_signature" + b"\x00" * (512 - 14))
        dataitem.signature = test_signature

        # Get ID
        item_id = dataitem.id()

        # Should be base64url encoded SHA-256 of signature
        expected_hash = hashlib.sha256(test_signature).digest()
        expected_id = base64.urlsafe_b64encode(expected_hash).decode().rstrip("=")

        assert item_id == expected_id
        assert isinstance(item_id, str)
        assert len(item_id) > 0

    def test_id_different_signatures(self):
        """Test that different signatures produce different IDs"""
        dataitem1 = DataItem(signature_type=1)
        dataitem2 = DataItem(signature_type=1)

        # Set different signatures
        dataitem1.signature = bytearray(b"signature1" + b"\x00" * (512 - 10))
        dataitem2.signature = bytearray(b"signature2" + b"\x00" * (512 - 10))

        id1 = dataitem1.id()
        id2 = dataitem2.id()

        assert id1 != id2

    def test_is_valid_empty(self):
        """Test validation of empty DataItem"""
        dataitem = DataItem(signature_type=1)

        # Should be invalid (no signature, no data)
        assert not dataitem.is_valid()

    def test_is_valid_with_data(self):
        """Test validation with data but no signature"""
        dataitem = DataItem(signature_type=1)
        dataitem.data = bytearray(b"Hello World")

        # Should be invalid (no signature)
        assert not dataitem.is_valid()

    def test_is_valid_with_signature(self):
        """Test validation with signature but no data"""
        dataitem = DataItem(signature_type=1)
        dataitem.signature = bytearray(b"x" * 512)
        dataitem.owner = bytearray(b"y" * 512)

        # Should be invalid (no data)
        assert not dataitem.is_valid()

    def test_is_valid_complete(self):
        """Test validation of complete DataItem"""
        dataitem = DataItem(signature_type=1)
        dataitem.signature = bytearray(b"x" * 512)
        dataitem.owner = bytearray(b"y" * 512)
        dataitem.data = bytearray(b"Hello World")

        # Should be valid
        assert dataitem.is_valid()

    def test_signature_types_from_config(self):
        """Test that DataItem respects signature configuration"""
        for sig_type, config in SIG_CONFIG.items():
            dataitem = DataItem(signature_type=sig_type)

            assert len(dataitem.signature) == config["sigLength"]
            assert len(dataitem.owner) == config["pubLength"]
            assert dataitem.signature_type == sig_type

    def test_data_assignment(self):
        """Test data assignment and retrieval"""
        dataitem = DataItem(signature_type=1)

        test_data = bytearray(b"This is test data for DataItem")
        dataitem.data = test_data

        assert dataitem.data == test_data
        assert len(dataitem.data) == len(test_data)

    def test_large_data(self):
        """Test DataItem with large data"""
        dataitem = DataItem(signature_type=1)

        # Create large data (1MB)
        large_data = bytearray(b"x" * (1024 * 1024))
        dataitem.data = large_data

        # Should handle large data without issues
        assert len(dataitem.data) == 1024 * 1024

        # Should still serialize
        raw = dataitem.get_raw()
        assert len(raw) > 1024 * 1024  # At least the size of data + headers
