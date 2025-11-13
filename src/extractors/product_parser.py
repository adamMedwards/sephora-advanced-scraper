import json
import logging
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from .utils_format import (
    clean_text,
    infer_product_id_from_url,
    parse_float,
    parse_int,
    parse_number_with_suffix,
)

logger = logging.getLogger(__name__)

def _safe_meta_content(soup: BeautifulSoup, **attrs: str) -> Optional[str]:
    tag = soup.find("meta", attrs=attrs)
    if tag and tag.get("content"):
        return tag["content"]
    return None

def _extract_ld_json_blocks(soup: BeautifulSoup) -> List[Any]:
    blocks: List[Any] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            if not script.string:
                continue
            data = json.loads(script.string)
            blocks.append(data)
        except json.JSONDecodeError:
            continue
    return blocks

def _find_product_ld(blocks: List[Any]) -> Optional[Dict[str, Any]]:
    for block in blocks:
        if isinstance(block, dict) and block.get("@type") == "Product":
            return block
        if isinstance(block, list):
            for item in block:
                if isinstance(item, dict) and item.get("@type") == "Product":
                    return item
    return None

def parse_product_info(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    """
    Extract core product information from a Sephora product page.

    Uses OpenGraph tags, JSON-LD, and common Sephora markup as fallbacks.
    """
    logger.debug("Parsing product info from %s", url)
    ld_blocks = _extract_ld_json_blocks(soup)
    product_ld = _find_product_ld(ld_blocks)

    name = _safe_meta_content(soup, property="og:title") or ""
    description = _safe_meta_content(soup, property="og:description") or ""
    image = _safe_meta_content(soup, property="og:image") or ""
    brand = ""
    price_text = ""

    if product_ld:
        name = product_ld.get("name") or name
        description = product_ld.get("description") or description
        image = product_ld.get("image") or image
        brand_data = product_ld.get("brand")
        if isinstance(brand_data, dict):
            brand = brand_data.get("name") or ""
        elif isinstance(brand_data, str):
            brand = brand_data
        offers = product_ld.get("offers")
        if isinstance(offers, dict):
            price_text = offers.get("price") or offers.get("priceSpecification", {}).get("price", "")
        elif isinstance(offers, list) and offers:
            offer0 = offers[0]
            if isinstance(offer0, dict):
                price_text = offer0.get("price", "")

    if not brand:
        brand_tag = soup.find(attrs={"data-at": "brand_name"})
        if isinstance(brand_tag, Tag):
            brand = clean_text(brand_tag.get_text(strip=True))

    if not price_text:
        price_tag = soup.find(attrs={"data-at": "price"})
        if isinstance(price_tag, Tag):
            price_text = clean_text(price_tag.get_text(strip=True))

    love_count = 0
    love_tag = soup.find(attrs={"data-at": "loves"})
    if isinstance(love_tag, Tag):
        love_count = parse_number_with_suffix(love_tag.get_text(strip=True))

    availability = True
    availability_tag = soup.find(attrs={"data-at": "out_of_stock"})
    if isinstance(availability_tag, Tag):
        availability = False

    product_id = None
    if product_ld:
        product_id = product_ld.get("sku") or product_ld.get("productID")
    if not product_id:
        product_id = infer_product_id_from_url(url)

    info = {
        "id": product_id or "",
        "name": clean_text(name),
        "image": image,
        "description": clean_text(description),
        "is_available": availability,
        "brand": clean_text(brand),
        "price": str(price_text) if price_text is not None else "",
        "love_count": love_count,
        "url": url,
    }
    return info

def parse_product_variants(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    Extract product variants when available.

    Attempts to read variants from JSON-LD first; falls back to variant tiles.
    """
    logger.debug("Parsing product variants")
    variants: List[Dict[str, Any]] = []

    ld_blocks = _extract_ld_json_blocks(soup)
    product_ld = _find_product_ld(ld_blocks)
    if product_ld:
        variants_ld = product_ld.get("isVariantOf") or product_ld.get("offers")
        if isinstance(variants_ld, list):
            for idx, v in enumerate(variants_ld):
                if not isinstance(v, dict):
                    continue
                variant_id = v.get("sku") or v.get("productID") or f"variant-{idx}"
                variant_name = v.get("name") or v.get("description") or ""
                variant_image = v.get("image") or ""
                availability_raw = v.get("availability") or v.get("itemCondition")
                is_available = True
                if isinstance(availability_raw, str) and "OutOfStock" in availability_raw:
                    is_available = False
                variants.append(
                    {
                        "variant_id": str(variant_id),
                        "variant_description": clean_text(variant_name),
                        "is_variant_available": is_available,
                        "variant_name": clean_text(variant_name),
                        "variant_image": variant_image,
                    }
                )

    if variants:
        return variants

    # Fallback: best-effort tile parsing
    tile_candidates = soup.select('[data-comp*="ProductVariant"]:not(script)')
    for idx, tile in enumerate(tile_candidates):
        name_tag = tile.find(attrs={"data-at": "sku_name"}) or tile.find("span")
        img_tag = tile.find("img")
        availability_tag = tile.find(attrs={"data-at": "out_of_stock"})
        variant_name = clean_text(name_tag.get_text(strip=True)) if name_tag else f"Variant {idx + 1}"
        variant_image = img_tag["src"] if img_tag and img_tag.get("src") else ""
        variants.append(
            {
                "variant_id": f"variant-{idx}",
                "variant_description": variant_name,
                "is_variant_available": availability_tag is None,
                "variant_name": variant_name,
                "variant_image": variant_image,
            }
        )

    return variants

def parse_statistics(soup: BeautifulSoup, reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute statistics from the page and review list.
    Falls back to aggregating from reviews when explicit stats are not present.
    """
    logger.debug("Parsing statistics")
    average_rating = 0.0
    review_count = 0
    helpful_vote_count = 0
    not_helpful_vote_count = 0

    rating_tag = soup.find(attrs={"data-at": "overall_rating"})
    if rating_tag:
        average_rating = parse_float(rating_tag.get_text(strip=True), default=0.0)

    count_tag = soup.find(attrs={"data-at": "total_reviews"})
    if count_tag:
        review_count = parse_int(count_tag.get_text(strip=True), default=0)

    if not reviews:
        # Try to build stats from rating histogram if present
        histogram_rows = soup.select('[data-comp*="Histogram"] [role="row"]')
        if histogram_rows:
            total_reviews = 0
            weighted_sum = 0.0
            for row in histogram_rows:
                cells = row.find_all("span")
                if len(cells) < 2:
                    continue
                try:
                    rating_value = parse_float(cells[0].get_text(strip=True), default=0.0)
                    rating_count = parse_int(cells[1].get_text(strip=True), default=0)
                except (IndexError, ValueError):
                    continue
                total_reviews += rating_count
                weighted_sum += rating_value * rating_count
            if total_reviews > 0:
                average_rating = weighted_sum / total_reviews
                review_count = total_reviews
    else:
        # Aggregate from scraped reviews
        total_reviews = len(reviews)
        total_rating = 0.0
        for r in reviews:
            total_rating += float(r.get("rating") or 0)
            helpful_vote_count += parse_int(r.get("helpful_vote_count"), default=0)
            not_helpful_vote_count += parse_int(r.get("not_helpful_vote_count"), default=0)
        if total_reviews > 0:
            average_rating = total_rating / total_reviews
            review_count = total_reviews

    statistics = {
        "average_rating": round(average_rating, 2) if average_rating else 0.0,
        "helpful_vote_count": helpful_vote_count,
        "not_helpful_vote_count": not_helpful_vote_count,
        "review_count": review_count,
        "variant_count": 0,
    }

    return statistics