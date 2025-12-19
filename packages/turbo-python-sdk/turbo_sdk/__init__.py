"""
Turbo SDK for Python

Python SDK for interacting with the Ardrive Turbo Upload and Payment Service.
"""

__version__ = "0.1.0"
__all__ = ["TurboClient"]


class TurboClient:
    """
    Main client for interacting with the Turbo service.
    
    This is a placeholder implementation. Full functionality will be added in future releases.
    """
    
    def __init__(self, api_key: str = None, base_url: str = "https://turbo.ardrive.io"):
        """
        Initialize the Turbo client.
        
        Args:
            api_key: Optional API key for authentication
            base_url: Base URL for the Turbo service
        """
        self.api_key = api_key
        self.base_url = base_url
    
    def __repr__(self) -> str:
        return f"TurboClient(base_url='{self.base_url}')"
