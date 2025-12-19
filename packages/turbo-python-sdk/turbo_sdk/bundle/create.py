from typing import Optional, List, Dict
from .dataitem import DataItem
from .tags import encode_tags
from .utils import set_bytes
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

    Args:
        data: The data to be included in the DataItem
        signer: The signer object with signature_type, owner, etc.
        tags: Optional list of tags as dictionaries with 'name' and 'value' keys
        target: Optional target address (hex string)
        anchor: Optional anchor (hex string)

    Returns:
        DataItem ready to be signed
    """
    dataitem = DataItem(signer.signature_type)

    # Set owner from signer
    dataitem.owner = bytearray(signer.public_key)

    # Set target if provided
    if target:
        target_bytes = bytes.fromhex(target.replace("0x", ""))
        if len(target_bytes) > 32:
            raise ValueError("Target must be 32 bytes or less")
        set_bytes(dataitem.target, target_bytes, 0)

    # Set anchor if provided
    if anchor:
        if isinstance(anchor, str):
            anchor_bytes = anchor.encode("utf-8")
        else:
            anchor_bytes = anchor
        if len(anchor_bytes) > 32:
            raise ValueError("Anchor must be 32 bytes or less")
        set_bytes(dataitem.anchor, anchor_bytes, 0)
    else:
        # Generate random anchor if none provided
        random_anchor = os.urandom(32)
        set_bytes(dataitem.anchor, random_anchor, 0)

    # Encode tags
    if tags:
        dataitem.tags = encode_tags(tags)
    else:
        dataitem.tags = encode_tags([])

    # Set data
    dataitem.data = data

    return dataitem
