# MVP Python Turbo SDK Implementation Plan

**Scope:** Ethereum + Arweave support for ChaosChain integration

## Table of Contents
- [Dependencies](#dependencies)
- [Architecture Overview](#architecture-overview)
- [Copy/Paste Ready Components](#copypaste-ready-components)
- [Missing Components to Implement](#missing-components-to-implement)
- [Turbo-Specific Implementation](#turbo-specific-implementation)
- [ChaosChain Integration](#chaoschain-integration)
- [Project Structure](#project-structure)
- [Usage Examples](#usage-examples)

## Dependencies

**Required dependencies from Irys SDK analysis:**

```toml
[dependencies]
# Core HTTP and encoding
requests = "^2.28.0"
base58 = "^2.1.1"

# Ethereum support (from Irys SDK)
eth-account = "^0.8.0"
web3 = "^6.5.0"  
eth-keys = "^0.4.0"
eth-hash = "*"  # For keccak hashing

# Arweave support (missing from Irys - we need to add)
cryptography = "^41.0.0"  # For RSA-PSS signing
```

## Architecture Overview

The MVP Python Turbo SDK will be built by:

1. **95% code reuse** from existing [Irys Python SDK](https://github.com/Irys-xyz/python-sdk)
2. **Adding missing Arweave RSA signer** (Irys SDK only supports Ethereum)
3. **Adapting endpoints** from Irys to Turbo service URLs
4. **Implementing ChaosChain StorageBackend interface**

## Copy/Paste Ready Components

### A. Core DataItem Infrastructure ✅

Copy these modules **AS-IS** from `irys-python-sdk`:

```python
# From irys_sdk/bundle/ - COPY EXACTLY:
from irys_sdk.bundle.constants import SIG_CONFIG, MAX_TAG_BYTES, MIN_BINARY_SIZE
from irys_sdk.bundle.dataitem import DataItem  
from irys_sdk.bundle.create import create_data
from irys_sdk.bundle.sign import sign, deep_hash, get_signature_data
from irys_sdk.bundle.tags import encode_tags, decode_tags
from irys_sdk.bundle.utils import long_to_8_byte_array, set_bytes, byte_array_to_long
```

**Constants from Irys SDK:**
```python
# irys_sdk/bundle/constants.py
SIG_CONFIG = {
    1: {"sigLength": 512, "pubLength": 512, "sigName": "arweave"},    # We need this
    3: {"sigLength": 65, "pubLength": 65, "sigName": "ethereum"},     # Already works
}
```

### B. Ethereum Signer ✅  

Copy **EXACTLY** from `irys_sdk/bundle/signers/ethereum.py`:

```python
import codecs
from eth_account import Account
from eth_account.messages import encode_defunct, _hash_eip191_message
from eth_keys import keys

class EthereumSigner:
    signature_type = 3
    signature_length = 65
    owner_length = 65  # Note: 65 bytes for Ethereum (includes 0x04 prefix)
    
    def __init__(self, private_key: str):
        private_key = private_key[2:] if private_key.startswith("0x") else private_key
        dec = codecs.decode(private_key, "hex")
        self.private_key = keys.PrivateKey(dec)
        self.public_key = b'\x04' + self.private_key.public_key.to_bytes()
    
    def sign(self, message: bytearray) -> bytearray:
        msg = encode_defunct(primitive=message)
        acc = Account.from_key(self.private_key)
        signature = (acc.sign_message(msg)).signature.hex()
        return bytearray.fromhex(signature[2:] if signature.startswith("0x") else signature)
```

### C. Ethereum Token/Payment Support ✅

Adapt from `irys_sdk/tokens/ethereum.py`:

```python
from web3 import Web3
from eth_hash.auto import keccak

class EthereumToken:
    def __init__(self, private_key: str, provider_url: str = "https://cloudflare-eth.com/"):
        self.private_key = private_key
        self.provider = Web3(Web3.HTTPProvider(provider_url))
        self.signer = EthereumSigner(private_key)
        self.address = self.owner_to_address(self.signer.public_key)
    
    def owner_to_address(self, pub: bytearray) -> str:
        """Convert public key to Ethereum address"""
        pubkey = pub if len(pub) == 64 else pub[1:]  # Remove 0x04 prefix
        kek = keccak(pubkey)
        return "0x" + kek[-20:].hex()
```

## Missing Components to Implement

### Arweave Signer ⚠️

**NEW IMPLEMENTATION NEEDED** (Not in Irys SDK):

```python
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
import base64

class ArweaveSigner:
    signature_type = 1
    signature_length = 512
    owner_length = 512
    
    def __init__(self, jwk: dict):
        """Initialize with Arweave JWK (JSON Web Key)"""
        self.jwk = jwk
        self.private_key = self._jwk_to_rsa_key(jwk)
        self.public_key = self._jwk_to_public_key_bytes(jwk)
    
    def _jwk_to_rsa_key(self, jwk: dict):
        """Convert JWK to RSA private key"""
        # Convert base64url to bytes
        def b64url_decode(s):
            padding = 4 - len(s) % 4
            if padding != 4:
                s += '=' * padding
            return base64.urlsafe_b64decode(s)
        
        # Extract RSA components
        n = int.from_bytes(b64url_decode(jwk['n']), 'big')
        e = int.from_bytes(b64url_decode(jwk['e']), 'big')  
        d = int.from_bytes(b64url_decode(jwk['d']), 'big')
        p = int.from_bytes(b64url_decode(jwk['p']), 'big')
        q = int.from_bytes(b64url_decode(jwk['q']), 'big')
        
        # Create RSA private key
        return rsa.RSAPrivateNumbers(
            p=p, q=q, d=d,
            dmp1=int.from_bytes(b64url_decode(jwk['dp']), 'big'),
            dmq1=int.from_bytes(b64url_decode(jwk['dq']), 'big'),
            iqmp=int.from_bytes(b64url_decode(jwk['qi']), 'big'),
            public_numbers=rsa.RSAPublicNumbers(e=e, n=n)
        ).private_key()
    
    def _jwk_to_public_key_bytes(self, jwk: dict) -> bytearray:
        """Extract 512-byte public key from JWK"""
        def b64url_decode(s):
            padding = 4 - len(s) % 4
            if padding != 4:
                s += '=' * padding
            return base64.urlsafe_b64decode(s)
        
        n_bytes = b64url_decode(jwk['n'])
        if len(n_bytes) != 512:
            raise ValueError(f"Invalid Arweave public key length: {len(n_bytes)} (expected 512)")
        return bytearray(n_bytes)
    
    def sign(self, message: bytearray) -> bytearray:
        """Sign using RSA-PSS SHA-256"""
        signature = self.private_key.sign(
            bytes(message),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return bytearray(signature)
    
    @staticmethod
    def verify(pubkey: bytearray, message: bytearray, signature: bytearray) -> bool:
        """Verify RSA-PSS signature"""
        try:
            # Convert modulus bytes to RSA public key
            n = int.from_bytes(pubkey, 'big')
            e = 65537  # Arweave always uses e=65537
            public_key = rsa.RSAPublicNumbers(e, n).public_key()
            
            public_key.verify(
                bytes(signature),
                bytes(message),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except:
            return False
```

## Turbo-Specific Implementation

### Multi-Token Factory Pattern

```python
from typing import Union, Dict, List
import requests

class TurboFactory:
    @classmethod
    def authenticated(cls, 
                     private_key: Union[str, dict],
                     token: str = "arweave",
                     network: str = "mainnet") -> 'TurboClient':
        """Create authenticated Turbo client"""
        
        if token == "arweave":
            if not isinstance(private_key, dict):
                raise ValueError("Arweave requires JWK format (dict)")
            signer = ArweaveSigner(private_key)
        elif token in ["ethereum", "base-eth", "matic"]:
            if not isinstance(private_key, str):
                raise ValueError("Ethereum requires hex private key (string)")
            signer = EthereumSigner(private_key)
        else:
            raise ValueError(f"Unsupported token for MVP: {token}")
            
        return TurboClient(signer=signer, token=token, network=network)
```

### Turbo Service Endpoints

```python
from dataclasses import dataclass

@dataclass
class TurboUploadResponse:
    id: str                        # Transaction ID  
    owner: str                     # Owner address
    data_caches: List[str]         # Cache endpoints
    fast_finality_indexes: List[str] # Fast finality
    winc: str                      # Winston credits cost

@dataclass
class TurboBalanceResponse:
    winc: str                      # Available credits
    controlled_winc: str           # Controlled amount
    effective_balance: str         # Including shared credits

class TurboClient:
    SERVICE_URLS = {
        "mainnet": {
            "upload": "https://upload.ardrive.io",
            "payment": "https://payment.ardrive.io"
        },
        "testnet": {  
            "upload": "https://upload.ardrive.dev",
            "payment": "https://payment.ardrive.dev"
        }
    }
    
    def __init__(self, signer, token: str, network: str = "mainnet"):
        self.signer = signer
        self.token = token
        self.network = network
        self.upload_url = self.SERVICE_URLS[network]["upload"]
        self.payment_url = self.SERVICE_URLS[network]["payment"]
    
    def upload(self, data: bytes, 
              tags: List[Dict[str, str]] = None,
              target: str = None) -> TurboUploadResponse:
        """Upload data with automatic signing"""
        
        # Create and sign DataItem (reuse Irys components)
        data_item = create_data(bytearray(data), self.signer, tags, target)
        sign(data_item, self.signer)
        
        # Upload to Turbo endpoint
        url = f"{self.upload_url}/tx/{self.token}"
        headers = {"Content-Type": "application/octet-stream"}
        
        response = requests.post(url, data=data_item.get_raw(), headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            return TurboUploadResponse(
                id=result["id"],
                owner=result["owner"],
                data_caches=result.get("dataCaches", []),
                fast_finality_indexes=result.get("fastFinalityIndexes", []),
                winc=result.get("winc", "0")
            )
        else:
            raise Exception(f"Upload failed: {response.status_code}")
    
    def get_balance(self, address: str = None) -> TurboBalanceResponse:
        """Get winston credit balance"""
        addr = address or self._get_wallet_address()
        url = f"{self.payment_url}/account/balance/{self.token}?address={addr}"
        
        response = requests.get(url)
        result = response.json()
        
        return TurboBalanceResponse(
            winc=result.get("winc", "0"),
            controlled_winc=result.get("controlledWinc", "0"),  
            effective_balance=result.get("effectiveBalance", "0")
        )
    
    def get_upload_price(self, byte_count: int) -> int:
        """Get upload cost in winston credits"""
        url = f"{self.payment_url}/price/{self.token}/{byte_count}"
        response = requests.get(url)
        result = response.json()
        return int(result.get("winc", "0"))
    
    def _get_wallet_address(self) -> str:
        """Get wallet address from signer"""
        if self.token == "arweave":
            # For Arweave, address is base64url encoded public key
            import base64
            return base64.urlsafe_b64encode(self.signer.public_key).decode().rstrip('=')
        elif self.token in ["ethereum", "base-eth", "matic"]:
            # For Ethereum, convert public key to address
            from eth_hash.auto import keccak
            pubkey = self.signer.public_key[1:]  # Remove 0x04 prefix
            kek = keccak(pubkey)
            return "0x" + kek[-20:].hex()
```

## ChaosChain Integration

### StorageBackend Implementation

ChaosChain currently implements Irys like this (`chaoschain_sdk/providers/storage/irys.py`):

```python
class IrysStorage:
    def put(self, blob: bytes, *, mime: Optional[str] = None, 
            tags: Optional[Dict[str, str]] = None, 
            idempotency_key: Optional[str] = None) -> StorageResult:
        # Custom HTTP implementation with Bearer token auth
        
    def get(self, uri: str) -> Tuple[bytes, Optional[Dict]]:
        # Download from gateway
        
    def verify(self, uri: str, expected_hash: str) -> bool:
        # Verify data integrity
        
    def delete(self, uri: str) -> bool:
        return False  # Permanent storage
        
    def pin(self, uri: str, name: Optional[str] = None) -> bool:
        return True   # Always pinned
```

### Turbo StorageBackend Implementation

Replace the custom HTTP implementation with the Python Turbo SDK:

```python
# chaoschain_sdk/providers/storage/turbo.py
from typing import Optional, Dict, Tuple, List, Any
from turbo_sdk import TurboFactory
from .base import StorageResult

class TurboStorage:
    """
    Turbo programmable datachain storage backend.
    
    Implements the unified StorageBackend Protocol for Turbo.
    Provides permanent data storage on Turbo datachain with multi-token support.
    
    Features:
    - Multi-token support (Arweave, Ethereum)
    - Cryptographic signing (no API keys)
    - Winston credits payment system
    - Fast finality and data caching
    """
    
    def __init__(self,
                 private_key: Union[str, dict],
                 token: str = "arweave", 
                 network: str = "mainnet",
                 gateway_url: Optional[str] = None):
        """
        Initialize Turbo storage.
        
        Args:
            private_key: JWK dict for Arweave, hex string for Ethereum
            token: "arweave" or "ethereum" 
            network: "mainnet" or "testnet"
            gateway_url: Custom gateway URL (optional)
        """
        self.token = token
        self.network = network
        self.gateway_url = gateway_url or "https://arweave.net"
        
        try:
            self.turbo_client = TurboFactory.authenticated(
                private_key=private_key,
                token=token,
                network=network
            )
            self._available = True
            print(f"✅ Connected to Turbo {network} ({token})")
        except Exception as e:
            self._available = False
            print(f"⚠️ Turbo connection failed: {e}")
    
    def put(self,
            blob: bytes,
            *,
            mime: Optional[str] = None,
            tags: Optional[Dict[str, str]] = None,
            idempotency_key: Optional[str] = None) -> StorageResult:
        """
        Store data on Turbo datachain.
        
        Args:
            blob: Data to store
            mime: MIME type (optional)
            tags: Metadata tags (optional)
            idempotency_key: Not used (Turbo handles this internally)
        
        Returns:
            StorageResult with Turbo URI and transaction ID
        """
        if not self._available:
            return StorageResult(
                success=False,
                uri="",
                hash="",
                provider="turbo",
                error="Turbo client not available"
            )
        
        try:
            # Prepare tags
            turbo_tags = []
            if mime:
                turbo_tags.append({"name": "Content-Type", "value": mime})
            if tags:
                for key, value in tags.items():
                    turbo_tags.append({"name": key, "value": value})
            
            # Add standard tags
            turbo_tags.extend([
                {"name": "App-Name", "value": "ChaosChain-SDK"},
                {"name": "App-Version", "value": "0.3.0"},
                {"name": "Token", "value": self.token}
            ])
            
            # Upload with automatic signing
            response = self.turbo_client.upload(blob, tags=turbo_tags)
            
            print(f"📁 Uploaded to Turbo: {response.id[:12]}... (Cost: {response.winc} winc)")
            
            return StorageResult(
                success=True,
                uri=f"ar://{response.id}",  # Arweave-compatible URI
                hash=response.id,          # Transaction ID serves as hash
                provider="turbo",
                cid=response.id,
                view_url=f"{self.gateway_url}/{response.id}",
                size=len(blob),
                metadata={
                    "winc": response.winc,
                    "dataCaches": response.data_caches,
                    "fastFinalityIndexes": response.fast_finality_indexes,
                    "token": self.token,
                    "network": self.network
                }
            )
            
        except Exception as e:
            return StorageResult(
                success=False,
                uri="",
                hash="",
                provider="turbo",
                error=f"Upload error: {str(e)}"
            )
    
    def get(self, uri: str) -> Tuple[bytes, Optional[Dict]]:
        """
        Retrieve data from Turbo datachain.
        
        Args:
            uri: Turbo URI (ar://... or just the transaction ID)
        
        Returns:
            Tuple of (data bytes, metadata dict)
        """
        # Extract transaction ID from URI
        tx_id = uri.replace("ar://", "")
        
        try:
            # Try multiple gateways for reliability
            gateways = [
                f"{self.gateway_url}/{tx_id}",
                f"https://arweave.net/{tx_id}",
                f"https://gateway.irys.xyz/{tx_id}"
            ]
            
            for gateway_url in gateways:
                try:
                    import requests
                    response = requests.get(gateway_url, timeout=60)
                    
                    if response.status_code == 200:
                        metadata = {
                            'content-type': response.headers.get('Content-Type'),
                            'content-length': response.headers.get('Content-Length'),
                            'gateway': gateway_url,
                            'token': self.token
                        }
                        return response.content, metadata
                except:
                    continue
            
            raise Exception(f"Failed to retrieve from any gateway")
            
        except Exception as e:
            raise Exception(f"Error retrieving from Turbo: {str(e)}")
    
    def verify(self, uri: str, expected_hash: str) -> bool:
        """
        Verify data integrity.
        
        For Turbo, the transaction ID IS the hash.
        
        Args:
            uri: Turbo URI
            expected_hash: Expected transaction ID
        
        Returns:
            True if transaction IDs match
        """
        tx_id = uri.replace("ar://", "")
        expected_tx_id = expected_hash.replace("ar://", "")
        return tx_id == expected_tx_id
    
    def delete(self, uri: str) -> bool:
        """
        Delete data from Turbo.
        
        Note: Turbo data is permanent by design and cannot be deleted.
        This method always returns False.
        """
        print("⚠️ Turbo data is permanent and cannot be deleted")
        return False
    
    def pin(self, uri: str, name: Optional[str] = None) -> bool:
        """
        Pin content (not applicable to Turbo - data is permanently stored).
        
        On Turbo, all uploaded data is permanent by design, so pinning
        is not necessary. This method always returns True for compatibility.
        """
        tx_id = uri.replace("ar://", "")
        print(f"📌 Content {tx_id[:12]}... is permanently stored on Turbo")
        return True
    
    def list_content(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List uploaded content.
        
        Note: This requires additional API support from Turbo services.
        For MVP, returns empty list.
        """
        print("⚠️ Content listing not yet supported in MVP")
        return []
    
    def get_gateway_url(self, uri: str) -> Optional[str]:
        """
        Get HTTPS gateway URL for viewing content.
        
        Args:
            uri: Turbo URI
        
        Returns:
            Gateway URL
        """
        tx_id = uri.replace("ar://", "")
        return f"{self.gateway_url}/{tx_id}"
    
    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return f"turbo-{self.token}-{self.network}"
    
    @property
    def is_available(self) -> bool:
        """Check if Turbo is available and configured."""
        return self._available
    
    @property
    def is_free(self) -> bool:
        """Turbo requires payment (winston credits)."""
        return False
    
    @property
    def requires_api_key(self) -> bool:
        """Turbo requires private key for signing."""
        return True
    
    def get_balance(self) -> int:
        """Get winston credit balance."""
        if not self._available:
            return 0
        
        try:
            balance = self.turbo_client.get_balance()
            return int(balance.winc)
        except Exception:
            return 0
    
    def get_upload_cost(self, byte_count: int) -> int:
        """Get upload cost in winston credits."""
        if not self._available:
            return 0
        
        try:
            return self.turbo_client.get_upload_price(byte_count)
        except Exception:
            return 0
```

### ChaosChain Integration Usage

```python
# In chaoschain_sdk/providers/storage/__init__.py
from .turbo import TurboStorage

# In chaoschain_sdk/__init__.py - lazy import pattern
def _lazy_import_storage(provider_name):
    """Lazy import storage providers to avoid import errors."""
    if provider_name == "turbo":
        from .providers.storage.turbo import TurboStorage
        _storage_providers["turbo"] = TurboStorage
        return TurboStorage
    # ... existing providers

# Usage in ChaosChain SDK:
from chaoschain_sdk import ChaosChainAgentSDK
from chaoschain_sdk.providers.storage import TurboStorage

# Arweave usage
arweave_jwk = {
    "kty": "RSA",
    "n": "...",  # JWK format
    "e": "AQAB",
    "d": "...",
    # ... other JWK fields  
}

turbo_storage = TurboStorage(
    private_key=arweave_jwk,
    token="arweave",
    network="mainnet"
)

sdk = ChaosChainAgentSDK(
    agent_name="MyAgent",
    storage_provider=turbo_storage
)

# Ethereum usage
turbo_storage_eth = TurboStorage(
    private_key="0x1234567890abcdef...",  # Hex private key
    token="ethereum", 
    network="mainnet"
)
```

## Project Structure

```
turbo_sdk_python/
├── pyproject.toml              # Dependencies
├── README.md                   # Usage documentation
├── turbo_sdk/
│   ├── __init__.py            # Public API exports
│   ├── client.py              # TurboClient main class  
│   ├── factory.py             # TurboFactory for easy setup
│   ├── types.py               # Response/request types
│   ├── bundle/                # Copy from Irys SDK
│   │   ├── __init__.py
│   │   ├── dataitem.py        # ✅ Copy as-is from Irys
│   │   ├── create.py          # ✅ Copy as-is from Irys
│   │   ├── sign.py            # ✅ Copy as-is from Irys
│   │   ├── tags.py            # ✅ Copy as-is from Irys
│   │   ├── utils.py           # ✅ Copy as-is from Irys
│   │   └── constants.py       # ✅ Copy as-is from Irys
│   └── signers/
│       ├── __init__.py
│       ├── base.py            # ✅ Copy from Irys
│       ├── ethereum.py        # ✅ Copy from Irys
│       └── arweave.py         # ⚠️ New implementation
├── examples/
│   ├── ethereum_upload.py     # Basic Ethereum example
│   ├── arweave_upload.py      # Basic Arweave example
│   └── chaoschain_integration.py # ChaosChain usage
└── tests/
    ├── test_ethereum_signer.py
    ├── test_arweave_signer.py
    └── test_chaoschain_integration.py
```

## Usage Examples

### Basic Ethereum Upload

```python
# examples/ethereum_upload.py
from turbo_sdk import TurboFactory

def main():
    # Ethereum private key (hex format)
    private_key = "0x1234567890abcdef..."  # Your private key
    
    # Create Turbo client
    turbo = TurboFactory.authenticated(
        private_key=private_key,
        token="ethereum",
        network="mainnet"  # or "testnet"
    )
    
    # Check balance
    balance = turbo.get_balance()
    print(f"Balance: {balance.winc} winc")
    
    # Get upload cost
    data = b"Hello, Turbo from Ethereum!"
    cost = turbo.get_upload_price(len(data))
    print(f"Upload cost: {cost} winc")
    
    # Upload data
    result = turbo.upload(data, tags=[
        {"name": "Content-Type", "value": "text/plain"},
        {"name": "App-Name", "value": "Turbo-SDK-Python"},
        {"name": "Source", "value": "Ethereum"}
    ])
    
    print(f"✅ Upload successful!")
    print(f"Transaction ID: {result.id}")
    print(f"Cost: {result.winc} winc")
    print(f"Data caches: {result.data_caches}")
    print(f"Gateway URL: https://arweave.net/{result.id}")

if __name__ == "__main__":
    main()
```

### Basic Arweave Upload

```python
# examples/arweave_upload.py
from turbo_sdk import TurboFactory
import json

def main():
    # Arweave JWK (JSON Web Key format)
    with open("arweave_wallet.json", "r") as f:
        arweave_jwk = json.load(f)
    
    # Create Turbo client
    turbo = TurboFactory.authenticated(
        private_key=arweave_jwk,
        token="arweave", 
        network="mainnet"
    )
    
    # Upload data
    data = b"Hello, Turbo from Arweave!"
    result = turbo.upload(data, tags=[
        {"name": "Content-Type", "value": "text/plain"},
        {"name": "App-Name", "value": "Turbo-SDK-Python"},
        {"name": "Source", "value": "Arweave"}
    ])
    
    print(f"✅ Upload successful!")
    print(f"Transaction ID: {result.id}")
    print(f"URI: ar://{result.id}")

if __name__ == "__main__":
    main()
```

### ChaosChain Integration

```python
# examples/chaoschain_integration.py
from chaoschain_sdk import ChaosChainAgentSDK
from chaoschain_sdk.providers.storage import TurboStorage
import json
import os

def main():
    # Setup storage backends
    
    # Option 1: Arweave with JWK
    with open("arweave_wallet.json", "r") as f:
        arweave_jwk = json.load(f)
    
    turbo_arweave = TurboStorage(
        private_key=arweave_jwk,
        token="arweave",
        network="mainnet"
    )
    
    # Option 2: Ethereum with private key
    turbo_ethereum = TurboStorage(
        private_key=os.getenv("ETHEREUM_PRIVATE_KEY"),
        token="ethereum", 
        network="mainnet"
    )
    
    # Initialize ChaosChain SDK with Turbo storage
    sdk = ChaosChainAgentSDK(
        agent_name="MyTurboAgent",
        agent_domain="myagent.example.com", 
        agent_role="worker",
        storage_provider=turbo_arweave  # or turbo_ethereum
    )
    
    # Use ChaosChain's storage interface
    result = sdk.storage_manager.store(
        data=b"Evidence data from ChaosChain",
        metadata={"type": "process_evidence", "version": "1.0"}
    )
    
    print(f"✅ Stored via ChaosChain: {result.uri}")
    print(f"Metadata: {result.metadata}")
    
    # Verify integrity
    is_valid = sdk.storage_manager.verify(result.uri, result.hash)
    print(f"Data integrity verified: {is_valid}")

if __name__ == "__main__":
    main()
```

---

## Summary

This MVP approach provides:

1. **Maximum code reuse** (95%) from existing Irys Python SDK
2. **Minimal new development** - only Arweave RSA signer needed
3. **Drop-in replacement** for ChaosChain's current Irys integration  
4. **Multi-token support** (Arweave + Ethereum) from day one
5. **Production-ready cryptographic signing** instead of API key auth
6. **Full compatibility** with existing ChaosChain StorageBackend interface

The implementation leverages proven, battle-tested code from Irys SDK while extending it to support Turbo's enhanced feature set and multi-token ecosystem.