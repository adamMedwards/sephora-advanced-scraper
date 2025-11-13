import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from ..utils.html_utils import (
    extract_json_ld_objects,
    extract_meta_tag,
    extract_numeric_from_text,
)
from ..extractors.reviews_extractor import extract_reviews
from ..extractors.questions_extractor import extract_questions
from ..extractors.stats_extractor import build_statistics_from_reviews

logger = logging.getLogger(__name__)

@dataclass
class ProductInfo:
    id: Optional[str] = None
    name: Optional[str] = None
    image: Optional[str] = None
    description: Optional[str] = None
    is_available: Optional[bool] = None
    brand: Optional[str] = None
    price: Optional[str] = None
    love_count: Optional[str] = None

@dataclass
class ProductVariant:
    variant_id: Optional[str] = None
    variant_description: Optional[str] = None
    is_variant_available: Optional[bool] = None
    variant_name: Optional[str] = None
    variant_image: Optional[str] = None

class ProductParser:
    """
    High-level product parser that coordinates HTML/JSON-LD parsing and delegates
    review/statistics/questions extraction to dedicated modules.
    """

    def parse_product(self, html: str, source_url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")

        json_ld_objects = extract_json_ld_objects(soup)
        product_json = self._find_product_json(json_ld_objects)

        info = self._build_product_info(soup, product_json, source_url)
        variants = self._build_variants(product_json)
        reviews = extract_reviews(soup, product_json)
        questions = extract_questions(soup, product_json)
        statistics = build_statistics_from_reviews(reviews)

        product_record: Dict[str, Any] = {
            "info": asdict(info),
            "product_variants": [asdict(v) for v in variants],
            "statistics": statistics,
            "reviews": reviews,
            "questions": questions,
            "_source": {
                "url": source_url,
            },
        }

        return product_record

    def _find_product_json(self, json_ld_objects: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for obj in json_ld_objects:
            t = obj.get("@type")
            if isinstance(t, list):
                if "Product" in t:
                    return obj
            elif t == "Product":
                return obj
        return None

    def _build_product_info(
        self,
        soup: BeautifulSoup,
        product_json: Optional[Dict[str, Any]],
        source_url: str,
    ) -> ProductInfo:
        info = ProductInfo()

        # Use JSON-LD if available
        if product_json:
            info.id = product_json.get("sku") or product_json.get("productID")
            info.name = product_json.get("name")
            desc = product_json.get("description")
            if isinstance(desc, str):
                info.description = desc.strip()
            brand = product_json.get("brand")
            if isinstance(brand, dict):
                info.brand = brand.get("name")
            elif isinstance(brand, str):
                info.brand = brand

            # Offers can contain price & availability
            offers = product_json.get("offers")
            if isinstance(offers, dict):
                price = offers.get("price")
                currency = offers.get("priceCurrency")
                if price:
                    info.price = f"{price} {currency}".strip() if currency else str(price)
                availability = offers.get("availability")
                if isinstance(availability, str):
                    info.is_available = "InStock" in availability or "instock" in availability.lower()

        # Fallbacks from meta tags
        if not info.name:
            info.name = extract_meta_tag(soup, property="og:title") or extract_meta_tag(
                soup, name="title"
            )
        if not info.image:
            info.image = extract_meta_tag(soup, property="og:image")
        if not info.description:
            info.description = extract_meta_tag(soup, name="description")

        # Sephora-specific "loves" count often shows as "XXK loves"
        love_text = extract_meta_tag(soup, name="twitter:data2") or ""
        love_number = extract_numeric_from_text(love_text)
        if love_number:
            info.love_count = love_number

        # Availability heuristic if not set
        if info.is_available is None:
            body_text = soup.get_text(separator=" ", strip=True).lower()
            if "out of stock" in body_text or "sold out" in body_text:
                info.is_available = False
            else:
                info.is_available = True

        # Derive ID from URL if missing
        if not info.id:
            # Sephora products often have IDs like "P455369" in URL
            import re

            match = re.search(r"/(P\d+)", source_url)
            if match:
                info.id = match.group(1)

        # Brand fallback
        if not info.brand:
            info.brand = extract_meta_tag(soup, property="og:site_name") or "Sephora"

        return info

    def _build_variants(
        self, product_json: Optional[Dict[str, Any]]
    ) -> List[ProductVariant]:
        variants: List[ProductVariant] = []

        if not product_json:
            return variants

        # Some Sephora pages may embed variants arrays within "offers" or custom keys
        offers = product_json.get("offers")
        if isinstance(offers, list):
            for offer in offers:
                v = ProductVariant(
                    variant_id=str(offer.get("sku") or offer.get("productID") or "") or None,
                    variant_description=offer.get("description"),
                    is_variant_available=self._is_offer_available(offer),
                    variant_name=offer.get("name"),
                    variant_image=offer.get("image"),
                )
                variants.append(v)
        elif isinstance(offers, dict):
            v = ProductVariant(
                variant_id=str(offers.get("sku") or offers.get("productID") or "") or None,
                variant_description=offers.get("description"),
                is_variant_available=self._is_offer_available(offers),
                variant_name=offers.get("name"),
                variant_image=offers.get("image"),
            )
            variants.append(v)

        return variants

    @staticmethod
    def _is_offer_available(offer: Dict[str, Any]) -> Optional[bool]:
        availability = offer.get("availability")
        if isinstance(availability, str):
            avail_lower = availability.lower()
            if "instock" in avail_lower or "in stock" in avail_lower:
                return True
            if "outofstock" in avail_lower or "out of stock" in avail_lower:
                return False
        return None