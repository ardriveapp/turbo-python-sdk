#!/usr/bin/env python3
"""
Example: Upload data using Ethereum private key
"""
from turbo_sdk import Turbo, EthereumSigner


def main():
    # Ethereum private key (hex format)
    # Replace with your actual private key
    private_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

    # Create signer and Turbo client
    signer = EthereumSigner(private_key)
    turbo = Turbo(signer, network="mainnet")  # or "testnet"

    print("🔑 Connected with Ethereum signer")

    # Check balance
    try:
        balance = turbo.get_balance()
        print(f"💰 Balance: {balance.winc} winc")
    except Exception as e:
        print(f"⚠️ Could not fetch balance: {e}")

    # Prepare data to upload
    data = b"Hello, Turbo from Ethereum!"

    # Get upload cost
    try:
        cost = turbo.get_upload_price(len(data))
        print(f"💸 Upload cost: {cost} winc")
    except Exception as e:
        print(f"⚠️ Could not fetch price: {e}")

    # Upload data
    try:
        result = turbo.upload(
            data,
            tags=[
                {"name": "Content-Type", "value": "text/plain"},
                {"name": "App-Name", "value": "Turbo-SDK-Python"},
                {"name": "Source", "value": "Ethereum"},
            ],
        )

        print("✅ Upload successful!")
        print(f"📄 Transaction ID: {result.id}")
        print(f"💸 Cost: {result.winc} winc")
        print(f"🚀 Data caches: {result.data_caches}")
        print(f"🌐 Gateway URL: https://arweave.net/{result.id}")

    except Exception as e:
        print(f"❌ Upload failed: {e}")


if __name__ == "__main__":
    main()
