"""
Unit tests for StreamingDataItem and create_data_header.

Tests verify that streaming DataItem construction produces identical binary
output to the in-memory approach, ensuring compatibility with the server.
"""

import io
import os
import pytest
from turbo_sdk.bundle import (
    create_data,
    create_data_header,
    sign,
    StreamingDataItem,
)
from turbo_sdk.signers import EthereumSigner

# Test private key (not a real key, just for testing)
TEST_PRIVATE_KEY = "0x" + "ab" * 32


class TestCreateDataHeader:
    """Tests for create_data_header function."""

    @pytest.fixture
    def signer(self):
        """Create a real Ethereum signer for testing."""
        return EthereumSigner(TEST_PRIVATE_KEY)

    def test_header_matches_dataitem_prefix(self, signer):
        """Header bytes should match the prefix of a full DataItem."""
        test_data = b"Hello, Arweave!"
        tags = [{"name": "Content-Type", "value": "text/plain"}]

        # Create full DataItem in memory
        data_item = create_data(bytearray(test_data), signer, tags)
        sign(data_item, signer)
        full_raw = bytes(data_item.get_raw())

        # Create header only
        header = create_data_header(
            signer=signer,
            signature=data_item.raw_signature,
            tags=tags,
            anchor=data_item.raw_anchor,
        )

        # Header should be a prefix of the full DataItem
        assert full_raw.startswith(header)

        # Header + data should equal full DataItem
        reconstructed = header + test_data
        assert reconstructed == full_raw

    def test_header_with_no_tags(self, signer):
        """Should work correctly with no tags."""
        test_data = b"No tags here"

        data_item = create_data(bytearray(test_data), signer, tags=None)
        sign(data_item, signer)
        full_raw = bytes(data_item.get_raw())

        header = create_data_header(
            signer=signer,
            signature=data_item.raw_signature,
            tags=None,
            anchor=data_item.raw_anchor,
        )

        reconstructed = header + test_data
        assert reconstructed == full_raw

    def test_header_with_multiple_tags(self, signer):
        """Should work correctly with multiple tags."""
        test_data = b"Multiple tags"
        tags = [
            {"name": "Content-Type", "value": "application/octet-stream"},
            {"name": "App-Name", "value": "TestApp"},
            {"name": "Version", "value": "1.0.0"},
        ]

        data_item = create_data(bytearray(test_data), signer, tags=tags)
        sign(data_item, signer)
        full_raw = bytes(data_item.get_raw())

        header = create_data_header(
            signer=signer,
            signature=data_item.raw_signature,
            tags=tags,
            anchor=data_item.raw_anchor,
        )

        reconstructed = header + test_data
        assert reconstructed == full_raw

    def test_signature_length_validation(self, signer):
        """Should reject signatures with wrong length."""
        with pytest.raises(ValueError, match="Signature must be"):
            create_data_header(
                signer=signer,
                signature=b"too_short",
                tags=None,
                anchor=os.urandom(32),
            )

    def test_anchor_length_validation(self, signer):
        """Should reject anchors with wrong length."""
        # Ethereum signature is 65 bytes
        signature = b"x" * 65

        with pytest.raises(ValueError, match="Anchor must be exactly 32 bytes"):
            create_data_header(
                signer=signer,
                signature=signature,
                tags=None,
                anchor=b"short_anchor",
            )

    def test_random_anchor_generated_when_none(self, signer):
        """Should generate random anchor when none provided."""
        signature = b"x" * 65

        header1 = create_data_header(
            signer=signer,
            signature=signature,
            tags=None,
            anchor=None,
        )

        header2 = create_data_header(
            signer=signer,
            signature=signature,
            tags=None,
            anchor=None,
        )

        # Headers should differ due to different random anchors
        assert header1 != header2


class TestStreamingDataItem:
    """Tests for StreamingDataItem class."""

    @pytest.fixture
    def signer(self):
        """Create a real Ethereum signer for testing."""
        return EthereumSigner(TEST_PRIVATE_KEY)

    def test_streaming_matches_inmemory(self, signer):
        """Streaming DataItem should produce identical bytes to in-memory."""
        test_data = b"Hello, streaming world!" * 100
        tags = [{"name": "Content-Type", "value": "text/plain"}]

        # In-memory approach
        data_item = create_data(bytearray(test_data), signer, tags)
        sign(data_item, signer)
        expected = bytes(data_item.get_raw())

        # Streaming approach - use same anchor for comparison
        streaming = StreamingDataItem(
            stream_factory=lambda: io.BytesIO(test_data),
            data_size=len(test_data),
            tags=tags,
        )
        # Manually set the anchor to match
        streaming._anchor = data_item.raw_anchor

        # Now prepare - this will use our preset anchor
        from turbo_sdk.bundle.sign import sign_stream
        from turbo_sdk.bundle.tags import encode_tags

        encoded_tags = encode_tags(tags)
        sign_stream_obj = streaming._stream_factory()
        signature = sign_stream(
            signature_type=signer.signature_type,
            raw_owner=signer.public_key,
            raw_target=b"",
            raw_anchor=streaming._anchor,
            raw_tags=encoded_tags,
            data_stream=sign_stream_obj,
            data_size=len(test_data),
            signer=signer,
        )

        streaming._signer = signer
        streaming._signature = signature
        streaming._data_stream = streaming._stream_factory()
        streaming._header = create_data_header(
            signer=signer,
            signature=signature,
            tags=tags,
            anchor=streaming._anchor,
        )
        streaming._signed = True

        actual = streaming.read(-1)

        assert actual == expected

    def test_sign_returns_raw_id(self, signer):
        """sign() should return raw_id bytes."""
        test_data = b"x" * 1000

        streaming = StreamingDataItem(
            stream_factory=lambda: io.BytesIO(test_data),
            data_size=len(test_data),
            tags=[{"name": "Test", "value": "value"}],
        )

        result = streaming.sign(signer)

        assert result == streaming.raw_id
        assert len(result) == 32  # SHA-256 digest

        # total_size should still be header + data
        total_size = streaming.total_size
        assert total_size == streaming.header_size + len(test_data)

    def test_read_chunks_correctly(self, signer):
        """Reading in chunks should produce same result as reading all."""
        test_data = b"chunked read test data " * 50

        streaming = StreamingDataItem(
            stream_factory=lambda: io.BytesIO(test_data),
            data_size=len(test_data),
            tags=None,
        )
        streaming.sign(signer)
        total_size = streaming.total_size

        # Read in chunks
        chunks = []
        while True:
            chunk = streaming.read(100)
            if not chunk:
                break
            chunks.append(chunk)

        chunked_result = b"".join(chunks)

        # Reset and read all at once
        streaming.reset()
        all_at_once = streaming.read(-1)

        assert chunked_result == all_at_once
        assert len(chunked_result) == total_size

    def test_read_empty_returns_empty(self, signer):
        """read(0) should return empty bytes."""
        test_data = b"test"

        streaming = StreamingDataItem(
            stream_factory=lambda: io.BytesIO(test_data),
            data_size=len(test_data),
            tags=None,
        )
        streaming.sign(signer)

        result = streaming.read(0)
        assert result == b""

    def test_raises_if_not_signed(self, signer):
        """Should raise error if read() called before sign()."""
        streaming = StreamingDataItem(
            stream_factory=lambda: io.BytesIO(b"test"),
            data_size=4,
            tags=None,
        )

        with pytest.raises(RuntimeError, match="Must call sign"):
            streaming.read(10)

    def test_works_with_non_seekable_stream(self, signer):
        """Should work with non-seekable streams via stream_factory."""
        test_data = b"non-seekable data"
        call_count = [0]

        class NonSeekableStream:
            def __init__(self, data):
                self._data = data
                self._pos = 0

            def read(self, size=-1):
                if size < 0:
                    result = self._data[self._pos :]
                    self._pos = len(self._data)
                else:
                    result = self._data[self._pos : self._pos + size]
                    self._pos += len(result)
                return result

            def close(self):
                pass

        def factory():
            call_count[0] += 1
            return NonSeekableStream(test_data)

        streaming = StreamingDataItem(
            stream_factory=factory,
            data_size=len(test_data),
            tags=None,
        )

        streaming.sign(signer)
        total_size = streaming.total_size
        result = streaming.read(-1)

        # Factory should have been called twice: once for signing, once for upload
        assert call_count[0] == 2
        assert len(result) == total_size

    def test_reset_allows_rereading(self, signer):
        """reset() should allow reading the data again."""
        test_data = b"reset test"

        streaming = StreamingDataItem(
            stream_factory=lambda: io.BytesIO(test_data),
            data_size=len(test_data),
            tags=None,
        )
        streaming.sign(signer)

        first_read = streaming.read(-1)
        streaming.reset()
        second_read = streaming.read(-1)

        assert first_read == second_read

    def test_progress_callback_during_signing(self, signer):
        """Progress callback should be called during sign()."""
        test_data = b"x" * 10000
        progress_calls = []

        def on_progress(processed, total):
            progress_calls.append((processed, total))

        streaming = StreamingDataItem(
            stream_factory=lambda: io.BytesIO(test_data),
            data_size=len(test_data),
            tags=None,
            on_sign_progress=on_progress,
        )
        streaming.sign(signer)

        assert len(progress_calls) > 0
        assert progress_calls[-1][0] == len(test_data)
        assert progress_calls[-1][1] == len(test_data)

    def test_large_data_streaming(self, signer):
        """Should handle large data without memory issues."""
        # 1 MiB of data
        test_data = os.urandom(1024 * 1024)

        streaming = StreamingDataItem(
            stream_factory=lambda: io.BytesIO(test_data),
            data_size=len(test_data),
            tags=[{"name": "Size", "value": "1MB"}],
        )

        streaming.sign(signer)
        total_size = streaming.total_size

        # Read in chunks and verify total size
        total_read = 0
        while True:
            chunk = streaming.read(64 * 1024)  # 64 KiB chunks
            if not chunk:
                break
            total_read += len(chunk)

        assert total_read == total_size

    def test_header_then_data_boundary(self, signer):
        """Reading across header/data boundary should work correctly."""
        test_data = b"boundary test data"

        streaming = StreamingDataItem(
            stream_factory=lambda: io.BytesIO(test_data),
            data_size=len(test_data),
            tags=None,
        )
        streaming.sign(signer)

        # Get header size
        header_size = streaming.header_size

        # Read exactly to header boundary
        header_part = streaming.read(header_size)
        assert len(header_part) == header_size

        # Read the data part
        data_part = streaming.read(-1)
        assert data_part == test_data

    def test_is_signed(self, signer):
        """is_signed should reflect whether sign() has been called."""
        streaming = StreamingDataItem(
            stream_factory=lambda: io.BytesIO(b"test"),
            data_size=4,
            tags=None,
        )

        assert streaming.is_signed is False
        streaming.sign(signer)
        assert streaming.is_signed is True

    def test_signature_type(self, signer):
        """signature_type should return the signer's type after sign()."""
        streaming = StreamingDataItem(
            stream_factory=lambda: io.BytesIO(b"test"),
            data_size=4,
            tags=None,
        )
        streaming.sign(signer)

        assert streaming.signature_type == signer.signature_type

    def test_id_and_signature_match_dataitem(self, signer):
        """id, signature, and owner should match an equivalent DataItem."""
        test_data = b"property parity test"
        tags = [{"name": "Content-Type", "value": "text/plain"}]

        # In-memory DataItem
        data_item = create_data(bytearray(test_data), signer, tags)
        sign(data_item, signer)

        # StreamingDataItem with same anchor
        streaming = StreamingDataItem(
            stream_factory=lambda: io.BytesIO(test_data),
            data_size=len(test_data),
            tags=tags,
        )
        streaming._anchor = data_item.raw_anchor

        # Manually sign with same anchor
        from turbo_sdk.bundle.sign import sign_stream
        from turbo_sdk.bundle.tags import encode_tags

        encoded_tags = encode_tags(tags)
        sign_stream_obj = streaming._stream_factory()
        sig = sign_stream(
            signature_type=signer.signature_type,
            raw_owner=signer.public_key,
            raw_target=b"",
            raw_anchor=streaming._anchor,
            raw_tags=encoded_tags,
            data_stream=sign_stream_obj,
            data_size=len(test_data),
            signer=signer,
        )
        streaming._signer = signer
        streaming._signature = sig
        streaming._data_stream = streaming._stream_factory()
        streaming._header = create_data_header(
            signer=signer,
            signature=sig,
            tags=tags,
            anchor=streaming._anchor,
        )
        streaming._signed = True

        assert streaming.id == data_item.id
        assert streaming.raw_id == data_item.raw_id
        assert streaming.raw_signature == bytes(data_item.raw_signature)
        assert streaming.signature == data_item.signature
        assert streaming.raw_owner == bytes(data_item.raw_owner)
        assert streaming.owner == data_item.owner
        assert streaming.raw_anchor == bytes(data_item.raw_anchor)
        assert streaming.raw_target == bytes(data_item.raw_target)

    def test_properties_before_sign_raises(self, signer):
        """Properties that require signing should raise before sign()."""
        streaming = StreamingDataItem(
            stream_factory=lambda: io.BytesIO(b"test"),
            data_size=4,
            tags=None,
        )

        with pytest.raises(RuntimeError, match="Must call sign"):
            _ = streaming.signature_type

        with pytest.raises(RuntimeError, match="Must call sign"):
            _ = streaming.raw_signature

        with pytest.raises(RuntimeError, match="Must call sign"):
            _ = streaming.raw_owner

        with pytest.raises(RuntimeError, match="Must call sign"):
            _ = streaming.raw_anchor

    def test_tags_property(self, signer):
        """tags should return the tags passed at construction."""
        tags = [{"name": "App", "value": "Test"}]
        streaming = StreamingDataItem(
            stream_factory=lambda: io.BytesIO(b"test"),
            data_size=4,
            tags=tags,
        )

        assert streaming.tags == tags


class TestStreamingDataItemIntegration:
    """Integration tests for StreamingDataItem with real file-like objects."""

    @pytest.fixture
    def signer(self):
        """Create a real Ethereum signer for testing."""
        return EthereumSigner(TEST_PRIVATE_KEY)

    def test_with_tempfile(self, signer, tmp_path):
        """Should work correctly with actual file objects."""
        from turbo_sdk.bundle.sign import sign_stream
        from turbo_sdk.bundle.tags import encode_tags

        # Create a temporary file
        test_file = tmp_path / "test_data.bin"
        test_data = os.urandom(5000)
        test_file.write_bytes(test_data)

        # Compare with in-memory result
        data_item = create_data(bytearray(test_data), signer, tags=None)
        sign(data_item, signer)

        # Get the raw_tags from data_item for consistency
        encoded_tags = encode_tags([])

        def open_file():
            return open(test_file, "rb")

        streaming = StreamingDataItem(
            stream_factory=open_file,
            data_size=len(test_data),
            tags=None,
        )
        # Use same anchor
        streaming._anchor = data_item.raw_anchor

        sign_stream_obj = streaming._stream_factory()
        signature = sign_stream(
            signature_type=signer.signature_type,
            raw_owner=signer.public_key,
            raw_target=b"",
            raw_anchor=streaming._anchor,
            raw_tags=encoded_tags,
            data_stream=sign_stream_obj,
            data_size=len(test_data),
            signer=signer,
        )
        sign_stream_obj.close()

        streaming._signer = signer
        streaming._signature = signature
        streaming._data_stream = streaming._stream_factory()
        streaming._header = create_data_header(
            signer=signer,
            signature=signature,
            tags=None,
            anchor=streaming._anchor,
        )
        streaming._signed = True

        streamed_result = streaming.read(-1)
        streaming._data_stream.close()

        expected = bytes(data_item.get_raw())
        assert streamed_result == expected

    def test_with_tempfile_using_sign(self, signer, tmp_path):
        """Test using the normal sign() flow with a temp file."""
        # Create a temporary file
        test_file = tmp_path / "test_data.bin"
        test_data = os.urandom(10000)
        test_file.write_bytes(test_data)

        def open_file():
            return open(test_file, "rb")

        streaming = StreamingDataItem(
            stream_factory=open_file,
            data_size=len(test_data),
            tags=[{"name": "App", "value": "Test"}],
        )

        streaming.sign(signer)
        total_size = streaming.total_size
        result = streaming.read(-1)

        # Verify size matches
        assert len(result) == total_size

        # Verify it starts with correct signature type (Ethereum = 3)
        assert result[0:2] == b"\x03\x00"  # Little-endian 3
