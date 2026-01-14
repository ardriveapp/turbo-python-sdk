import hashlib
from typing import BinaryIO, Callable, Optional


def deep_hash(data) -> bytearray:
    """
    Create a deep hash using the exact Irys/ANS-104 algorithm
    """
    if isinstance(data, list):
        tag = b"list" + str(len(data)).encode()
        return deep_hash_chunks(data, hashlib.sha384(tag).digest())
    else:
        if isinstance(data, str):
            data = data.encode("utf-8")
        tag = b"blob" + str(len(data)).encode()
        tagged_hash = hashlib.sha384(tag).digest() + hashlib.sha384(data).digest()
        return hashlib.sha384(tagged_hash).digest()


def deep_hash_chunks(chunks, acc: bytearray):
    """
    Recursively hash chunks for deep hash algorithm
    """
    if len(chunks) < 1:
        return acc
    hash_pair = acc + deep_hash(chunks[0])
    new_acc = hashlib.sha384(hash_pair).digest()
    return deep_hash_chunks(chunks[1:], new_acc)


def get_signature_data(dataitem) -> bytearray:
    """
    Get the data that needs to be signed for a DataItem
    Using exact Irys implementation
    """
    signature_data = [
        "dataitem",  # String, will be encoded to UTF-8 by deep_hash
        "1",  # Version as string
        str(dataitem.signature_type),  # Signature type as string (KEY FIX!)
        dataitem.raw_owner,
        dataitem.raw_target,
        dataitem.raw_anchor,
        dataitem.raw_tags,
        dataitem.raw_data,
    ]

    return deep_hash(signature_data)


def sign(dataitem, signer):
    """
    Sign a DataItem using the provided signer
    """
    signature_data = get_signature_data(dataitem)
    signature = signer.sign(signature_data)
    dataitem.set_signature(signature)
    return hashlib.sha256(signature).digest()


# Default chunk size for streaming: 256 KiB (matches Arweave chunk size)
DEFAULT_STREAM_CHUNK_SIZE = 256 * 1024


def deep_hash_blob_stream(
    stream: BinaryIO,
    data_size: int,
    chunk_size: int = DEFAULT_STREAM_CHUNK_SIZE,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> bytes:
    """
    Compute deep hash of a blob by streaming data without loading it all into memory.

    Args:
        stream: A file-like object supporting read()
        data_size: Total size of the data in bytes (must be known upfront)
        chunk_size: Size of chunks to read at a time (default 64KB)
        on_progress: Optional callback(processed_bytes, total_bytes) called after each chunk

    Returns:
        The deep hash as bytes
    """
    # Compute tag hash - requires knowing size upfront
    tag = b"blob" + str(data_size).encode()
    tag_hash = hashlib.sha384(tag).digest()

    # Stream data through SHA-384
    data_hasher = hashlib.sha384()
    bytes_processed = 0

    while bytes_processed < data_size:
        remaining = data_size - bytes_processed
        to_read = min(chunk_size, remaining)
        chunk = stream.read(to_read)

        if not chunk:
            raise ValueError(
                f"Stream ended prematurely: expected {data_size} bytes, got {bytes_processed}"
            )

        data_hasher.update(chunk)
        bytes_processed += len(chunk)

        if on_progress:
            on_progress(bytes_processed, data_size)

    # Combine tag hash and data hash, then hash again
    tagged_hash = tag_hash + data_hasher.digest()
    return hashlib.sha384(tagged_hash).digest()


def deep_hash_chunks_with_final_stream(
    chunks: list,
    acc: bytes,
    final_stream: BinaryIO,
    final_size: int,
    chunk_size: int = DEFAULT_STREAM_CHUNK_SIZE,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> bytes:
    """
    Process deep hash chunks where the final element is a stream.

    This processes all chunks except the last one normally, then streams the final chunk.
    """
    if len(chunks) == 0:
        # No more regular chunks, process the stream as final element
        final_hash = deep_hash_blob_stream(final_stream, final_size, chunk_size, on_progress)
        hash_pair = acc + final_hash
        return hashlib.sha384(hash_pair).digest()

    # Process current chunk normally
    hash_pair = acc + deep_hash(chunks[0])
    new_acc = hashlib.sha384(hash_pair).digest()
    return deep_hash_chunks_with_final_stream(
        chunks[1:], new_acc, final_stream, final_size, chunk_size, on_progress
    )


def get_signature_data_stream(
    signature_type: int,
    raw_owner: bytes,
    raw_target: bytes,
    raw_anchor: bytes,
    raw_tags: bytes,
    data_stream: BinaryIO,
    data_size: int,
    chunk_size: int = DEFAULT_STREAM_CHUNK_SIZE,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> bytes:
    """
    Compute signature data hash with streaming support for the data portion.

    This is equivalent to get_signature_data() but streams the data instead of
    loading it all into memory.

    Args:
        signature_type: The signature type (1 for Arweave, 3 for Ethereum)
        raw_owner: The raw owner/public key bytes
        raw_target: The raw target bytes (empty if none)
        raw_anchor: The raw anchor bytes (empty if none)
        raw_tags: The raw encoded tags bytes
        data_stream: A file-like object for reading the data
        data_size: Total size of the data in bytes
        chunk_size: Size of chunks to read (default 64KB)
        on_progress: Optional callback(processed_bytes, total_bytes)

    Returns:
        The signature data hash as bytes
    """
    # All elements except raw_data - these are processed normally
    prefix_elements = [
        "dataitem",
        "1",
        str(signature_type),
        raw_owner,
        raw_target,
        raw_anchor,
        raw_tags,
    ]

    # Start the list deep hash
    tag = b"list" + str(len(prefix_elements) + 1).encode()  # +1 for the streamed data
    acc = hashlib.sha384(tag).digest()

    # Process prefix elements, then stream the final data element
    return deep_hash_chunks_with_final_stream(
        prefix_elements, acc, data_stream, data_size, chunk_size, on_progress
    )


def sign_stream(
    signature_type: int,
    raw_owner: bytes,
    raw_target: bytes,
    raw_anchor: bytes,
    raw_tags: bytes,
    data_stream: BinaryIO,
    data_size: int,
    signer,
    chunk_size: int = DEFAULT_STREAM_CHUNK_SIZE,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> bytes:
    """
    Sign streaming data without loading the entire payload into memory.

    This computes the signature by streaming the data through the deep hash algorithm,
    then signs the result.

    Args:
        signature_type: The signature type (1 for Arweave, 3 for Ethereum)
        raw_owner: The raw owner/public key bytes
        raw_target: The raw target bytes (empty if none)
        raw_anchor: The raw anchor bytes (empty if none)
        raw_tags: The raw encoded tags bytes
        data_stream: A file-like object for reading the data
        data_size: Total size of the data in bytes
        signer: The signer instance with a sign() method
        chunk_size: Size of chunks to read (default 64KB)
        on_progress: Optional callback(processed_bytes, total_bytes) for signing progress

    Returns:
        The signature bytes
    """
    signature_data = get_signature_data_stream(
        signature_type=signature_type,
        raw_owner=raw_owner,
        raw_target=raw_target,
        raw_anchor=raw_anchor,
        raw_tags=raw_tags,
        data_stream=data_stream,
        data_size=data_size,
        chunk_size=chunk_size,
        on_progress=on_progress,
    )

    return signer.sign(signature_data)
