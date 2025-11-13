import logging
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class SimilarProductsParser:
    """
    Parses a product detail page and attempts to extract links to similar or
    recommended products ("You may also like", "Similar products", etc.).
    """

    def extract_similar_product_links(self, html: str, base_url: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: List[str] = []

        # Look for sections that contain recommendation copy
        candidate_sections = []
        keywords = ["you may also like", "similar", "recommended", "more like this"]

        for section in soup.find_all(["section", "div"]):
            text = section.get_text(" ", strip=True).lower()
            if any(k in text for k in keywords):
                candidate_sections.append(section)

        for section in candidate_sections:
            for a in section.find_all("a", href=True):
                href = a["href"]
                full_url = urljoin(base_url, href)
                if "/product/" in full_url:
                    links.append(full_url)

        # Fallback: some layouts might not group recommendations; as a fallback
        # we simply don't add anything rather than risk spurious URLs.
        seen = set()
        unique_links: List[str] = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)

        logger.debug("Extracted %d similar product links.", len(unique_links))
        return unique_links