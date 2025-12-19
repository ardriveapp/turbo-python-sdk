import pytest
from turbo_sdk.bundle.utils import long_to_8_byte_array, set_bytes, byte_array_to_long


class TestUtils:
    """Test utility functions in bundle/utils.py"""

    def test_long_to_8_byte_array(self):
        """Test conversion from long to 8-byte array"""
        # Test small number
        result = long_to_8_byte_array(42)
        assert len(result) == 8
        assert result == b"\x2a\x00\x00\x00\x00\x00\x00\x00"  # little-endian

        # Test zero
        result = long_to_8_byte_array(0)
        assert result == b"\x00\x00\x00\x00\x00\x00\x00\x00"

        # Test larger number
        result = long_to_8_byte_array(256)
        assert result == b"\x00\x01\x00\x00\x00\x00\x00\x00"

        # Test max value for 8 bytes
        max_val = (2**64) - 1
        result = long_to_8_byte_array(max_val)
        assert result == b"\xff\xff\xff\xff\xff\xff\xff\xff"

    def test_byte_array_to_long(self):
        """Test conversion from byte array to long"""
        # Test small number
        data = b"\x2a\x00\x00\x00\x00\x00\x00\x00"
        result = byte_array_to_long(data)
        assert result == 42

        # Test zero
        data = b"\x00\x00\x00\x00\x00\x00\x00\x00"
        result = byte_array_to_long(data)
        assert result == 0

        # Test larger number
        data = b"\x00\x01\x00\x00\x00\x00\x00\x00"
        result = byte_array_to_long(data)
        assert result == 256

        # Test max value
        data = b"\xff\xff\xff\xff\xff\xff\xff\xff"
        result = byte_array_to_long(data)
        assert result == (2**64) - 1

    def test_roundtrip_conversion(self):
        """Test that long->bytes->long conversion is lossless"""
        test_values = [0, 1, 42, 256, 65535, 2**32 - 1, 2**63 - 1]

        for value in test_values:
            byte_array = long_to_8_byte_array(value)
            converted_back = byte_array_to_long(byte_array)
            assert converted_back == value

    def test_set_bytes(self):
        """Test setting bytes in target array"""
        # Test basic functionality
        target = bytearray(10)
        source = bytearray([1, 2, 3, 4])
        set_bytes(target, source, 2)

        expected = bytearray([0, 0, 1, 2, 3, 4, 0, 0, 0, 0])
        assert target == expected

        # Test at beginning
        target = bytearray(5)
        source = bytearray([10, 20])
        set_bytes(target, source, 0)

        expected = bytearray([10, 20, 0, 0, 0])
        assert target == expected

        # Test at end
        target = bytearray(5)
        source = bytearray([30, 40])
        set_bytes(target, source, 3)

        expected = bytearray([0, 0, 0, 30, 40])
        assert target == expected

    def test_set_bytes_empty_source(self):
        """Test setting empty bytes"""
        target = bytearray([1, 2, 3, 4, 5])
        source = bytearray()
        set_bytes(target, source, 2)

        # Should remain unchanged
        assert target == bytearray([1, 2, 3, 4, 5])

    def test_set_bytes_overwrite(self):
        """Test overwriting existing bytes"""
        target = bytearray([1, 2, 3, 4, 5])
        source = bytearray([10, 20, 30])
        set_bytes(target, source, 1)

        expected = bytearray([1, 10, 20, 30, 5])
        assert target == expected
