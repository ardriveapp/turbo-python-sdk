SIG_CONFIG = {
    1: {"sigLength": 512, "pubLength": 512, "sigName": "arweave"},
    2: {"sigLength": 64, "pubLength": 32, "sigName": "ed25519"},
    3: {"sigLength": 65, "pubLength": 65, "sigName": "ethereum"},
    4: {"sigLength": 64, "pubLength": 32, "sigName": "solana"},
    5: {"sigLength": 64, "pubLength": 32, "sigName": "injectedAptos"},
    6: {"sigLength": 64 * 32 + 4, "pubLength": 32 * 32 + 1, "sigName": "multiAptos"},
    7: {"sigLength": 65, "pubLength": 42, "sigName": "typedEthereum"},
}

MAX_TAG_BYTES = 4096
MIN_BINARY_SIZE = 80
