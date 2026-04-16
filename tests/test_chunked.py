"""Tests for chunked/multipart upload functionality"""

import io
import pytest
from unittest.mock import Mock, patch, MagicMock
import json

from turbo_sdk.types import ChunkingParams, TurboUploadStatus, ChunkedUploadInit
from turbo_sdk.chunked import (
    ChunkedUploader,
    ChunkedUploadError,
    UnderfundedError,
    UploadValidationError,
    UploadFinalizationError,
)


class TestChunkingParams:
    """Test ChunkingParams dataclass"""

    def test_default_values(self):
        """Test default parameter values"""
        params = ChunkingParams()
        assert params.chunk_size == 5 * 1024 * 1024  # 5 MiB
        assert params.max_chunk_concurrency == 1
        assert params.chunking_mode == "auto"
        assert params.max_finalize_ms == 150_000

    def test_custom_values(self):
        """Test custom parameter values"""
        params = ChunkingParams(
            chunk_size=10 * 1024 * 1024,
            max_chunk_concurrency=4,
            chunking_mode="force",
            max_finalize_ms=300_000,
        )
        assert params.chunk_size == 10 * 1024 * 1024
        assert params.max_chunk_concurrency == 4
        assert params.chunking_mode == "force"
        assert params.max_finalize_ms == 300_000

    def test_chunk_size_validation_too_small(self):
        """Test validation rejects chunk size below 5 MiB"""
        with pytest.raises(ValueError, match="chunk_size must be between"):
            ChunkingParams(chunk_size=1024 * 1024)  # 1 MiB

    def test_chunk_size_validation_too_large(self):
        """Test validation rejects chunk size above 500 MiB"""
        with pytest.raises(ValueError, match="chunk_size must be between"):
            ChunkingParams(chunk_size=600 * 1024 * 1024)  # 600 MiB

    def test_chunk_size_at_boundaries(self):
        """Test chunk size at valid boundaries"""
        # Minimum boundary
        params_min = ChunkingParams(chunk_size=5 * 1024 * 1024)
        assert params_min.chunk_size == 5 * 1024 * 1024

        # Maximum boundary
        params_max = ChunkingParams(chunk_size=500 * 1024 * 1024)
        assert params_max.chunk_size == 500 * 1024 * 1024

    def test_concurrency_validation(self):
        """Test validation rejects concurrency below 1"""
        with pytest.raises(ValueError, match="max_chunk_concurrency must be at least 1"):
            ChunkingParams(max_chunk_concurrency=0)


class TestChunkedUploader:
    """Test ChunkedUploader class"""

    @pytest.fixture
    def uploader(self):
        """Create a ChunkedUploader instance for testing"""
        return ChunkedUploader(
            upload_url="https://upload.test.io",
            token="arweave",
            chunking_params=ChunkingParams(),
        )

    def test_init(self, uploader):
        """Test uploader initialization"""
        assert uploader.upload_url == "https://upload.test.io"
        assert uploader.token == "arweave"
        assert uploader.params.chunk_size == 5 * 1024 * 1024

    def test_chunking_version_header(self, uploader):
        """Test x-chunking-version header is set"""
        assert uploader._session.headers["x-chunking-version"] == "2"

    def test_poll_interval_small_file(self, uploader):
        """Test poll interval for files < 100 MB"""
        interval = uploader._get_poll_interval(50 * 1024 * 1024)  # 50 MB
        assert interval == 2.0

    def test_poll_interval_medium_file(self, uploader):
        """Test poll interval for files < 3 GiB"""
        interval = uploader._get_poll_interval(1024 * 1024 * 1024)  # 1 GiB
        assert interval == 4.0

    def test_poll_interval_large_file(self, uploader):
        """Test poll interval for files >= 3 GiB"""
        interval = uploader._get_poll_interval(5 * 1024 * 1024 * 1024)  # 5 GiB
        assert interval == 7.5  # 1.5 * 5

    def test_poll_interval_max_cap(self, uploader):
        """Test poll interval caps at 15 seconds"""
        interval = uploader._get_poll_interval(20 * 1024 * 1024 * 1024)  # 20 GiB
        assert interval == 15.0

    @patch("turbo_sdk.chunked.requests.Session")
    def test_initiate_success(self, mock_session_class):
        """Test successful upload initiation"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-upload-id",
            "min": 5242880,
            "max": 524288000,
            "chunkSize": 5242880,
        }

        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        uploader = ChunkedUploader(
            upload_url="https://upload.test.io",
            token="arweave",
        )

        result = uploader.initiate()

        assert isinstance(result, ChunkedUploadInit)
        assert result.id == "test-upload-id"
        assert result.min == 5242880
        assert result.max == 524288000

    @patch("turbo_sdk.chunked.requests.Session")
    def test_initiate_service_unavailable(self, mock_session_class):
        """Test initiation with 503 error"""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"

        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        uploader = ChunkedUploader(
            upload_url="https://upload.test.io",
            token="arweave",
        )

        with pytest.raises(ChunkedUploadError, match="Service unavailable"):
            uploader.initiate()

    @patch("turbo_sdk.chunked.requests.Session")
    def test_upload_chunk_success(self, mock_session_class):
        """Test successful chunk upload"""
        mock_response = Mock()
        mock_response.status_code = 200

        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        uploader = ChunkedUploader(
            upload_url="https://upload.test.io",
            token="arweave",
        )

        # Should not raise
        uploader.upload_chunk("upload-id", 0, b"test data")

        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert "upload-id" in call_args[0][0]
        assert "/0" in call_args[0][0]

    @patch("turbo_sdk.chunked.requests.Session")
    def test_upload_chunk_underfunded(self, mock_session_class):
        """Test chunk upload with 402 error"""
        mock_response = Mock()
        mock_response.status_code = 402

        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        uploader = ChunkedUploader(
            upload_url="https://upload.test.io",
            token="arweave",
        )

        with pytest.raises(UnderfundedError):
            uploader.upload_chunk("upload-id", 0, b"test data")

    @patch("turbo_sdk.chunked.requests.Session")
    def test_upload_chunk_not_found(self, mock_session_class):
        """Test chunk upload with 404 error"""
        mock_response = Mock()
        mock_response.status_code = 404

        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        uploader = ChunkedUploader(
            upload_url="https://upload.test.io",
            token="arweave",
        )

        with pytest.raises(ChunkedUploadError, match="not found or expired"):
            uploader.upload_chunk("upload-id", 0, b"test data")

    @patch("turbo_sdk.chunked.requests.Session")
    def test_finalize_success(self, mock_session_class):
        """Test successful finalization"""
        mock_response = Mock()
        mock_response.status_code = 202

        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        uploader = ChunkedUploader(
            upload_url="https://upload.test.io",
            token="arweave",
        )

        # Should not raise
        uploader.finalize("upload-id")

        call_args = mock_session.post.call_args
        assert "finalize" in call_args[0][0]

    @patch("turbo_sdk.chunked.requests.Session")
    def test_get_status_finalized(self, mock_session_class):
        """Test getting finalized status"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "FINALIZED",
            "timestamp": 1234567890,
            "receipt": {
                "id": "tx-id",
                "owner": "owner-address",
                "dataCaches": ["arweave.net"],
                "fastFinalityIndexes": ["arweave.net"],
                "winc": "1000",
                "signature": "receipt_sig",
                "public": "receipt_pub",
                "version": "1.0.0",
                "deadlineHeight": 999999,
            },
        }

        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        uploader = ChunkedUploader(
            upload_url="https://upload.test.io",
            token="arweave",
        )

        status = uploader.get_status("upload-id")

        assert isinstance(status, TurboUploadStatus)
        assert status.status == "FINALIZED"
        assert status.id == "tx-id"
        assert status.owner == "owner-address"
        assert status.data_caches == ["arweave.net"]
        assert status.signature == "receipt_sig"
        assert status.public == "receipt_pub"
        assert status.version == "1.0.0"
        assert status.deadline_height == 999999

    @patch("turbo_sdk.chunked.requests.Session")
    def test_get_status_validating(self, mock_session_class):
        """Test getting validating status (no receipt yet)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "VALIDATING",
            "timestamp": 1234567890,
        }

        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        uploader = ChunkedUploader(
            upload_url="https://upload.test.io",
            token="arweave",
        )

        status = uploader.get_status("upload-id")

        assert status.status == "VALIDATING"
        assert status.id is None
        assert status.owner is None

    @patch("turbo_sdk.chunked.time.sleep")
    @patch("turbo_sdk.chunked.requests.Session")
    def test_poll_for_finalization_success(self, mock_session_class, mock_sleep):
        """Test successful finalization polling"""
        # First call returns VALIDATING, second returns FINALIZED
        mock_response_validating = Mock()
        mock_response_validating.status_code = 200
        mock_response_validating.json.return_value = {
            "status": "VALIDATING",
            "timestamp": 1234567890,
        }

        mock_response_finalized = Mock()
        mock_response_finalized.status_code = 200
        mock_response_finalized.json.return_value = {
            "status": "FINALIZED",
            "timestamp": 1234567891,
            "receipt": {
                "id": "tx-id",
                "owner": "owner",
                "dataCaches": [],
                "fastFinalityIndexes": [],
                "winc": "0",
            },
        }

        mock_session = Mock()
        mock_session.get.side_effect = [mock_response_validating, mock_response_finalized]
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        uploader = ChunkedUploader(
            upload_url="https://upload.test.io",
            token="arweave",
        )

        status = uploader.poll_for_finalization("upload-id", 1024 * 1024)

        assert status.status == "FINALIZED"
        assert mock_sleep.called

    @patch("turbo_sdk.chunked.time.sleep")
    @patch("turbo_sdk.chunked.requests.Session")
    def test_poll_for_finalization_underfunded(self, mock_session_class, mock_sleep):
        """Test polling returns UNDERFUNDED status"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "UNDERFUNDED",
            "timestamp": 1234567890,
        }

        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        uploader = ChunkedUploader(
            upload_url="https://upload.test.io",
            token="arweave",
        )

        with pytest.raises(UnderfundedError):
            uploader.poll_for_finalization("upload-id", 1024 * 1024)

    @patch("turbo_sdk.chunked.time.sleep")
    @patch("turbo_sdk.chunked.requests.Session")
    def test_poll_for_finalization_invalid(self, mock_session_class, mock_sleep):
        """Test polling returns INVALID status"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "INVALID",
            "timestamp": 1234567890,
        }

        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        uploader = ChunkedUploader(
            upload_url="https://upload.test.io",
            token="arweave",
        )

        with pytest.raises(UploadValidationError, match="INVALID"):
            uploader.poll_for_finalization("upload-id", 1024 * 1024)


class TestChunkedUploaderSequentialUpload:
    """Test sequential chunk upload"""

    @patch("turbo_sdk.chunked.requests.Session")
    def test_upload_chunks_sequential_bytes(self, mock_session_class):
        """Test sequential upload with bytes data"""
        mock_session = Mock()
        mock_session.post.return_value = Mock(status_code=200)
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        params = ChunkingParams(chunk_size=5 * 1024 * 1024)
        uploader = ChunkedUploader(
            upload_url="https://upload.test.io",
            token="arweave",
            chunking_params=params,
        )

        # Create 12 MiB of data (should result in 3 chunks)
        data = b"x" * (12 * 1024 * 1024)
        progress_calls = []

        def on_progress(processed, total):
            progress_calls.append((processed, total))

        uploader.upload_chunks_sequential("upload-id", data, len(data), on_progress)

        # Should have 3 chunk uploads
        assert mock_session.post.call_count == 3

        # Progress should be reported after each chunk
        assert len(progress_calls) == 3
        assert progress_calls[-1][0] == len(data)

    @patch("turbo_sdk.chunked.requests.Session")
    def test_upload_chunks_sequential_stream(self, mock_session_class):
        """Test sequential upload with stream data"""
        mock_session = Mock()
        mock_session.post.return_value = Mock(status_code=200)
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        params = ChunkingParams(chunk_size=5 * 1024 * 1024)
        uploader = ChunkedUploader(
            upload_url="https://upload.test.io",
            token="arweave",
            chunking_params=params,
        )

        # Create stream with 10 MiB
        data = b"y" * (10 * 1024 * 1024)
        stream = io.BytesIO(data)

        uploader.upload_chunks_sequential("upload-id", stream, len(data), None)

        # Should have 2 chunk uploads
        assert mock_session.post.call_count == 2


class TestChunkedUploaderConcurrentUpload:
    """Test concurrent chunk upload"""

    @patch("turbo_sdk.chunked.requests.Session")
    def test_upload_chunks_concurrent(self, mock_session_class):
        """Test concurrent upload"""
        mock_session = Mock()
        mock_session.post.return_value = Mock(status_code=200)
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        params = ChunkingParams(
            chunk_size=5 * 1024 * 1024,
            max_chunk_concurrency=3,
        )
        uploader = ChunkedUploader(
            upload_url="https://upload.test.io",
            token="arweave",
            chunking_params=params,
        )

        # Create 15 MiB of data
        data = b"z" * (15 * 1024 * 1024)

        uploader.upload_chunks_concurrent("upload-id", data, len(data), None)

        # Should have 3 chunk uploads
        assert mock_session.post.call_count == 3


class TestUnderfundedError:
    """Test UnderfundedError exception"""

    def test_default_message(self):
        """Test default error message"""
        error = UnderfundedError()
        assert str(error) == "Insufficient balance for upload"
        assert error.status_code == 402

    def test_custom_message(self):
        """Test custom error message"""
        error = UnderfundedError("Custom message")
        assert str(error) == "Custom message"
        assert error.status_code == 402
