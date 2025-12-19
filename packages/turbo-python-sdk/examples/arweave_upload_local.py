#!/usr/bin/env python3
"""
Example: Upload data using Arweave JWK wallet to local turbo service
"""
from turbo_sdk import Turbo, ArweaveSigner
import json
import sys


def main():
    # Load Arweave JWK from file
    try:
        with open("test-wallet.json", "r") as f:
            arweave_jwk = json.load(f)
    except FileNotFoundError:
        print("❌ Please create a 'test-wallet.json' file with your Arweave JWK")
        print("   You can generate one at https://arweave.app/wallet")
        sys.exit(1)
    except json.JSONDecodeError:
        print("❌ Invalid JSON in test-wallet.json")
        sys.exit(1)

    # Create signer and Turbo client pointing to local service
    try:
        signer = ArweaveSigner(arweave_jwk)
        turbo = Turbo(signer, network="testnet")
        # Override URLs to point to local service
        turbo.upload_url = "http://localhost:3000"
        turbo.payment_url = "http://localhost:3000"
        print("🔑 Connected with Arweave signer (local service)")
    except Exception as e:
        print(f"❌ Failed to create Turbo client: {e}")
        sys.exit(1)

    # Prepare data to upload
    data = b"Hello, Local Turbo!"

    print(f"📝 Data to upload: {data}")
    print(f"📊 Data size: {len(data)} bytes")

    # Upload data
    try:
        result = turbo.upload(
            data,
            tags=[
                {"name": "Content-Type", "value": "text/plain"},
                {"name": "App-Name", "value": "Turbo-SDK-Python"},
                {"name": "Source", "value": "Arweave"},
            ]
        )

        print("✅ Upload successful!")
        print(f"📄 Transaction ID: {result.id}")
        print(f"🔗 URI: ar://{result.id}")
        print(f"💸 Cost: {result.winc} winc")

    except Exception as e:
        print(f"❌ Upload failed: {e}")


if __name__ == "__main__":
    main()