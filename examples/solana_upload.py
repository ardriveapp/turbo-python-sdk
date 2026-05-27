#!/usr/bin/env python3
"""
Example: Upload data using a Solana wallet
"""

from turbo_sdk import Turbo, SolanaSigner


def main():
    # Solana secret key. Any of these forms work:
    #   - a Solana CLI ``id.json`` (use ``SolanaSigner.from_file("id.json")``)
    #   - a base58-encoded secret key (Phantom "export private key")
    #   - raw 64-byte secret key (seed||pubkey) or a 32-byte seed
    # Replace with your actual key (base58 shown here).
    secret_key = "your-base58-encoded-solana-secret-key"

    # Create signer and Turbo client
    signer = SolanaSigner(secret_key)
    turbo = Turbo(signer, network="mainnet")  # or "testnet"

    print(f"🔑 Connected with Solana signer ({signer.get_wallet_address()})")

    # Check balance
    try:
        balance = turbo.get_balance()
        print(f"💰 Balance: {balance.winc} winc")
    except Exception as e:
        print(f"⚠️ Could not fetch balance: {e}")

    # Prepare data to upload
    data = b"Hello, Turbo from Solana!"

    # Get upload cost
    try:
        cost = turbo.get_upload_price(len(data))
        print(f"💸 Upload cost: {cost} winc")
    except Exception as e:
        print(f"⚠️ Could not fetch price: {e}")

    # Upload data (files under 100 KiB are free-tier)
    try:
        result = turbo.upload(
            data,
            tags=[
                {"name": "Content-Type", "value": "text/plain"},
                {"name": "App-Name", "value": "Turbo-SDK-Python"},
                {"name": "Source", "value": "Solana"},
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
