#!/usr/bin/env python3
"""
Example: Upload data using Arweave JWK wallet
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

    # Create signer and Turbo client
    try:
        signer = ArweaveSigner(arweave_jwk)
        turbo = Turbo(signer, network="mainnet")
        print("🔑 Connected with Arweave signer")
    except Exception as e:
        print(f"❌ Failed to create Turbo client: {e}")
        sys.exit(1)

    # Check balance
    try:
        balance = turbo.get_balance()
        print(f"💰 Balance: {balance.winc} winc")
    except Exception as e:
        print(f"⚠️ Could not fetch balance: {e}")

    # Prepare minimal data to upload
    data = b"test"

    # Get upload cost
    try:
        cost = turbo.get_upload_price(len(data))
        print(f"💸 Upload cost for {len(data)} bytes: {cost} winc")
    except Exception as e:
        print(f"⚠️ Could not fetch price: {e}")

    # Upload data
    try:
        result = turbo.upload(
            data,
            tags=[
                {"name": "Content-Type", "value": "text/plain"},
                {"name": "App-Name", "value": "Turbo-SDK-Python"},
                {"name": "Source", "value": "Arweave"},
            ],
        )

        print("✅ Upload successful!")
        print(f"📄 Transaction ID: {result.id}")
        print(f"🔗 URI: ar://{result.id}")
        print(f"💸 Cost: {result.winc} winc")
        print(f"🌐 Gateway URL: https://arweave.net/{result.id}")

        # v0.0.6 fields
        if result.timestamp:
            print(f"⏰ Timestamp: {result.timestamp}")
        if result.signature:
            print(f"✍️  Signature: {result.signature}")
        if result.public:
            print(f"🔑 Public Key: {result.public}")
        if result.version:
            print(f"📋 Version: {result.version}")
        if result.deadline_height:
            print(f"📏 Deadline Height: {result.deadline_height}")

    except Exception as e:
        print(f"❌ Upload failed: {e}")


if __name__ == "__main__":
    main()
