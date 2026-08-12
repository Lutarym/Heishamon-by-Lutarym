"""Heishamon API Client."""

import aiohttp
import json
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

    async def async_get_data(self) -> Dict[str, Any]:
        """Fetch data from Heishamon /json endpoint."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/json"
                auth = None
                if self.username and self.password:
                    auth = aiohttp.BasicAuth(self.username, self.password)

                async with session.get(url, auth=auth, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        raise Exception(f"HTTP {response.status}: {await response.text()}")

        except aiohttp.ClientError as e:
            _LOGGER.error(f"Connection error to Heishamon: {e}")
            raise
        except json.JSONDecodeError as e:
            _LOGGER.error(f"JSON decode error: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"Unexpected error: {e}")
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

                async with session.get(
                    url, params=params, auth=auth, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        _LOGGER.debug(f"Set {key}={value} on Heishamon")
                        return True
                    else:
                        _LOGGER.error(f"HTTP {response.status} setting {key}: {await response.text()}")
                        return False

        except Exception as e:
            _LOGGER.error(f"Error setting {key}: {e}")
            return False

    async def test_connection(self) -> bool:
        """Test connection to Heishamon."""
        try:
            await self.async_get_data()
            return True
        except Exception:
            return False
