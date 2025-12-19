import codecs
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys import keys


class EthereumSigner:
    signature_type = 3
    signature_length = 65
    owner_length = 65

    def __init__(self, private_key: str):
        """
        Initialize Ethereum signer with private key

        Args:
            private_key: Hex string private key (with or without 0x prefix)
        """
        private_key = private_key[2:] if private_key.startswith("0x") else private_key
        dec = codecs.decode(private_key, "hex")
        self.private_key = keys.PrivateKey(dec)
        self.public_key = b"\x04" + self.private_key.public_key.to_bytes()

    def sign(self, message: bytearray) -> bytearray:
        """
        Sign a message using Ethereum's personal_sign format

        Args:
            message: The message to sign

        Returns:
            The signature as bytearray
        """
        msg = encode_defunct(primitive=message)
        acc = Account.from_key(self.private_key)
        signature = acc.sign_message(msg).signature.hex()
        return bytearray.fromhex(signature[2:] if signature.startswith("0x") else signature)
