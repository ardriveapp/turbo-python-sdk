import pytest
from turbo_sdk.bundle.utils import set_bytes


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
