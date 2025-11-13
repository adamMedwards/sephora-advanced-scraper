import logging
from typing import List
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class CategoryParser:
    """
    Parses Sephora category/listing pages and extracts product detail links.
    The implementation is resilient and uses several heuristics, so it can
    work even if the exact markup differs slightly.
    """

    def extract_product_links(self, html: str, base_url: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: List[str] = []

        # Common Sephora patterns
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href:
                continue

            # Normalize to absolute
            full_url = urljoin(base_url, href)

            # Heuristics: product URLs often contain "/product/" and product IDs
            if "/product/" in full_url:
                links.append(full_url)

        # Deduplicate while preserving order
        seen = set()
        unique_links: List[str] = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)

        logger.debug("Extracted %d unique product links from category page.", len(unique_links))
        return unique_links