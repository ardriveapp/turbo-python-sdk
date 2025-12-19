# Turbo Python SDK

A Python SDK for interacting with the Turbo datachain, supporting both Ethereum and Arweave signers for permanent data storage with winston credit payments.

## Get Started

### Installation

```bash
pip install turbo-sdk
```

### Quick Start

#### Ethereum Usage

```python
from turbo_sdk import Turbo, EthereumSigner

# Create Ethereum signer
signer = EthereumSigner("0x1234567890abcdef...")  # Your private key

# Create Turbo client
turbo = Turbo(signer, network="mainnet")

# Upload data
result = turbo.upload(b"Hello, Turbo!", tags=[
    {"name": "Content-Type", "value": "text/plain"},
    {"name": "App-Name", "value": "MyApp"}
])

print(f"✅ Uploaded! TX ID: {result.id}")
print(f"🌐 View at: https://arweave.net/{result.id}")
```

#### Arweave Usage

```python
import json
from turbo_sdk import Turbo, ArweaveSigner

# Load Arweave wallet (JWK format)
with open("test-wallet.json") as f:
    jwk = json.load(f)

# Create Arweave signer
signer = ArweaveSigner(jwk)

# Create Turbo client
turbo = Turbo(signer, network="mainnet")

# Upload data
result = turbo.upload(b"Hello from Arweave!", tags=[
    {"name": "Content-Type", "value": "text/plain"}
])

print(f"✅ Uploaded! URI: ar://{result.id}")
```

## APIs

### Core Classes

#### `Turbo(signer, network="mainnet")`

Main client for interacting with Turbo services.

**Parameters:**
- `signer`: Either `EthereumSigner` or `ArweaveSigner` instance
- `network`: `"mainnet"` or `"testnet"` (default: `"mainnet"`)

**Methods:**

##### `upload(data, tags=None, target=None) -> TurboUploadResponse`

Upload data to the Turbo datachain.

```python
result = turbo.upload(
    data=b"Your data here",
    tags=[
        {"name": "Content-Type", "value": "application/json"},
        {"name": "App-Name", "value": "MyApp"}
    ],
    target="optional_target_address"
)
```

**Returns:** `TurboUploadResponse`
```python
@dataclass
class TurboUploadResponse:
    id: str                        # Transaction ID
    owner: str                     # Owner address
    data_caches: List[str]         # Cache endpoints
    fast_finality_indexes: List[str] # Fast finality indexes
    winc: str                      # Winston credits cost
```

##### `get_balance(address=None) -> TurboBalanceResponse`

Get winston credit balance for an address.

```python
balance = turbo.get_balance()
print(f"Balance: {balance.winc} winc")
```

**Returns:** `TurboBalanceResponse`
```python
@dataclass
class TurboBalanceResponse:
    winc: str                      # Available winston credits
    controlled_winc: str           # Controlled amount
    effective_balance: str         # Effective balance including shared credits
```

##### `get_upload_price(byte_count) -> int`

Get the cost to upload data of a specific size.

```python
cost = turbo.get_upload_price(1024)  # Cost for 1KB
print(f"Upload cost: {cost} winc")
```

### Signers

#### `EthereumSigner(private_key)`

Ethereum signer using ECDSA signatures.

**Parameters:**
- `private_key` (str): Hex private key with or without `0x` prefix

```python
signer = EthereumSigner("0x1234567890abcdef...")
```

#### `ArweaveSigner(jwk)`

Arweave signer using RSA-PSS signatures.

**Parameters:**
- `jwk` (dict): Arweave wallet in JWK format

```python
signer = ArweaveSigner({
    "kty": "RSA",
    "n": "...",
    "e": "AQAB",
    "d": "...",
    # ... other JWK fields
})
```


## Developers

### Setup

1. **Crete a virtual environment:**

```bash
python -m venv venv
source venv/bin/activate 
```

1. **Install dependencies:**

```bash
pip install -e ".[dev]"
```

2. **Run tests:**

```bash
pytest
```

That's it! The test suite includes comprehensive tests for all components without requiring network access.

## Acknowledgments

This package leverages implementations from the [Irys Python SDK](https://github.com/Irys-xyz/python-sdk) for ANS-104 DataItem format and cryptographic operations. Special thanks to the Irys team for their work on permanent data storage standards.

## License

MIT License - see [LICENSE](../../LICENSE) for details.
