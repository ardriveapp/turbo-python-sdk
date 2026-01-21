"""Chunked/multipart upload support for large files"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import BinaryIO, Optional, Union

import requests

from .types import (
    ChunkedUploadInit,
    TurboUploadStatus,
    ChunkingParams,
    ProgressCallback,
    TurboUploadResponse,
)


class ChunkedUploadError(Exception):
    """Base exception for chunked upload errors"""

    pass


class UnderfundedError(ChunkedUploadError):
    """Raised when account has insufficient balance (402)"""

    def __init__(self, message: str = "Insufficient balance for upload"):
        self.status_code = 402
        super().__init__(message)


class UploadValidationError(ChunkedUploadError):
    """Raised when upload validation fails"""

    pass


class UploadFinalizationError(ChunkedUploadError):
    """Raised when upload finalization fails or times out"""

    pass


class ChunkedUploader:
    """Manages multipart upload lifecycle for large files"""

    CHUNKING_VERSION = "2"
    FINALIZED_STATES = {"FINALIZED"}
    ERROR_STATES = {"INVALID", "UNDERFUNDED", "APPROVAL_FAILED"}

    def __init__(
        self,
        upload_url: str,
        token: str,
        chunking_params: Optional[ChunkingParams] = None,
    ):
        self.upload_url = upload_url
        self.token = token
        self.params = chunking_params or ChunkingParams()
        self._session = requests.Session()
        self._session.headers.update({"x-chunking-version": self.CHUNKING_VERSION})

    def _get_poll_interval(self, total_bytes: int) -> float:
        """Calculate poll interval based on data size (from TS SDK)"""
        mb_100 = 100 * 1024 * 1024
        gb_3 = 3 * 1024 * 1024 * 1024

        if total_bytes < mb_100:
            return 2.0
        elif total_bytes < gb_3:
            return 4.0
        else:
            # 1.5 seconds per GiB, max 15 seconds
            gib = total_bytes / (1024 * 1024 * 1024)
            return min(1.5 * gib, 15.0)

    def _get_max_finalize_time(self, total_bytes: int) -> float:
        """Calculate max finalization wait time (2.5 min per GiB)"""
        gib = max(1, total_bytes / (1024 * 1024 * 1024))
        return gib * 150_000 / 1000  # Convert ms to seconds

    def initiate(self) -> ChunkedUploadInit:
        """Initiate a new chunked upload session"""
        url = f"{self.upload_url}/chunks/{self.token}/-1/-1"
        params = {"chunkSize": self.params.chunk_byte_count}

        response = self._session.get(url, params=params)

        if response.status_code == 200:
            data = response.json()
            return ChunkedUploadInit(
                id=data["id"],
                min=data["min"],
                max=data["max"],
                chunk_size=data.get("chunkSize", self.params.chunk_byte_count),
            )
        elif response.status_code == 503:
            raise ChunkedUploadError(f"Service unavailable: {response.text}")
        else:
            raise ChunkedUploadError(
                f"Failed to initiate upload: {response.status_code} - {response.text}"
            )

    def upload_chunk(self, upload_id: str, offset: int, data: bytes) -> None:
        """Upload a single chunk"""
        url = f"{self.upload_url}/chunks/{self.token}/{upload_id}/{offset}"

        response = self._session.post(
            url,
            data=data,
            headers={"Content-Type": "application/octet-stream"},
        )

        if response.status_code == 200:
            return
        elif response.status_code == 402:
            raise UnderfundedError()
        elif response.status_code == 404:
            raise ChunkedUploadError("Upload session not found or expired")
        else:
            raise ChunkedUploadError(
                f"Chunk upload failed: {response.status_code} - {response.text}"
            )

    def finalize(self, upload_id: str) -> None:
        """Finalize the chunked upload (enqueue for processing)"""
        url = f"{self.upload_url}/chunks/{self.token}/{upload_id}/finalize"

        response = self._session.post(url)

        if response.status_code == 202:
            return
        elif response.status_code == 402:
            raise UnderfundedError()
        elif response.status_code == 404:
            raise ChunkedUploadError("Upload session not found or expired")
        else:
            raise ChunkedUploadError(
                f"Finalize failed: {response.status_code} - {response.text}"
            )

    def get_status(self, upload_id: str) -> TurboUploadStatus:
        """Get current upload status"""
        url = f"{self.upload_url}/chunks/{self.token}/{upload_id}/status"

        response = self._session.get(url)

        if response.status_code == 200:
            data = response.json()
            receipt = data.get("receipt", {})
            return TurboUploadStatus(
                status=data["status"],
                timestamp=data["timestamp"],
                id=receipt.get("id"),
                owner=receipt.get("owner"),
                data_caches=receipt.get("dataCaches", []),
                fast_finality_indexes=receipt.get("fastFinalityIndexes", []),
                winc=receipt.get("winc"),
            )
        elif response.status_code == 404:
            raise ChunkedUploadError("Upload session not found")
        else:
            raise ChunkedUploadError(
                f"Status check failed: {response.status_code} - {response.text}"
            )

    def poll_for_finalization(
        self, upload_id: str, total_bytes: int
    ) -> TurboUploadStatus:
        """Poll until upload is finalized or fails"""
        poll_interval = self._get_poll_interval(total_bytes)
        max_wait = self._get_max_finalize_time(total_bytes)
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait:
                raise UploadFinalizationError(
                    f"Finalization timed out after {elapsed:.1f}s"
                )

            status = self.get_status(upload_id)

            if status.status in self.FINALIZED_STATES:
                return status
            elif status.status == "UNDERFUNDED":
                raise UnderfundedError()
            elif status.status in self.ERROR_STATES:
                raise UploadValidationError(f"Upload failed with status: {status.status}")

            time.sleep(poll_interval)

    def upload_chunks_sequential(
        self,
        upload_id: str,
        data: Union[bytes, BinaryIO],
        total_size: int,
        on_progress: Optional[ProgressCallback] = None,
    ) -> None:
        """Upload chunks sequentially"""
        chunk_size = self.params.chunk_byte_count
        offset = 0
        processed = 0

        while offset < total_size:
            # Read chunk
            if isinstance(data, bytes):
                chunk = data[offset : offset + chunk_size]
            else:
                chunk = data.read(chunk_size)
                if not chunk:
                    break

            # Upload chunk
            self.upload_chunk(upload_id, offset, chunk)

            processed += len(chunk)
            offset += len(chunk)

            if on_progress:
                on_progress(processed, total_size)

    def upload_chunks_concurrent(
        self,
        upload_id: str,
        data: bytes,
        total_size: int,
        on_progress: Optional[ProgressCallback] = None,
    ) -> None:
        """Upload chunks concurrently (requires bytes, not stream)"""
        chunk_size = self.params.chunk_byte_count
        max_workers = self.params.max_chunk_concurrency

        # Build list of chunks
        chunks = []
        offset = 0
        while offset < total_size:
            chunk_data = data[offset : offset + chunk_size]
            chunks.append((offset, chunk_data))
            offset += len(chunk_data)

        processed = 0
        lock = None
        if on_progress:
            import threading

            lock = threading.Lock()

        def upload_one(args):
            nonlocal processed
            chunk_offset, chunk_data = args
            self.upload_chunk(upload_id, chunk_offset, chunk_data)
            if on_progress and lock:
                with lock:
                    nonlocal processed
                    processed += len(chunk_data)
                    on_progress(processed, total_size)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(upload_one, chunk) for chunk in chunks]
            for future in as_completed(futures):
                future.result()  # Raise any exceptions

    def upload(
        self,
        data: Union[bytes, BinaryIO],
        total_size: Optional[int] = None,
        on_progress: Optional[ProgressCallback] = None,
    ) -> TurboUploadResponse:
        """
        Perform complete chunked upload

        Args:
            data: Data to upload (bytes or file-like object)
            total_size: Total size in bytes (required for BinaryIO)
            on_progress: Optional progress callback

        Returns:
            TurboUploadResponse with transaction details
        """
        # Determine total size
        if isinstance(data, bytes):
            total_size = len(data)
        elif total_size is None:
            raise ValueError("total_size required for file-like objects")

        # Initiate upload
        init = self.initiate()

        try:
            # Upload chunks
            if (
                self.params.max_chunk_concurrency > 1
                and isinstance(data, bytes)
            ):
                self.upload_chunks_concurrent(
                    init.id, data, total_size, on_progress
                )
            else:
                self.upload_chunks_sequential(
                    init.id, data, total_size, on_progress
                )

            # Finalize
            self.finalize(init.id)

            # Poll for completion
            status = self.poll_for_finalization(init.id, total_size)

            return TurboUploadResponse(
                id=status.id or "",
                owner=status.owner or "",
                data_caches=status.data_caches,
                fast_finality_indexes=status.fast_finality_indexes,
                winc=status.winc or "0",
            )
        except Exception:
            # Could implement cleanup here in future
            raise
