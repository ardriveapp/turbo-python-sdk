import pytest
from turbo_sdk.bundle.utils import set_bytes, byte_array_to_long, b64url_decode


class TestUtils:
    """Test utility functions in bundle/utils.py"""

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

    def test_byte_array_to_long(self):
        """Test converting byte array to long using little-endian"""
        # Test small number
        data = bytearray([42, 0, 0, 0])
        result = byte_array_to_long(data)
        assert result == 42

        # Test zero
        data = bytearray([0, 0, 0, 0])
        result = byte_array_to_long(data)
        assert result == 0

        # Test larger number (256 in little-endian)
        data = bytearray([0, 1, 0, 0])
        result = byte_array_to_long(data)
        assert result == 256

        # Test with 8 bytes
        data = bytearray([255, 255, 255, 255, 0, 0, 0, 0])
        result = byte_array_to_long(data)
        assert result == 4294967295  # 2^32 - 1

    def test_byte_array_to_long_single_byte(self):
        """Test with single byte"""
        data = bytearray([123])
        result = byte_array_to_long(data)
        assert result == 123

    def test_byte_array_to_long_two_bytes(self):
        """Test with two bytes (little-endian)"""
        data = bytearray([0, 1])  # 256 in little-endian
        result = byte_array_to_long(data)
        assert result == 256

        data = bytearray([1, 1])  # 257 in little-endian
        result = byte_array_to_long(data)
        assert result == 257

    def test_b64url_decode_with_padding(self):
        """Test decoding base64url with proper padding"""
        # "hello" in base64url with padding
        result = b64url_decode("aGVsbG8=")
        assert result == b"hello"

    def test_b64url_decode_without_padding(self):
        """Test decoding base64url without padding"""
        # "hello" in base64url without padding
        result = b64url_decode("aGVsbG8")
        assert result == b"hello"

    def test_b64url_decode_url_safe_chars(self):
        """Test that url-safe characters are decoded correctly"""
        import base64

        # Data that would have + and / in standard base64
        data = b"\xfb\xff\xfe"
        encoded = base64.urlsafe_b64encode(data).decode().rstrip("=")
        result = b64url_decode(encoded)
        assert result == data

    def test_b64url_decode_empty(self):
        """Test decoding empty string"""
        result = b64url_decode("")
        assert result == b""

    def test_b64url_decode_various_lengths(self):
        """Test decoding strings of various lengths (different padding needs)"""
        import base64

        for length in [1, 2, 3, 4, 5, 10, 100]:
            data = bytes(range(length % 256)) * (length // 256 + 1)
            data = data[:length]
            encoded = base64.urlsafe_b64encode(data).decode().rstrip("=")
            result = b64url_decode(encoded)
            assert result == data
