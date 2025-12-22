import pytest
from turbo_sdk.bundle.tags import encode_tags, decode_tags


class TestTags:
    """Test tag encoding and decoding functions"""

    def test_encode_empty_tags(self):
        """Test encoding empty tag list"""
        result = encode_tags([])
        assert len(result) == 1  # Single 0x00 byte for empty array

        # Should be single zero byte (Avro empty array)
        expected = bytearray([0x00])
        assert result == expected

    def test_encode_none_tags(self):
        """Test encoding None tags"""
        result = encode_tags(None)
        assert len(result) == 1

        # Should be same as empty tags (Avro empty array)
        expected = bytearray([0x00])
        assert result == expected

    def test_encode_single_tag(self):
        """Test encoding single tag"""
        tags = [{"name": "Content-Type", "value": "text/plain"}]
        result = encode_tags(tags)

        # Should be Avro-encoded with reasonable length
        assert len(result) > 1  # More than just empty array marker

        # Verify by decoding
        decoded = decode_tags(result)
        assert len(decoded) == 1
        assert decoded[0]["name"] == "Content-Type"
        assert decoded[0]["value"] == "text/plain"

    def test_encode_multiple_tags(self):
        """Test encoding multiple tags"""
        tags = [
            {"name": "Content-Type", "value": "text/plain"},
            {"name": "App-Name", "value": "Turbo-SDK"},
            {"name": "Version", "value": "1.0"},
        ]
        result = encode_tags(tags)

        # Should be Avro-encoded with reasonable length
        assert len(result) > 1  # More than just empty array marker

        # Verify by decoding
        decoded = decode_tags(result)
        assert len(decoded) == 3
        assert decoded == tags

    def test_decode_empty_tags(self):
        """Test decoding empty tags"""
        # Create empty tag data (Avro empty array)
        empty_data = bytearray([0x00])
        result = decode_tags(empty_data)

        assert result == []

    def test_decode_insufficient_data(self):
        """Test decoding with insufficient data"""
        # Empty bytearray
        short_data = bytearray()
        result = decode_tags(short_data)

        assert result == []

    def test_roundtrip_single_tag(self):
        """Test encoding then decoding single tag"""
        original_tags = [{"name": "Content-Type", "value": "text/plain"}]

        # Encode then decode
        encoded = encode_tags(original_tags)
        decoded = decode_tags(encoded)

        assert decoded == original_tags

    def test_roundtrip_multiple_tags(self):
        """Test encoding then decoding multiple tags"""
        original_tags = [
            {"name": "Content-Type", "value": "application/json"},
            {"name": "App-Name", "value": "Turbo-SDK-Python"},
            {"name": "Version", "value": "0.1.0"},
            {"name": "Author", "value": "ArDrive"},
        ]

        # Encode then decode
        encoded = encode_tags(original_tags)
        decoded = decode_tags(encoded)

        assert decoded == original_tags

    def test_roundtrip_unicode_tags(self):
        """Test encoding/decoding with unicode characters"""
        original_tags = [
            {"name": "Title", "value": "Hello 世界"},
            {"name": "Emoji", "value": "🚀🌟💫"},
            {"name": "Accents", "value": "Café naïve résumé"},
        ]

        # Encode then decode
        encoded = encode_tags(original_tags)
        decoded = decode_tags(encoded)

        assert decoded == original_tags

    def test_roundtrip_empty_values(self):
        """Test encoding/decoding tags with empty values"""
        original_tags = [
            {"name": "EmptyValue", "value": ""},
            {"name": "", "value": "EmptyName"},
            {"name": "Normal", "value": "Value"},
        ]

        # Encode then decode
        encoded = encode_tags(original_tags)
        decoded = decode_tags(encoded)

        assert decoded == original_tags

    def test_encode_missing_keys(self):
        """Test encoding tags with missing name/value keys"""
        # Missing value
        tags_missing_value = [{"name": "Test"}]
        result = encode_tags(tags_missing_value)
        decoded = decode_tags(result)

        # Should default to empty string for missing value
        assert decoded == [{"name": "Test", "value": ""}]

        # Missing name
        tags_missing_name = [{"value": "TestValue"}]
        result = encode_tags(tags_missing_name)
        decoded = decode_tags(result)

        # Should default to empty string for missing name
        assert decoded == [{"name": "", "value": "TestValue"}]

    def test_encode_large_tags(self):
        """Test encoding large tag values"""
        # Create a large tag value
        large_value = "x" * 1000
        tags = [{"name": "LargeTag", "value": large_value}]

        # Encode then decode
        encoded = encode_tags(tags)
        decoded = decode_tags(encoded)

        assert decoded == tags
        assert decoded[0]["value"] == large_value
