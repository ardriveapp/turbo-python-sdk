def set_bytes(target_array, source_array, offset):
    target_array[offset : offset + len(source_array)] = source_array
