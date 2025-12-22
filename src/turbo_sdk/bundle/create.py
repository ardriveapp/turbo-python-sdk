from typing import Optional, List, Dict
from .dataitem import DataItem
from .tags import encode_tags
from .constants import SIG_CONFIG
from .utils import set_bytes
import struct
import os


def create_data(
    data: bytearray,
    signer,
    tags: Optional[List[Dict[str, str]]] = None,
    target: Optional[str] = None,
    anchor: Optional[str] = None,
) -> DataItem:
    """
    Create a DataItem with the provided data and signer
    Returns a DataItem that matches the Irys binary format exactly

    Args:
        data: The data to be included in the DataItem
        signer: The signer object with signature_type, public_key, etc.
        tags: Optional list of tags as dictionaries with 'name' and 'value' keys
        target: Optional target address (hex string)
        anchor: Optional anchor (hex string)

    Returns:
        DataItem ready to be signed
    """

    # Get signature configuration
    sig_config = SIG_CONFIG[signer.signature_type]
    sig_length = sig_config["sigLength"]
    pub_length = sig_config["pubLength"]

    # Process tags
    if tags is None:
        tags = []
    encoded_tags = encode_tags(tags)

    # Process target
    target_bytes = bytearray(32)  # Initialize with zeros
    target_present = False
    if target:
        target_hex = target.replace("0x", "")
        target_data = bytes.fromhex(target_hex)
        if len(target_data) > 32:
            raise ValueError("Target must be 32 bytes or less")
        # Copy target data to the beginning of target_bytes
        for i, b in enumerate(target_data):
            target_bytes[i] = b
        target_present = True

    # Process anchor
    anchor_bytes = bytearray(32)  # Initialize with zeros
    if anchor:
        if isinstance(anchor, str):
            anchor_data = anchor.encode("utf-8")
        else:
            anchor_data = anchor
        if len(anchor_data) > 32:
            raise ValueError("Anchor must be 32 bytes or less")
        # Copy anchor data to the beginning of anchor_bytes
        for i, b in enumerate(anchor_data):
            anchor_bytes[i] = b
    else:
        # Generate random anchor if none provided
        random_anchor = os.urandom(32)
        for i, b in enumerate(random_anchor):
            anchor_bytes[i] = b

    # Calculate total size
    total_size = (
        2  # signature type
        + sig_length  # signature
        + pub_length  # owner/public key
        + 1  # target present flag
        + (32 if target_present else 0)  # target
        + 1  # anchor present flag
        + 32  # anchor (always present)
        + 8  # number of tags
        + 8  # tag data length
        + len(encoded_tags)  # tag data
        + len(data)  # data
    )

    # Create binary buffer
    binary = bytearray(total_size)
    offset = 0

    # 1. Signature type (2 bytes, little-endian)
    struct.pack_into("<H", binary, offset, signer.signature_type)
    offset += 2

    # 2. Signature (will be filled when signing)
    offset += sig_length

    # 3. Owner/public key
    set_bytes(binary, signer.public_key, offset)
    offset += pub_length

    # 4. Target present flag
    binary[offset] = 1 if target_present else 0
    offset += 1

    # 5. Target (32 bytes, only if present)
    if target_present:
        set_bytes(binary, target_bytes, offset)
        offset += 32

    # 6. Anchor present flag (always 1)
    binary[offset] = 1
    offset += 1

    # 7. Anchor (32 bytes, always present)
    set_bytes(binary, anchor_bytes, offset)
    offset += 32

    # 8. Number of tags (8 bytes, little-endian)
    struct.pack_into("<Q", binary, offset, len(tags))
    offset += 8

    # 9. Tag data length (8 bytes, little-endian)
    struct.pack_into("<Q", binary, offset, len(encoded_tags))
    offset += 8

    # 10. Tag data
    set_bytes(binary, encoded_tags, offset)
    offset += len(encoded_tags)

    # 11. Data
    set_bytes(binary, data, offset)

    return DataItem(binary)
