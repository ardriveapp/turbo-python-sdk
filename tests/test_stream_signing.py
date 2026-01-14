"""
Unit tests for stream signing functionality.

Tests verify that stream signing produces identical results to in-memory signing
and that progress callbacks work correctly.
"""

import io
import pytest
from turbo_sdk.bundle import create_data, sign, encode_tags
from turbo_sdk.bundle.sign import (
    deep_hash,
    deep_hash_blob_stream,
    get_signature_data,
    get_signature_data_stream,
    sign_stream,
    DEFAULT_STREAM_CHUNK_SIZE,
)
from turbo_sdk.signers import EthereumSigner


# Test private key (not a real key, just for testing)
TEST_PRIVATE_KEY = "0x" + "ab" * 32


class TestDeepHashBlobStream:
    """Tests for deep_hash_blob_stream function."""

    def test_matches_in_memory_deep_hash(self):
        """Stream hash should match in-memory hash for same data."""
        test_data = b"Hello, this is test data for streaming hash verification!" * 100
        stream = io.BytesIO(test_data)

        in_memory_hash = deep_hash(test_data)
        stream_hash = deep_hash_blob_stream(stream, len(test_data))

        assert in_memory_hash == stream_hash

    def test_empty_data(self):
        """Should handle empty data correctly."""
        test_data = b""
        stream = io.BytesIO(test_data)

        in_memory_hash = deep_hash(test_data)
        stream_hash = deep_hash_blob_stream(stream, len(test_data))

        assert in_memory_hash == stream_hash

    def test_single_byte(self):
        """Should handle single byte data."""
        test_data = b"x"
        stream = io.BytesIO(test_data)

        in_memory_hash = deep_hash(test_data)
        stream_hash = deep_hash_blob_stream(stream, len(test_data))

        assert in_memory_hash == stream_hash

    def test_large_data(self):
        """Should handle data larger than chunk size."""
        # Create data larger than default chunk size (256 KiB)
        test_data = b"x" * (DEFAULT_STREAM_CHUNK_SIZE * 3 + 1000)
        stream = io.BytesIO(test_data)

        in_memory_hash = deep_hash(test_data)
        stream_hash = deep_hash_blob_stream(stream, len(test_data))

        assert in_memory_hash == stream_hash

    def test_custom_chunk_size(self):
        """Should work with custom chunk sizes."""
        test_data = b"Test data for custom chunk size" * 100
        stream = io.BytesIO(test_data)

        in_memory_hash = deep_hash(test_data)
        stream_hash = deep_hash_blob_stream(stream, len(test_data), chunk_size=64)

        assert in_memory_hash == stream_hash

    def test_progress_callback_called(self):
        """Progress callback should be called during hashing."""
        test_data = b"x" * 5000
        stream = io.BytesIO(test_data)
        progress_calls = []

        def on_progress(processed, total):
            progress_calls.append((processed, total))

        deep_hash_blob_stream(stream, len(test_data), chunk_size=1024, on_progress=on_progress)

        assert len(progress_calls) > 0
        assert progress_calls[-1] == (len(test_data), len(test_data))

    def test_progress_callback_increments(self):
        """Progress should increment correctly."""
        test_data = b"x" * 3000
        stream = io.BytesIO(test_data)
        progress_calls = []

        def on_progress(processed, total):
            progress_calls.append((processed, total))

        deep_hash_blob_stream(stream, len(test_data), chunk_size=1000, on_progress=on_progress)

        # Should have 3 calls for 3000 bytes with 1000 byte chunks
        assert len(progress_calls) == 3
        assert progress_calls[0] == (1000, 3000)
        assert progress_calls[1] == (2000, 3000)
        assert progress_calls[2] == (3000, 3000)

    def test_raises_on_premature_stream_end(self):
        """Should raise error if stream ends before expected size."""
        test_data = b"short"
        stream = io.BytesIO(test_data)

        with pytest.raises(ValueError, match="Stream ended prematurely"):
            deep_hash_blob_stream(stream, len(test_data) + 100)


class TestGetSignatureDataStream:
    """Tests for get_signature_data_stream function."""

    def test_matches_in_memory_signature_data(self):
        """Stream signature data should match in-memory version."""
        sig_type = 3  # Ethereum
        raw_owner = b"x" * 65
        raw_target = b""
        raw_anchor = b"a" * 32
        raw_tags = b""
        data = b"Test payload data" * 500

        # Create mock dataitem for in-memory comparison
        class MockDataItem:
            signature_type = sig_type
            raw_owner = b"x" * 65
            raw_target = b""
            raw_anchor = b"a" * 32
            raw_tags = b""
            raw_data = data

        mock_item = MockDataItem()
        in_memory_hash = get_signature_data(mock_item)

        data_stream = io.BytesIO(data)
        stream_hash = get_signature_data_stream(
            signature_type=sig_type,
            raw_owner=raw_owner,
            raw_target=raw_target,
            raw_anchor=raw_anchor,
            raw_tags=raw_tags,
            data_stream=data_stream,
            data_size=len(data),
        )

        assert in_memory_hash == stream_hash

    def test_with_tags(self):
        """Should work correctly with encoded tags."""
        sig_type = 3
        raw_owner = b"x" * 65
        raw_target = b""
        raw_anchor = b"a" * 32
        raw_tags = encode_tags([{"name": "Content-Type", "value": "text/plain"}])
        data = b"Data with tags"

        class MockDataItem:
            signature_type = sig_type
            raw_owner = b"x" * 65
            raw_target = b""
            raw_anchor = b"a" * 32
            raw_tags = encode_tags([{"name": "Content-Type", "value": "text/plain"}])
            raw_data = data

        mock_item = MockDataItem()
        in_memory_hash = get_signature_data(mock_item)

        data_stream = io.BytesIO(data)
        stream_hash = get_signature_data_stream(
            signature_type=sig_type,
            raw_owner=raw_owner,
            raw_target=raw_target,
            raw_anchor=raw_anchor,
            raw_tags=raw_tags,
            data_stream=data_stream,
            data_size=len(data),
        )

        assert in_memory_hash == stream_hash

    def test_with_target(self):
        """Should work correctly with target address."""
        sig_type = 3
        raw_owner = b"x" * 65
        raw_target = b"t" * 32  # 32-byte target
        raw_anchor = b"a" * 32
        raw_tags = b""
        data = b"Data with target"

        class MockDataItem:
            signature_type = sig_type
            raw_owner = b"x" * 65
            raw_target = b"t" * 32
            raw_anchor = b"a" * 32
            raw_tags = b""
            raw_data = data

        mock_item = MockDataItem()
        in_memory_hash = get_signature_data(mock_item)

        data_stream = io.BytesIO(data)
        stream_hash = get_signature_data_stream(
            signature_type=sig_type,
            raw_owner=raw_owner,
            raw_target=raw_target,
            raw_anchor=raw_anchor,
            raw_tags=raw_tags,
            data_stream=data_stream,
            data_size=len(data),
        )

        assert in_memory_hash == stream_hash


class TestSignStream:
    """Tests for sign_stream function."""

    @pytest.fixture
    def signer(self):
        """Create a real Ethereum signer for testing."""
        return EthereumSigner(TEST_PRIVATE_KEY)

    def test_matches_in_memory_sign(self, signer):
        """Stream signing should produce identical signature to in-memory signing."""
        test_data = b"Hello Arweave! " * 1000
        tags = [{"name": "Content-Type", "value": "text/plain"}]

        # In-memory signing via DataItem
        data_item = create_data(bytearray(test_data), signer, tags)
        sign(data_item, signer)
        in_memory_signature = data_item.raw_signature

        # Stream signing
        encoded_tags = encode_tags(tags)
        stream = io.BytesIO(test_data)

        stream_signature = sign_stream(
            signature_type=signer.signature_type,
            raw_owner=signer.public_key,
            raw_target=b"",
            raw_anchor=data_item.raw_anchor,  # Use same anchor
            raw_tags=encoded_tags,
            data_stream=stream,
            data_size=len(test_data),
            signer=signer,
        )

        assert in_memory_signature == stream_signature

    def test_with_progress_callback(self, signer):
        """Progress callback should work during stream signing."""
        test_data = b"x" * 10000
        progress_calls = []

        def on_progress(processed, total):
            progress_calls.append((processed, total))

        stream = io.BytesIO(test_data)

        sign_stream(
            signature_type=signer.signature_type,
            raw_owner=signer.public_key,
            raw_target=b"",
            raw_anchor=b"a" * 32,
            raw_tags=b"",
            data_stream=stream,
            data_size=len(test_data),
            signer=signer,
            chunk_size=1000,
            on_progress=on_progress,
        )

        assert len(progress_calls) == 10
        assert progress_calls[-1] == (10000, 10000)

    def test_different_data_produces_different_signature(self, signer):
        """Different data should produce different signatures."""
        data1 = b"First data payload"
        data2 = b"Second data payload"
        anchor = b"a" * 32

        stream1 = io.BytesIO(data1)
        sig1 = sign_stream(
            signature_type=signer.signature_type,
            raw_owner=signer.public_key,
            raw_target=b"",
            raw_anchor=anchor,
            raw_tags=b"",
            data_stream=stream1,
            data_size=len(data1),
            signer=signer,
        )

        stream2 = io.BytesIO(data2)
        sig2 = sign_stream(
            signature_type=signer.signature_type,
            raw_owner=signer.public_key,
            raw_target=b"",
            raw_anchor=anchor,
            raw_tags=b"",
            data_stream=stream2,
            data_size=len(data2),
            signer=signer,
        )

        assert sig1 != sig2


class TestDefaultChunkSize:
    """Tests for default chunk size constant."""

    def test_default_chunk_size_is_256_kib(self):
        """Default chunk size should be 256 KiB to match Arweave."""
        assert DEFAULT_STREAM_CHUNK_SIZE == 256 * 1024
