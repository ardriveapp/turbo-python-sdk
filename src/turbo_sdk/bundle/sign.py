import hashlib


def deep_hash(data) -> bytearray:
    """
    Create a deep hash using the exact Irys/ANS-104 algorithm
    """
    if isinstance(data, list):
        tag = b"list" + str(len(data)).encode()
        return deep_hash_chunks(data, hashlib.sha384(tag).digest())
    else:
        if isinstance(data, str):
            data = data.encode('utf-8')
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
        "1",         # Version as string
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