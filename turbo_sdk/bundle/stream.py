"""Streaming DataItem support for large file uploads."""

import os
from typing import BinaryIO, Callable, Dict, List, Optional

from .create import create_data_header
from .sign import sign_stream
from .tags import encode_tags


class StreamingDataItem:
    """
    Wraps a data stream with DataItem header for streaming uploads.

    This class enables uploading large files without loading the entire
    file into memory. It:
    1. Uses sign_stream to compute the signature by streaming through data
    2. Builds the DataItem header with the computed signature
    3. Provides a read() interface that returns header bytes first, then data

    The underlying stream must be seekable (supports seek(0)) because:
    - First pass: read through data to compute signature hash
    - Second pass: read through data for upload

    Usage:
        with open("large_file.bin", "rb") as f:
            streaming = StreamingDataItem(f, file_size, signer, tags)
            total_size = streaming.prepare()
            # Now use streaming.read() to get chunks for upload
    """

    def __init__(
        self,
        data_stream: BinaryIO,
        data_size: int,
        signer,
        tags: Optional[List[Dict[str, str]]] = None,
        on_sign_progress: Optional[Callable[[int, int], None]] = None,
    ):
        """
        Initialize a StreamingDataItem.

        Args:
            data_stream: A seekable file-like object containing the data
            data_size: Total size of the data in bytes
            signer: The signer object with signature_type, public_key, sign()
            tags: Optional list of tags as dictionaries with 'name' and 'value'
            on_sign_progress: Optional callback(processed, total) during signing
        """
        self._data_stream = data_stream
        self._data_size = data_size
        self._signer = signer
        self._tags = tags or []
        self._on_sign_progress = on_sign_progress

        self._header: Optional[bytes] = None
        self._header_offset = 0
        self._prepared = False
        self._anchor: Optional[bytes] = None

    def prepare(self) -> int:
        """
        Sign the data (streaming) and prepare the header.

        This reads through the entire data stream to compute the signature,
        then seeks back to the start for the upload phase.

        Returns:
            Total size in bytes (header + data)

        Raises:
            RuntimeError: If stream is not seekable
        """
        if self._prepared:
            return len(self._header) + self._data_size

        # Verify stream is seekable
        if not self._data_stream.seekable():
            raise RuntimeError(
                "StreamingDataItem requires a seekable stream. "
                "For non-seekable streams, load data into memory first."
            )

        # Generate random anchor
        self._anchor = os.urandom(32)

        # Encode tags for signing
        encoded_tags = encode_tags(self._tags)

        # Compute signature by streaming through data
        signature = sign_stream(
            signature_type=self._signer.signature_type,
            raw_owner=self._signer.public_key,
            raw_target=b"",
            raw_anchor=self._anchor,
            raw_tags=encoded_tags,
            data_stream=self._data_stream,
            data_size=self._data_size,
            signer=self._signer,
            on_progress=self._on_sign_progress,
        )

        # Seek back to start for upload
        self._data_stream.seek(0)

        # Build header with the computed signature
        self._header = create_data_header(
            signer=self._signer,
            signature=signature,
            tags=self._tags,
            anchor=self._anchor,
        )

        self._prepared = True
        return len(self._header) + self._data_size

    @property
    def total_size(self) -> int:
        """Total size in bytes (header + data). Must call prepare() first."""
        if not self._prepared:
            raise RuntimeError("Must call prepare() first")
        return len(self._header) + self._data_size

    @property
    def header_size(self) -> int:
        """Size of the header in bytes. Must call prepare() first."""
        if not self._prepared:
            raise RuntimeError("Must call prepare() first")
        return len(self._header)

    def read(self, size: int = -1) -> bytes:
        """
        Read bytes from the streaming DataItem.

        Reads header bytes first, then data bytes. This method is compatible
        with the BinaryIO interface expected by ChunkedUploader.

        Args:
            size: Number of bytes to read. -1 means read all remaining.

        Returns:
            Bytes read (may be less than size if at end)

        Raises:
            RuntimeError: If prepare() has not been called
        """
        if not self._prepared:
            raise RuntimeError("Must call prepare() first")

        if size == 0:
            return b""

        result = bytearray()

        # Determine how many bytes to read
        if size < 0:
            # Read everything remaining
            remaining = float("inf")
        else:
            remaining = size

        # Read from header first
        if self._header_offset < len(self._header):
            header_remaining = len(self._header) - self._header_offset
            to_read = min(header_remaining, remaining)
            header_chunk = self._header[
                self._header_offset : self._header_offset + int(to_read)
            ]
            result.extend(header_chunk)
            self._header_offset += len(header_chunk)
            remaining -= len(header_chunk)

        # Then read from data stream
        if remaining > 0:
            if remaining == float("inf"):
                data_chunk = self._data_stream.read()
            else:
                data_chunk = self._data_stream.read(int(remaining))
            if data_chunk:
                result.extend(data_chunk)

        return bytes(result)

    def seekable(self) -> bool:
        """Return False - StreamingDataItem is forward-only after prepare()."""
        return False

    def reset(self) -> None:
        """
        Reset the streaming position to allow re-reading.

        This seeks the underlying data stream back to the start and
        resets the header offset.
        """
        if not self._prepared:
            raise RuntimeError("Must call prepare() first")
        self._header_offset = 0
        self._data_stream.seek(0)
