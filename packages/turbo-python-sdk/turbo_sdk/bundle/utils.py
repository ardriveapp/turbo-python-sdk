def long_to_8_byte_array(value):
    return value.to_bytes(8, byteorder="little")


def set_bytes(target_array, source_array, offset):
    target_array[offset : offset + len(source_array)] = source_array


def byte_array_to_long(byte_array):
    return int.from_bytes(byte_array, byteorder="little")
