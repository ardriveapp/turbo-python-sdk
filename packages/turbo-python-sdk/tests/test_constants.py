import pytest
from turbo_sdk.bundle.constants import SIG_CONFIG, MAX_TAG_BYTES, MIN_BINARY_SIZE


class TestConstants:
    """Test constants defined in bundle/constants.py"""

    def test_sig_config_structure(self):
        """Test signature configuration structure"""
        # Should have Arweave (type 1) and Ethereum (type 3)
        assert 1 in SIG_CONFIG
        assert 3 in SIG_CONFIG

        # Check Arweave config
        arweave_config = SIG_CONFIG[1]
        assert arweave_config["sigLength"] == 512
        assert arweave_config["pubLength"] == 512
        assert arweave_config["sigName"] == "arweave"

        # Check Ethereum config
        ethereum_config = SIG_CONFIG[3]
        assert ethereum_config["sigLength"] == 65
        assert ethereum_config["pubLength"] == 65
        assert ethereum_config["sigName"] == "ethereum"

    def test_sig_config_keys(self):
        """Test that signature configs have required keys"""
        for sig_type, config in SIG_CONFIG.items():
            assert "sigLength" in config
            assert "pubLength" in config
            assert "sigName" in config

            # All values should be positive integers for lengths
            assert isinstance(config["sigLength"], int)
            assert isinstance(config["pubLength"], int)
            assert config["sigLength"] > 0
            assert config["pubLength"] > 0

            # sigName should be a string
            assert isinstance(config["sigName"], str)
            assert len(config["sigName"]) > 0

    def test_max_tag_bytes(self):
        """Test MAX_TAG_BYTES constant"""
        assert isinstance(MAX_TAG_BYTES, int)
        assert MAX_TAG_BYTES > 0
        assert MAX_TAG_BYTES == 4096

    def test_min_binary_size(self):
        """Test MIN_BINARY_SIZE constant"""
        assert isinstance(MIN_BINARY_SIZE, int)
        assert MIN_BINARY_SIZE > 0
        assert MIN_BINARY_SIZE == 80
