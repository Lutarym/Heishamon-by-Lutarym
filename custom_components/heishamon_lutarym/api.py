"""Heishamon API Client."""
import asyncio
import aiohttp
import logging
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)


class HeishamonAPI:
    """Heishamon HTTP API Client."""

    def __init__(
        self,
        host: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """Initialize API client."""
        self.host = host
        self.username = username
        self.password = password
        self.base_url = f"http://{host}"
        _LOGGER.info(f"HeishamonAPI initialized for {self.base_url}")

    async def async_get_data(self) -> Dict[str, Any]:
        """Fetch data from Heishamon /json endpoint."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/json"
                auth = None
                if self.username and self.password:
                    auth = aiohttp.BasicAuth(self.username, self.password)

                _LOGGER.info(f"Fetching from {url}")
                
                try:
                    async with session.get(
                        url, auth=auth, timeout=aiohttp.ClientTimeout(total=20)
                    ) as response:
                        _LOGGER.info(f"Response status: {response.status}")
                        
                        if response.status == 200:
                            try:
                                data = await response.json()
                                _LOGGER.info(f"Got JSON data: {len(data) if isinstance(data, dict) else 'not dict'} keys")
                                
                                # Debug: Zeige erste paar Keys
                                if isinstance(data, dict):
                                    sample_keys = list(data.keys())[:5]
                                    _LOGGER.info(f"Sample keys: {sample_keys}")
                                    for key in sample_keys:
                                        _LOGGER.info(f"  {key}: {data[key]}")
                                
                                return data if isinstance(data, dict) else {}
                            except Exception as json_err:
                                _LOGGER.error(f"JSON parse error: {json_err}")
                                text = await response.text()
                                _LOGGER.error(f"Response text: {text[:500]}")
                                raise
                        else:
                            error_text = await response.text()
                            _LOGGER.error(f"HTTP {response.status}: {error_text[:200]}")
                            raise Exception(f"HTTP {response.status}")
                            
                except asyncio.TimeoutError:
                    _LOGGER.error(f"Timeout connecting to {url}")
                    raise Exception("Connection timeout")
                    
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Connection error to {self.base_url}: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"Heishamon API error: {type(e).__name__}: {e}")
            raise

    async def async_set_value(self, key: str, value: Any) -> bool:
        """Send command to Heishamon."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/command"
                params = {key: value}
                auth = None
                if self.username and self.password:
                    auth = aiohttp.BasicAuth(self.username, self.password)

                _LOGGER.debug(f"Setting {key}={value} on {url}")
                async with session.get(
                    url, params=params, auth=auth, timeout=aiohttp.ClientTimeout(total=20)
                ) as response:
                    success = response.status == 200
                    if success:
                        _LOGGER.debug(f"Successfully set {key}={value}")
                    else:
                        _LOGGER.error(f"Failed to set {key}: HTTP {response.status}")
                    return success
        except Exception as e:
            _LOGGER.error(f"Error setting {key}: {e}")
            return False

    async def test_connection(self) -> bool:
        """Test connection to Heishamon."""
        try:
            _LOGGER.info(f"Testing connection to {self.base_url}")
            data = await self.async_get_data()
            if data and isinstance(data, dict) and len(data) > 0:
                _LOGGER.info(f"✓ Connection test successful, got {len(data)} keys")
                return True
            else:
                _LOGGER.error(f"✗ Connection test failed: no data or wrong format")
                return False
        except Exception as e:
            _LOGGER.error(f"✗ Connection test failed: {e}")
            return False
