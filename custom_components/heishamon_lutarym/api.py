"""Heishamon API Client."""
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
        _LOGGER.debug(f"HeishamonAPI initialized for {self.base_url}")

    async def async_get_data(self) -> Dict[str, Any]:
        """Fetch data from Heishamon /json endpoint."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/json"
                auth = None
                if self.username and self.password:
                    auth = aiohttp.BasicAuth(self.username, self.password)

                _LOGGER.debug(f"Fetching from {url}")
                async with session.get(
                    url, auth=auth, timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        _LOGGER.debug(f"Got data from Heishamon: {len(data)} keys")
                        return data
                    else:
                        error_text = await response.text()
                        _LOGGER.error(f"HTTP {response.status}: {error_text}")
                        raise Exception(f"HTTP {response.status}: {error_text}")
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Connection error to {self.base_url}: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"Heishamon API error: {e}")
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
                    url, params=params, auth=auth, timeout=aiohttp.ClientTimeout(total=15)
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
            _LOGGER.debug(f"Testing connection to {self.base_url}")
            await self.async_get_data()
            _LOGGER.debug(f"Connection test successful")
            return True
        except Exception as e:
            _LOGGER.error(f"Connection test failed: {e}")
            return False
