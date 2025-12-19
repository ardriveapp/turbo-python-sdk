import struct


def encode_tags(tags):
    if not tags:
        return bytearray(16)

    tags_data = bytearray()

    for tag in tags:
        name = tag.get("name", "").encode("utf-8")
        value = tag.get("value", "").encode("utf-8")

        name_length = len(name)
        value_length = len(value)

        tags_data.extend(struct.pack("<Q", name_length))
        tags_data.extend(struct.pack("<Q", value_length))
        tags_data.extend(name)
        tags_data.extend(value)

    tag_count = len(tags)
    total_length = len(tags_data)

    result = bytearray()
    result.extend(struct.pack("<Q", tag_count))
    result.extend(struct.pack("<Q", total_length))
    result.extend(tags_data)

    return result


def decode_tags(data):
    if len(data) < 16:
        return []

    tag_count = struct.unpack("<Q", data[0:8])[0]

    if tag_count == 0:
        return []

    tags = []
    offset = 16

    for _ in range(tag_count):
        if offset + 16 > len(data):
            break

        name_length = struct.unpack("<Q", data[offset : offset + 8])[0]
        value_length = struct.unpack("<Q", data[offset + 8 : offset + 16])[0]
        offset += 16

        if offset + name_length + value_length > len(data):
            break

        name = data[offset : offset + name_length].decode("utf-8")
        offset += name_length

        value = data[offset : offset + value_length].decode("utf-8")
        offset += value_length

        tags.append({"name": name, "value": value})

    return tags
