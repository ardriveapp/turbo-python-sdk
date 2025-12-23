# turbo-python-sdk

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
