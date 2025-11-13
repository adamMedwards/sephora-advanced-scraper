import logging
import time
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

class RequestHelper:
    """
    Thin wrapper around requests.Session that provides retry logic,
    sensible defaults, and lightweight logging for scraping runs.
    """

    def __init__(
        self,
        default_headers: Optional[Dict[str, str]] = None,
        timeout: float = 20.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        self.session = requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        if default_headers:
            headers.update(default_headers)

        self.session.headers.update(headers)

    def fetch_html(self, url: str) -> Optional[str]:
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug("Requesting %s (attempt %d)", url, attempt)
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code == 200:
                    return resp.text
                logger.warning("Non-200 status for %s: %s", url, resp.status_code)
            except requests.RequestException as e:
                logger.warning("Request error for %s: %s", url, e)

            if attempt < self.max_retries:
                sleep_time = self.backoff_factor * attempt
                logger.debug("Backing off for %.2f seconds before retry.", sleep_time)
                time.sleep(sleep_time)

        logger.error("Failed to fetch %s after %d attempts.", url, self.max_retries)
        return None