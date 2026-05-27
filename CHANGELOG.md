# turbo-python-sdk

## 0.1.0

### Added

- `SolanaSigner` for signing data items with a Solana (ed25519) wallet. Accepts a Solana CLI `id.json` (via `SolanaSigner.from_file()` or a 64-int list), a base58-encoded secret key, a raw 64-byte secret key, or a 32-byte seed; the wallet address is the base58 of the ed25519 public key. Uses ANS-104 signature type 2 (raw ED25519), which Turbo bills as the `solana` token. Verified end-to-end against the upload backend and cross-checked byte-for-byte with `@dha-team/arbundles`.
- `TOKEN_MAP` entry mapping signature type 2 to the `solana` token so `Turbo(SolanaSigner(...))` initializes correctly.

### Fixed

- Aligned `pyproject.toml` version (was `0.0.6`) with `turbo_sdk.__version__` (`0.1.0`), which had drifted apart.

## 0.0.6

### Added

- Added timestamp, signature, public, version, and deadline_height to TurboUploadResponse and TurboUploadStatus data classes
- Extracted receipt fields in `_upload_single()` from API response JSON (previously discarded)
- Extracted receipt fields in `get_status()` from chunked upload receipt dict
- Carried all fields through the `TurboUploadStatus` → `TurboUploadResponse` conversion

## 0.0.5

### Added

- Multipart upload support with progress callbacks
- True streaming upload support with `StreamingDataItem`
- Stream factory pattern for reliable stream handling during signing

### Fixed

- Read `BinaryIO` into bytes so stream factory survives `sign()` close

### Changed

- Refactored signer from constructor to `sign()` method on `StreamingDataItem`
- Updated mypy Python version target
- Pinned `black` dependency version to avoid failures with Python 3.11

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
