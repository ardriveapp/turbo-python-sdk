#!/usr/bin/env python3
"""
Example demonstrating balance checking with signed requests
"""

from turbo_sdk import Turbo, EthereumSigner


def main():
    # Example private key (use your own)
    private_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

    # Create signer and client
    signer = EthereumSigner(private_key)
    turbo = Turbo(signer, network="testnet")

    print("🔑 Wallet Address:", turbo.get_wallet_address())
    print("🌐 Network:", turbo.network)
    print("🏦 Payment URL:", turbo.payment_url)

    # Get balance with signed request (authenticates as this wallet)
    print("\n📊 Checking balance with signed request...")
    balance = turbo.get_balance()

    print("✅ Balance retrieved!")
    print(f"💰 Available Credits: {balance.winc} winc")
    print(f"🔒 Controlled Credits: {balance.controlled_winc} winc")
    print(f"⚡ Effective Balance: {balance.effective_balance} winc")

    if balance.winc == "0":
        print("💡 Zero balance indicates an unfunded wallet")

    # Example: Check another wallet's balance (no auth needed)
    other_address = "0x742d35Cc6635C0532925a3b8C17af2e95C5Aca4A"
    print(f"\n📊 Checking balance for {other_address}...")
    other_balance = turbo.get_balance(address=other_address)

    print("✅ Other balance retrieved!")
    print(f"💰 Available Credits: {other_balance.winc} winc")

    if other_balance.winc == "0":
        print("💡 This wallet also appears to be unfunded")


if __name__ == "__main__":
    main()
