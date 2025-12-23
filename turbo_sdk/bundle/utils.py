import base64


def b64url_decode(s: str) -> bytes:
    """Decode a base64url-encoded string (with or without padding)"""
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def set_bytes(dest: bytearray, src: bytearray, offset: int):
    """Set bytes in destination array at offset"""
    for i in range(offset, offset + len(src), 1):
        dest[i] = src[i - offset]


def byte_array_to_long(byte_array: bytearray):
    """Convert byte array to long using little-endian"""
    value = 0
    for i in range(len(byte_array) - 1, -1, -1):
        value = value * 256 + byte_array[i]
    return value
