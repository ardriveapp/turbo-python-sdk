def _encode_varint(value):
    # cSpell:ignore varint
    """Encode a positive integer as a variable-length integer (Avro zigzag + varint encoding)"""
    # Zigzag encoding for signed integers (even though we're using positive values)
    zigzag = (value << 1) ^ (value >> 63)

    result = bytearray()
    while zigzag >= 0x80:
        result.append((zigzag & 0x7F) | 0x80)
        zigzag >>= 7
    result.append(zigzag & 0x7F)
    return result


def _encode_bytes(data):
    """Encode bytes with Avro bytes encoding (length + data)"""
    if isinstance(data, str):
        data = data.encode("utf-8")

    result = bytearray()
    result.extend(_encode_varint(len(data)))
    result.extend(data)
    return result


def encode_tags(tags):
    """
    Encode tags using Apache Avro format as required by ANS-104.

    Tags are encoded as an Avro array of records, where each record has:
    { "name": "bytes", "value": "bytes" }
    """
    if not tags:
        # Empty array: count = 0
        return bytearray([0x00])

    result = bytearray()

    # Encode array count (number of tags)
    result.extend(_encode_varint(len(tags)))

    # Encode each tag as a record
    for tag in tags:
        name = tag.get("name", "")
        value = tag.get("value", "")

        # Encode name as bytes
        result.extend(_encode_bytes(name))

        # Encode value as bytes
        result.extend(_encode_bytes(value))

    # Array terminator (count = 0)
    result.append(0x00)

    return result


def _decode_varint(data, offset):
    """Decode a variable-length integer from data starting at offset"""
    value = 0
    shift = 0
    pos = offset

    while pos < len(data):
        byte = data[pos]
        value |= (byte & 0x7F) << shift
        pos += 1

        if (byte & 0x80) == 0:
            break
        shift += 7

    # Zigzag decode
    return (value >> 1) ^ (-(value & 1)), pos


def _decode_bytes(data, offset):
    """Decode bytes from data starting at offset"""
    length, new_offset = _decode_varint(data, offset)

    if new_offset + length > len(data):
        raise ValueError("Invalid bytes length")

    bytes_data = data[new_offset : new_offset + length]
    return bytes_data.decode("utf-8"), new_offset + length


def decode_tags(data):
    """
    Decode tags from Apache Avro format.
    """
    if not data:
        return []

    tags = []
    offset = 0

    try:
        # Decode array count
        count, offset = _decode_varint(data, offset)

        # Decode each tag
        for _ in range(count):
            if offset >= len(data):
                break

            # Decode name
            name, offset = _decode_bytes(data, offset)

            # Decode value
            value, offset = _decode_bytes(data, offset)

            tags.append({"name": name, "value": value})

        return tags

    except Exception:
        # If decoding fails, return empty list
        return []
