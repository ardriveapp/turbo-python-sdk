import hashlib
from .dataitem import DataItem


def deep_hash(data) -> bytearray:
    """
    Create a deep hash of the data using SHA-384

    Args:
        data: The data to hash

    Returns:
        SHA-384 hash as bytearray
    """
    if isinstance(data, list):
        # For arrays, hash each element and concatenate
        hasher = hashlib.sha384()
        hasher.update(b"list")
        hasher.update(len(data).to_bytes(8, "big"))

        for item in data:
            item_hash = deep_hash(item)
            hasher.update(item_hash)

        return bytearray(hasher.digest())

    elif isinstance(data, (bytes, bytearray)):
        # For binary data, hash directly
        hasher = hashlib.sha384()
        hasher.update(b"blob")
        hasher.update(len(data).to_bytes(8, "big"))
        hasher.update(data)
        return bytearray(hasher.digest())

    elif isinstance(data, str):
        # For strings, encode as UTF-8 then hash
        encoded = data.encode("utf-8")
        return deep_hash(encoded)

    else:
        # For other types, convert to string
        return deep_hash(str(data))


def get_signature_data(dataitem: DataItem) -> bytearray:
    """
    Get the data that needs to be signed for a DataItem

    Args:
        dataitem: The DataItem to get signature data for

    Returns:
        The data to be signed as bytearray
    """
    # Build the signature data by concatenating relevant fields
    signature_data = []

    # Add each component for deep hashing
    signature_data.append(b"dataitem")
    signature_data.append(b"1")  # Version
    signature_data.append(dataitem.signature_type.to_bytes(2, "little"))
    signature_data.append(dataitem.owner)
    signature_data.append(dataitem.target)
    signature_data.append(dataitem.anchor)
    signature_data.append(dataitem.tags)
    signature_data.append(dataitem.data)

    # Create deep hash of all components
    return deep_hash(signature_data)


def sign(dataitem: DataItem, signer) -> DataItem:
    """
    Sign a DataItem using the provided signer

    Args:
        dataitem: The DataItem to sign
        signer: The signer object with a sign() method

    Returns:
        The signed DataItem
    """
    # Get the data to be signed
    signature_data = get_signature_data(dataitem)

    # Sign the data using the signer
    signature = signer.sign(signature_data)

    # Set the signature on the dataitem
    dataitem.signature = signature

    return dataitem
