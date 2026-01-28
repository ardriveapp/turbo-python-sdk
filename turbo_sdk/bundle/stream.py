"""Streaming DataItem support for large file uploads."""

import base64
import hashlib
import os
from typing import BinaryIO, Callable, Dict, List, Optional

from base58 import b58encode

from .constants import SIG_CONFIG
from .create import create_data_header
from .sign import sign_stream
from .tags import encode_tags

# Type alias for stream factory
StreamFactory = Callable[[], BinaryIO]


class StreamingDataItem:
    """
    Wraps a data stream with DataItem header for streaming uploads.

    This class enables uploading large files without loading the entire
    file into memory. It:
    1. Uses sign_stream to compute the signature by streaming through data
    2. Builds the DataItem header with the computed signature
    3. Provides a read() interface that returns header bytes first, then data

    After sign(), exposes the same properties as DataItem:
    id, raw_id, signature, raw_signature, signature_type,
    owner, raw_owner, raw_target, raw_anchor, tags.

    Uses a stream_factory pattern: a callable that returns a fresh stream
    each time it's called. This allows:
    - Non-seekable streams (generators, network streams, etc.)
    - Clean separation between signing pass and upload pass
    - Easy retries by creating a new stream

    Usage:
        def open_file():
            return open("large_file.bin", "rb")

        streaming = StreamingDataItem(
            stream_factory=open_file,
            data_size=file_size,
            tags=tags,
        )
        streaming.sign(signer)
        # Now use streaming.read() to get chunks for upload
    """

    def __init__(
        self,
        stream_factory: StreamFactory,
        data_size: int,
        tags: Optional[List[Dict[str, str]]] = None,
        on_sign_progress: Optional[Callable[[int, int], None]] = None,
    ):
        """
        Initialize a StreamingDataItem.

        Args:
            stream_factory: A callable that returns a fresh BinaryIO stream
            data_size: Total size of the data in bytes
            tags: Optional list of tags as dictionaries with 'name' and 'value'
            on_sign_progress: Optional callback(processed, total) during signing
        """
        self._stream_factory = stream_factory
        self._data_size = data_size
        self._tags = tags or []
        self._on_sign_progress = on_sign_progress

        self._header: Optional[bytes] = None
        self._header_offset = 0
        self._signed = False
        self._signer = None
        self._signature: Optional[bytes] = None
        self._anchor: Optional[bytes] = None
        self._data_stream: Optional[BinaryIO] = None

    def sign(self, signer) -> bytes:
        """
        Sign the data (streaming) and build the header.

        This creates a fresh stream from the factory to compute the signature,
        then creates another fresh stream for the upload phase.

        Args:
            signer: The signer object with signature_type, public_key, sign()

        Returns:
            The raw ID (SHA-256 of the signature)
        """
        if self._signed:
            return self.raw_id

        self._signer = signer

        # Generate random anchor
        self._anchor = os.urandom(32)

        # Encode tags for signing
        encoded_tags = encode_tags(self._tags)

        # Create a stream for signing
        sign_stream_obj = self._stream_factory()

        # Compute signature by streaming through data
        self._signature = sign_stream(
            signature_type=signer.signature_type,
            raw_owner=signer.public_key,
            raw_target=b"",
            raw_anchor=self._anchor,
            raw_tags=encoded_tags,
            data_stream=sign_stream_obj,
            data_size=self._data_size,
            signer=signer,
            on_progress=self._on_sign_progress,
        )

        # Close the signing stream if it has a close method
        if hasattr(sign_stream_obj, "close"):
            try:
                sign_stream_obj.close()
            except Exception:
                pass  # Ignore close errors

        # Create a fresh stream for upload
        self._data_stream = self._stream_factory()

        # Build header with the computed signature
        self._header = create_data_header(
            signer=signer,
            signature=self._signature,
            tags=self._tags,
            anchor=self._anchor,
        )

        self._signed = True
        return self.raw_id

    @property
    def is_signed(self) -> bool:
        return self._signed

    @property
    def signature_type(self) -> int:
        if not self._signed:
            raise RuntimeError("Must call sign() first")
        return self._signer.signature_type

    @property
    def raw_signature(self) -> bytes:
        if not self._signed:
            raise RuntimeError("Must call sign() first")
        return self._signature

    @property
    def signature(self) -> bytes:
        return base64.urlsafe_b64encode(self.raw_signature)

    @property
    def raw_id(self) -> bytes:
        return hashlib.sha256(self.raw_signature).digest()

    @property
    def id(self) -> str:
        return b58encode(self.raw_id).decode("utf-8")

    @property
    def raw_owner(self) -> bytes:
        if not self._signed:
            raise RuntimeError("Must call sign() first")
        return self._signer.public_key

    @property
    def owner(self) -> bytes:
        return base64.urlsafe_b64encode(self.raw_owner)

    @property
    def raw_target(self) -> bytes:
        return b""

    @property
    def raw_anchor(self) -> bytes:
        if not self._signed:
            raise RuntimeError("Must call sign() first")
        return self._anchor

    @property
    def tags(self) -> List[Dict[str, str]]:
        return self._tags

    @property
    def total_size(self) -> int:
        """Total size in bytes (header + data). Must call sign() first."""
        if not self._signed:
            raise RuntimeError("Must call sign() first")
        return len(self._header) + self._data_size

    @property
    def header_size(self) -> int:
        """Size of the header in bytes. Must call sign() first."""
        if not self._signed:
            raise RuntimeError("Must call sign() first")
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
            RuntimeError: If sign() has not been called
        """
        if not self._signed:
            raise RuntimeError("Must call sign() first")

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

    def reset(self) -> None:
        """
        Reset the streaming position to allow re-reading.

        Creates a fresh data stream from the factory and resets the header offset.
        """
        if not self._signed:
            raise RuntimeError("Must call sign() first")
        self._header_offset = 0
        # Close existing stream if it has a close method
        if self._data_stream is not None and hasattr(self._data_stream, "close"):
            try:
                self._data_stream.close()
            except Exception:
                pass  # Ignore close errors
        # Create fresh stream from factory
        self._data_stream = self._stream_factory()
