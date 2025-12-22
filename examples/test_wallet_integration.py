#!/usr/bin/env python3
"""
Test integration with real Arweave wallet (without network calls)
"""
import json
from pathlib import Path
from turbo_sdk import Turbo, ArweaveSigner


def main():
    # Load the real wallet
    wallet_path = Path(__file__).parent / "test-wallet.json"
    if not wallet_path.exists():
        wallet_path = Path("test-wallet.json")  # Try current directory

    if not wallet_path.exists():
        print("❌ test-wallet.json not found")
        print("   Expected location: test-wallet.json")
        return

    try:
        with open(wallet_path) as f:
            jwk = json.load(f)
        print("✅ Loaded test-wallet.json")
    except Exception as e:
        print(f"❌ Failed to load wallet: {e}")
        return

    # Test Arweave signer creation
    try:
        signer = ArweaveSigner(jwk)
        print("✅ Created ArweaveSigner")
        print(f"   - Type: {signer.signature_type}")
        print(f"   - Public key length: {len(signer.public_key)} bytes")
    except Exception as e:
        print(f"❌ Failed to create signer: {e}")
        return

    # Test Turbo client creation
    try:
        turbo = Turbo(signer, network="testnet")
        print("✅ Created Turbo client")
        print(f"   - Token: {turbo.token}")
        print(f"   - Network: {turbo.network}")
        print(f"   - Upload URL: {turbo.upload_url}")
    except Exception as e:
        print(f"❌ Failed to create Turbo client: {e}")
        return

    # Test signing capability (without network)
    try:
        test_message = bytearray(b"Hello, Arweave!")
        signature = signer.sign(test_message)
        print("✅ Successfully signed test message")
        print(f"   - Message: {test_message}")
        print(f"   - Signature length: {len(signature)} bytes")
        print(f"   - First few bytes: {signature[:8].hex()}")
    except Exception as e:
        print(f"❌ Failed to sign message: {e}")
        return

    print("\n🎉 All tests passed! Your wallet integration is working.")
    print("\nNext steps:")
    print("1. Fund your wallet with winston credits")
    print("2. Try running examples/arweave_upload.py")


if __name__ == "__main__":
    main()
