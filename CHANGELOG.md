# turbo-python-sdk

## 0.0.4

### Added

- Stream signing support for large files via `sign_stream()` function
- `deep_hash_blob_stream()` for streaming hash computation without loading entire payload into memory
- `get_signature_data_stream()` for computing signature hash with streaming data
- Progress callback support: `on_progress(processed_bytes, total_bytes)` during signing
- Default chunk size of 256 KiB (matches Arweave chunk size)
- Exported new functions from `turbo_sdk.bundle` module

## 0.0.3

### Changed

- Moved `turbo_sdk` package from `src/` to root directory
- Extracted `b64url_decode` utility function to `turbo_sdk/bundle/utils.py`

## 0.0.2

### Changed

- Moved `get_wallet_address()` to Signer base class with implementations in ArweaveSigner and EthereumSigner
- Moved `create_signed_headers()` to Signer base class (shared implementation for all signers)
- Removed `get_wallet_address()` and `_create_signed_headers()` from Turbo client
- Removed `target` parameter from `upload()` method

## 0.1.0

Initial release of the Turbo Python SDK.

### Features

- Basic client structure for interacting with Turbo service
- Type hints and modern Python packaging setup
